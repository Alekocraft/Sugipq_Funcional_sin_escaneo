# models/inventario_corporativo_model_extended.py
"""
Extensiones al modelo de inventario corporativo para soportar:
- Asignación a usuarios del Active Directory
- Búsqueda de usuarios AD
- Notificaciones por email
- Sistema de confirmación con tokens
- DEVOLUCIONES de productos asignados
- TRASPASOS entre oficinas
"""
from database import get_database_connection
import logging

logger = logging.getLogger(__name__)


class InventarioCorporativoModelExtended:
    """
    Métodos adicionales para el modelo de inventario corporativo.
    Estos métodos pueden ser agregados a la clase InventarioCorporativoModel existente.
    """
    
    @staticmethod
    def asignar_a_usuario_ad(producto_id, oficina_id, cantidad, usuario_ad_info, usuario_accion):
        """
        Asigna un producto a un usuario específico del Active Directory.
        
        Args:
            producto_id: ID del producto a asignar
            oficina_id: ID de la oficina destino
            cantidad: Cantidad a asignar
            usuario_ad_info: Diccionario con información del usuario AD
                - username: Nombre de usuario AD
                - full_name: Nombre completo
                - email: Correo electrónico
                - department: Departamento
            usuario_accion: Usuario que realiza la acción
            
        Returns:
            dict: Resultado de la operación con 'success' y 'message'
        """
        conn = get_database_connection()
        if not conn:
            return {'success': False, 'message': 'Error de conexión a la base de datos'}
        
        cursor = None
        try:
            cursor = conn.cursor()
            
            # 1. Verificar stock disponible
            cursor.execute(
                "SELECT CantidadDisponible, NombreProducto FROM ProductosCorporativos "
                "WHERE ProductoId = ? AND Activo = 1",
                (int(producto_id),)
            )
            row = cursor.fetchone()
            if not row:
                return {'success': False, 'message': 'Producto no encontrado'}
            
            stock = int(row[0])
            nombre_producto = row[1]
            cant = int(cantidad)
            
            if cant <= 0:
                return {'success': False, 'message': 'La cantidad debe ser mayor a 0'}
            
            if cant > stock:
                return {'success': False, 'message': f'Stock insuficiente. Disponible: {stock}'}
            
            # 2. Buscar o crear usuario en la base de datos local
            usuario_asignado_id = InventarioCorporativoModelExtended._obtener_o_crear_usuario_ad(
                cursor, usuario_ad_info
            )
            
            if not usuario_asignado_id:
                return {'success': False, 'message': 'Error al procesar el usuario asignado'}
            
            # 3. Descontar stock
            cursor.execute("""
                UPDATE ProductosCorporativos
                SET CantidadDisponible = CantidadDisponible - ?
                WHERE ProductoId = ?
            """, (cant, int(producto_id)))
            
            # 4. Crear registro en tabla Asignaciones con usuario AD
            cursor.execute("""
                INSERT INTO Asignaciones 
                (ProductoId, OficinaId, UsuarioAsignadoId, FechaAsignacion, 
                 Estado, UsuarioAsignador, Activo, UsuarioADNombre, UsuarioADEmail)
                VALUES (?, ?, ?, GETDATE(), 'ASIGNADO', ?, 1, ?, ?)
            """, (
                int(producto_id), 
                int(oficina_id), 
                usuario_asignado_id,
                usuario_accion,
                usuario_ad_info.get('full_name', usuario_ad_info.get('username', '')),
                usuario_ad_info.get('email', '')
            ))
            
            # 5. Registrar en historial con información del usuario AD
            cursor.execute("""
                INSERT INTO AsignacionesCorporativasHistorial
                    (ProductoId, OficinaId, Accion, Cantidad, UsuarioAccion, 
                     Fecha, UsuarioAsignadoNombre, UsuarioAsignadoEmail)
                VALUES (?, ?, 'ASIGNAR', ?, ?, GETDATE(), ?, ?)
            """, (
                int(producto_id), 
                int(oficina_id), 
                cant, 
                usuario_accion,
                usuario_ad_info.get('full_name', usuario_ad_info.get('username', '')),
                usuario_ad_info.get('email', '')
            ))
            
            conn.commit()
            
            return {
                'success': True, 
                'message': 'Producto asignado correctamente',
                'usuario_email': usuario_ad_info.get('email'),
                'usuario_nombre': usuario_ad_info.get('full_name'),
                'producto_nombre': nombre_producto
            }
            
        except Exception as e:
            logger.error(f"Error asignar_a_usuario_ad: {e}")
            try:
                if conn: conn.rollback()
            except:
                pass
            return {'success': False, 'message': f'Error al asignar: {str(e)}'}
        finally:
            if cursor: cursor.close()
            if conn: conn.close()
    
    # ========================================================================
    # NUEVAS FUNCIONES: DEVOLUCIONES
    # ========================================================================
    
    @staticmethod
    def devolver_producto(asignacion_id, cantidad_devolver, motivo, usuario_accion, observaciones=''):
        """
        Procesa la devolución de un producto asignado.
        
        Args:
            asignacion_id: ID de la asignación a devolver
            cantidad_devolver: Cantidad a devolver
            motivo: Motivo de la devolución
            usuario_accion: Usuario que procesa la devolución
            observaciones: Observaciones adicionales (opcional)
            
        Returns:
            dict: Resultado con 'success' y 'message'
        """
        conn = get_database_connection()
        if not conn:
            return {'success': False, 'message': 'Error de conexión a la base de datos'}
        
        cursor = None
        try:
            cursor = conn.cursor()
            
            # 1. Obtener información de la asignación
            cursor.execute("""
                SELECT 
                    a.ProductoId,
                    a.OficinaId,
                    a.Estado,
                    a.UsuarioADNombre,
                    a.UsuarioADEmail,
                    p.NombreProducto,
                    p.CantidadDisponible
                FROM Asignaciones a
                INNER JOIN ProductosCorporativos p ON a.ProductoId = p.ProductoId
                WHERE a.AsignacionId = ? AND a.Activo = 1
            """, (int(asignacion_id),))
            
            asig = cursor.fetchone()
            if not asig:
                return {'success': False, 'message': 'Asignación no encontrada'}
            
            producto_id = asig[0]
            oficina_id = asig[1]
            estado_actual = asig[2]
            usuario_nombre = asig[3]
            usuario_email = asig[4]
            producto_nombre = asig[5]
            stock_actual = asig[6]
            
            cant_dev = int(cantidad_devolver)
            
            if cant_dev <= 0:
                return {'success': False, 'message': 'La cantidad debe ser mayor a 0'}
            
            if estado_actual == 'DEVUELTO':
                return {'success': False, 'message': 'Esta asignación ya fue devuelta'}
            
            # 2. Incrementar stock del producto
            cursor.execute("""
                UPDATE ProductosCorporativos
                SET CantidadDisponible = CantidadDisponible + ?
                WHERE ProductoId = ?
            """, (cant_dev, int(producto_id)))
            
            # 3. Actualizar estado de la asignación
            cursor.execute("""
                UPDATE Asignaciones
                SET Estado = 'DEVUELTO',
                    FechaDevolucion = GETDATE(),
                    MotivoDevolucion = ?,
                    ObservacionesDevolucion = ?
                WHERE AsignacionId = ?
            """, (motivo, observaciones or '', int(asignacion_id)))
            
            # 4. Registrar en historial
            cursor.execute("""
                INSERT INTO AsignacionesCorporativasHistorial
                    (ProductoId, OficinaId, Accion, Cantidad, UsuarioAccion, 
                     Fecha, UsuarioAsignadoNombre, UsuarioAsignadoEmail, Observaciones)
                VALUES (?, ?, 'DEVOLVER', ?, ?, GETDATE(), ?, ?, ?)
            """, (
                int(producto_id),
                int(oficina_id),
                cant_dev,
                usuario_accion,
                usuario_nombre,
                usuario_email,
                f'Motivo: {motivo}. {observaciones}'
            ))
            
            conn.commit()
            
            return {
                'success': True,
                'message': 'Devolución procesada correctamente',
                'producto_nombre': producto_nombre,
                'cantidad_devuelta': cant_dev,
                'nuevo_stock': stock_actual + cant_dev
            }
            
        except Exception as e:
            logger.error(f"Error devolver_producto: {e}")
            try:
                if conn: conn.rollback()
            except:
                pass
            return {'success': False, 'message': f'Error al procesar devolución: {str(e)}'}
        finally:
            if cursor: cursor.close()
            if conn: conn.close()
    
    @staticmethod
    def obtener_asignaciones_para_devolver(producto_id=None):
        """
        Obtiene las asignaciones activas que pueden ser devueltas.
        
        Args:
            producto_id: ID del producto (opcional, filtra por producto)
            
        Returns:
            list: Lista de asignaciones disponibles para devolución
        """
        conn = get_database_connection()
        if not conn:
            return []
        
        cursor = None
        try:
            cursor = conn.cursor()
            
            query = """
                SELECT 
                    a.AsignacionId,
                    a.ProductoId,
                    p.CodigoUnico,
                    p.NombreProducto,
                    c.NombreCategoria AS Categoria,
                    a.OficinaId,
                    o.NombreOficina AS Oficina,
                    a.UsuarioADNombre,
                    a.UsuarioADEmail,
                    a.FechaAsignacion,
                    a.Estado,
                    a.UsuarioAsignador
                FROM Asignaciones a
                INNER JOIN ProductosCorporativos p ON a.ProductoId = p.ProductoId
                INNER JOIN CategoriasProductos c ON p.CategoriaId = c.CategoriaId
                INNER JOIN Oficinas o ON a.OficinaId = o.OficinaId
                WHERE a.Activo = 1 
                    AND a.Estado IN ('ASIGNADO', 'CONFIRMADO')
            """
            
            if producto_id:
                query += " AND a.ProductoId = ?"
                cursor.execute(query + " ORDER BY a.FechaAsignacion DESC", (int(producto_id),))
            else:
                cursor.execute(query + " ORDER BY a.FechaAsignacion DESC")
            
            cols = [c[0] for c in cursor.description]
            return [dict(zip(cols, r)) for r in cursor.fetchall()]
            
        except Exception as e:
            logger.error(f"Error obtener_asignaciones_para_devolver: {e}")
            return []
        finally:
            if cursor: cursor.close()
            if conn: conn.close()
    
    # ========================================================================
    # NUEVAS FUNCIONES: TRASPASOS ENTRE OFICINAS
    # ========================================================================
    
    @staticmethod
    def traspasar_producto(producto_id, oficina_origen_id, oficina_destino_id, 
                          cantidad, usuario_accion, observaciones=''):
        """
        Traspasa productos de una oficina a otra.
        
        Args:
            producto_id: ID del producto a traspasar
            oficina_origen_id: ID de la oficina origen
            oficina_destino_id: ID de la oficina destino
            cantidad: Cantidad a traspasar
            usuario_accion: Usuario que realiza el traspaso
            observaciones: Observaciones del traspaso (opcional)
            
        Returns:
            dict: Resultado con 'success' y 'message'
        """
        conn = get_database_connection()
        if not conn:
            return {'success': False, 'message': 'Error de conexión a la base de datos'}
        
        cursor = None
        try:
            cursor = conn.cursor()
            
            # Validaciones
            if oficina_origen_id == oficina_destino_id:
                return {'success': False, 'message': 'La oficina origen y destino deben ser diferentes'}
            
            cant = int(cantidad)
            if cant <= 0:
                return {'success': False, 'message': 'La cantidad debe ser mayor a 0'}
            
            # 1. Verificar stock disponible del producto
            cursor.execute("""
                SELECT NombreProducto, CantidadDisponible 
                FROM ProductosCorporativos 
                WHERE ProductoId = ? AND Activo = 1
            """, (int(producto_id),))
            
            producto = cursor.fetchone()
            if not producto:
                return {'success': False, 'message': 'Producto no encontrado'}
            
            producto_nombre = producto[0]
            stock_disponible = int(producto[1])
            
            if cant > stock_disponible:
                return {'success': False, 'message': f'Stock insuficiente. Disponible: {stock_disponible}'}
            
            # 2. Obtener nombres de oficinas
            cursor.execute("SELECT NombreOficina FROM Oficinas WHERE OficinaId = ?", (int(oficina_origen_id),))
            oficina_origen = cursor.fetchone()
            if not oficina_origen:
                return {'success': False, 'message': 'Oficina origen no encontrada'}
            
            cursor.execute("SELECT NombreOficina FROM Oficinas WHERE OficinaId = ?", (int(oficina_destino_id),))
            oficina_destino = cursor.fetchone()
            if not oficina_destino:
                return {'success': False, 'message': 'Oficina destino no encontrada'}
            
            oficina_origen_nombre = oficina_origen[0]
            oficina_destino_nombre = oficina_destino[0]
            
            # 3. Registrar traspaso en historial (ORIGEN)
            cursor.execute("""
                INSERT INTO AsignacionesCorporativasHistorial
                    (ProductoId, OficinaId, Accion, Cantidad, UsuarioAccion, 
                     Fecha, Observaciones)
                VALUES (?, ?, 'TRASPASO_SALIDA', ?, ?, GETDATE(), ?)
            """, (
                int(producto_id),
                int(oficina_origen_id),
                cant,
                usuario_accion,
                f'Traspaso a: {oficina_destino_nombre}. {observaciones}'
            ))
            
            # 4. Registrar traspaso en historial (DESTINO)
            cursor.execute("""
                INSERT INTO AsignacionesCorporativasHistorial
                    (ProductoId, OficinaId, Accion, Cantidad, UsuarioAccion, 
                     Fecha, Observaciones)
                VALUES (?, ?, 'TRASPASO_ENTRADA', ?, ?, GETDATE(), ?)
            """, (
                int(producto_id),
                int(oficina_destino_id),
                cant,
                usuario_accion,
                f'Traspaso desde: {oficina_origen_nombre}. {observaciones}'
            ))
            
            # 5. Crear asignación en oficina destino
            # Buscar un usuario válido para la asignación
            cursor.execute(
                "SELECT TOP 1 UsuarioId FROM Usuarios WHERE Activo = 1 ORDER BY UsuarioId"
            )
            usuario_row = cursor.fetchone()
            if not usuario_row:
                return {'success': False, 'message': 'No hay usuarios activos en el sistema'}
            
            usuario_sistema_id = usuario_row[0]
            
            cursor.execute("""
                INSERT INTO Asignaciones 
                (ProductoId, OficinaId, UsuarioAsignadoId, FechaAsignacion, 
                 Estado, UsuarioAsignador, Activo)
                VALUES (?, ?, ?, GETDATE(), 'TRASPASADO', ?, 1)
            """, (
                int(producto_id),
                int(oficina_destino_id),
                usuario_sistema_id,
                usuario_accion
            ))
            
            conn.commit()
            
            return {
                'success': True,
                'message': 'Traspaso realizado correctamente',
                'producto_nombre': producto_nombre,
                'cantidad': cant,
                'oficina_origen': oficina_origen_nombre,
                'oficina_destino': oficina_destino_nombre
            }
            
        except Exception as e:
            logger.error(f"Error traspasar_producto: {e}")
            try:
                if conn: conn.rollback()
            except:
                pass
            return {'success': False, 'message': f'Error al procesar traspaso: {str(e)}'}
        finally:
            if cursor: cursor.close()
            if conn: conn.close()
    
    @staticmethod
    def obtener_productos_para_traspaso(oficina_id=None):
        """
        Obtiene productos disponibles para traspaso.
        
        Args:
            oficina_id: ID de la oficina (opcional, filtra por oficina)
            
        Returns:
            list: Lista de productos disponibles
        """
        conn = get_database_connection()
        if not conn:
            return []
        
        cursor = None
        try:
            cursor = conn.cursor()
            
            query = """
                SELECT 
                    p.ProductoId,
                    p.CodigoUnico,
                    p.NombreProducto,
                    c.NombreCategoria AS Categoria,
                    p.CantidadDisponible,
                    p.CantidadMinima,
                    p.ValorUnitario
                FROM ProductosCorporativos p
                INNER JOIN CategoriasProductos c ON p.CategoriaId = c.CategoriaId
                WHERE p.Activo = 1 AND p.CantidadDisponible > 0
            """
            
            if oficina_id:
                # Si se especifica oficina, filtrar por productos asignados a esa oficina
                query += """
                    AND EXISTS (
                        SELECT 1 FROM Asignaciones a 
                        WHERE a.ProductoId = p.ProductoId 
                        AND a.OficinaId = ? 
                        AND a.Activo = 1
                    )
                """
                cursor.execute(query + " ORDER BY p.NombreProducto", (int(oficina_id),))
            else:
                cursor.execute(query + " ORDER BY p.NombreProducto")
            
            cols = [c[0] for c in cursor.description]
            return [dict(zip(cols, r)) for r in cursor.fetchall()]
            
        except Exception as e:
            logger.error(f"Error obtener_productos_para_traspaso: {e}")
            return []
        finally:
            if cursor: cursor.close()
            if conn: conn.close()
    
    # ========================================================================
    # FUNCIONES EXISTENTES (mantener sin cambios)
    # ========================================================================
    
    @staticmethod
    def asignar_a_usuario_ad_con_confirmacion(producto_id, oficina_id, cantidad, 
                                               usuario_ad_info, usuario_accion):
        """
        Asigna un producto a un usuario del Active Directory y genera token de confirmación.
        
        Args:
            producto_id: ID del producto a asignar
            oficina_id: ID de la oficina destino
            cantidad: Cantidad a asignar
            usuario_ad_info: Diccionario con información del usuario AD
                - username: Nombre de usuario AD
                - full_name: Nombre completo
                - email: Correo electrónico
                - department: Departamento
            usuario_accion: Usuario que realiza la acción
            
        Returns:
            dict: Resultado de la operación con 'success', 'message', 'token', 'asignacion_id'
        """
        conn = get_database_connection()
        if not conn:
            return {'success': False, 'message': 'Error de conexión a la base de datos'}
        
        cursor = None
        try:
            cursor = conn.cursor()
            
            # 1. Verificar stock disponible
            cursor.execute(
                "SELECT CantidadDisponible, NombreProducto FROM ProductosCorporativos "
                "WHERE ProductoId = ? AND Activo = 1",
                (int(producto_id),)
            )
            row = cursor.fetchone()
            if not row:
                return {'success': False, 'message': 'Producto no encontrado'}
            
            stock = int(row[0])
            nombre_producto = row[1]
            cant = int(cantidad)
            
            if cant <= 0:
                return {'success': False, 'message': 'La cantidad debe ser mayor a 0'}
            
            if cant > stock:
                return {'success': False, 'message': f'Stock insuficiente. Disponible: {stock}'}
            
            # 2. Buscar o crear usuario en la base de datos local
            usuario_asignado_id = InventarioCorporativoModelExtended._obtener_o_crear_usuario_ad(
                cursor, usuario_ad_info
            )
            
            if not usuario_asignado_id:
                return {'success': False, 'message': 'Error al procesar el usuario asignado'}
            
            # 3. Descontar stock
            cursor.execute("""
                UPDATE ProductosCorporativos
                SET CantidadDisponible = CantidadDisponible - ?
                WHERE ProductoId = ?
            """, (cant, int(producto_id)))
            
            # 4. Crear registro en tabla Asignaciones con usuario AD
            cursor.execute("""
                INSERT INTO Asignaciones 
                (ProductoId, OficinaId, UsuarioAsignadoId, FechaAsignacion, 
                 Estado, UsuarioAsignador, Activo, UsuarioADNombre, UsuarioADEmail)
                OUTPUT INSERTED.AsignacionId
                VALUES (?, ?, ?, GETDATE(), 'ASIGNADO', ?, 1, ?, ?)
            """, (
                int(producto_id), 
                int(oficina_id), 
                usuario_asignado_id,
                usuario_accion,
                usuario_ad_info.get('full_name', usuario_ad_info.get('username', '')),
                usuario_ad_info.get('email', '')
            ))
            
            # Obtener el ID de la asignación recién creada
            asignacion_result = cursor.fetchone()
            if not asignacion_result:
                conn.rollback()
                return {'success': False, 'message': 'Error al crear la asignación'}
            
            asignacion_id = asignacion_result[0]
            
            # 5. Registrar en historial
            cursor.execute("""
                INSERT INTO AsignacionesCorporativasHistorial
                    (ProductoId, OficinaId, Accion, Cantidad, UsuarioAccion, 
                     Fecha, UsuarioAsignadoNombre, UsuarioAsignadoEmail)
                VALUES (?, ?, 'ASIGNAR', ?, ?, GETDATE(), ?, ?)
            """, (
                int(producto_id), 
                int(oficina_id), 
                cant, 
                usuario_accion,
                usuario_ad_info.get('full_name', usuario_ad_info.get('username', '')),
                usuario_ad_info.get('email', '')
            ))
            
            # 6. Generar token de confirmación
            import secrets
            from datetime import datetime, timedelta
            
            token = secrets.token_urlsafe(32)
            fecha_expiracion = datetime.now() + timedelta(days=7)  # Token válido por 7 días
            
            cursor.execute("""
                INSERT INTO TokensConfirmacionAsignacion 
                (AsignacionId, Token, FechaCreacion, FechaExpiracion, Utilizado)
                VALUES (?, ?, GETDATE(), ?, 0)
            """, (asignacion_id, token, fecha_expiracion))
            
            conn.commit()
            
            return {
                'success': True, 
                'message': 'Producto asignado correctamente. Se envió email con enlace de confirmación.',
                'usuario_email': usuario_ad_info.get('email'),
                'usuario_nombre': usuario_ad_info.get('full_name'),
                'producto_nombre': nombre_producto,
                'token': token,
                'asignacion_id': asignacion_id
            }
            
        except Exception as e:
            logger.error(f"Error asignar_a_usuario_ad_con_confirmacion: {e}")
            try:
                if conn: conn.rollback()
            except:
                pass
            return {'success': False, 'message': f'Error al asignar: {str(e)}'}
        finally:
            if cursor: cursor.close()
            if conn: conn.close()
    
    @staticmethod
    def obtener_asignaciones_con_confirmacion(producto_id=None):
        """
        Obtiene asignaciones con su estado de confirmación.
        
        Args:
            producto_id: ID del producto (opcional)
            
        Returns:
            list: Lista de asignaciones con información de confirmación
        """
        conn = get_database_connection()
        if not conn:
            return []
        
        cursor = None
        try:
            cursor = conn.cursor()
            
            query = """
                SELECT 
                    a.AsignacionId,
                    a.ProductoId,
                    p.CodigoUnico,
                    p.NombreProducto,
                    c.NombreCategoria AS categoria,
                    a.OficinaId,
                    o.NombreOficina AS oficina,
                    a.FechaAsignacion,
                    a.Estado,
                    a.FechaConfirmacion,
                    a.UsuarioConfirmacion,
                    a.UsuarioAsignador,
                    a.UsuarioADNombre,
                    a.UsuarioADEmail,
                    CASE 
                        WHEN t.Utilizado = 1 THEN 'CONFIRMADO'
                        WHEN t.FechaExpiracion < GETDATE() THEN 'EXPIRADO'
                        WHEN t.TokenId IS NOT NULL THEN 'PENDIENTE'
                        ELSE 'SIN_TOKEN'
                    END AS EstadoConfirmacion,
                    t.FechaExpiracion,
                    DATEDIFF(day, GETDATE(), t.FechaExpiracion) AS DiasRestantes
                FROM Asignaciones a
                INNER JOIN ProductosCorporativos p ON a.ProductoId = p.ProductoId
                INNER JOIN CategoriasProductos c ON p.CategoriaId = c.CategoriaId
                INNER JOIN Oficinas o ON a.OficinaId = o.OficinaId
                LEFT JOIN TokensConfirmacionAsignacion t ON a.AsignacionId = t.AsignacionId
                WHERE a.Activo = 1
            """
            
            if producto_id:
                query += " AND a.ProductoId = ?"
                cursor.execute(query + " ORDER BY a.FechaAsignacion DESC", (int(producto_id),))
            else:
                cursor.execute(query + " ORDER BY a.FechaAsignacion DESC")
            
            cols = [c[0] for c in cursor.description]
            return [dict(zip(cols, r)) for r in cursor.fetchall()]
            
        except Exception as e:
            logger.error(f"Error obteniendo asignaciones con confirmación: {e}")
            return []
        finally:
            if cursor: cursor.close()
            if conn: conn.close()
    
    @staticmethod
    def _obtener_o_crear_usuario_ad(cursor, usuario_ad_info):
        """
        Obtiene el ID del usuario en la base de datos local o lo crea si no existe.
        
        Args:
            cursor: Cursor de la base de datos
            usuario_ad_info: Información del usuario AD
            
        Returns:
            int: ID del usuario o None si falla
        """
        try:
            username = usuario_ad_info.get('username', '')
            
            # Buscar usuario existente por nombre de usuario AD
            cursor.execute(
                "SELECT UsuarioId FROM Usuarios WHERE UsuarioAD = ? AND Activo = 1",
                (username,)
            )
            row = cursor.fetchone()
            
            if row:
                return row[0]
            
            # Si no existe, buscar por email
            email = usuario_ad_info.get('email', '')
            if email:
                cursor.execute(
                    "SELECT UsuarioId FROM Usuarios WHERE CorreoElectronico = ? AND Activo = 1",
                    (email,)
                )
                row = cursor.fetchone()
                if row:
                    # Actualizar el UsuarioAD
                    cursor.execute(
                        "UPDATE Usuarios SET UsuarioAD = ? WHERE UsuarioId = ?",
                        (username, row[0])
                    )
                    return row[0]
            
            # Si no existe, crear nuevo usuario
            cursor.execute("""
                INSERT INTO Usuarios 
                (NombreUsuario, NombreCompleto, Email, UsuarioAD, Rol, Activo, FechaCreacion)
                OUTPUT INSERTED.UsuarioId
                VALUES (?, ?, ?, ?, 'usuario', 1, GETDATE())
            """, (
                username,
                usuario_ad_info.get('full_name', username),
                email,
                username
            ))
            
            new_id = cursor.fetchone()
            return new_id[0] if new_id else None
            
        except Exception as e:
            logger.error(f"Error obteniendo/creando usuario AD: {e}")
            # Si falla, retornar el primer usuario activo como fallback
            cursor.execute(
                "SELECT TOP 1 UsuarioId FROM Usuarios WHERE Activo = 1 ORDER BY UsuarioId"
            )
            row = cursor.fetchone()
            return row[0] if row else None
    
    @staticmethod
    def obtener_asignaciones_por_usuario(usuario_ad_nombre):
        """
        Obtiene todas las asignaciones de un usuario específico del AD.
        
        Args:
            usuario_ad_nombre: Nombre del usuario en AD
            
        Returns:
            list: Lista de asignaciones
        """
        conn = get_database_connection()
        if not conn:
            return []
        
        cursor = None
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    a.AsignacionId,
                    p.ProductoId,
                    p.CodigoUnico,
                    p.NombreProducto,
                    c.NombreCategoria AS categoria,
                    o.NombreOficina AS oficina,
                    a.FechaAsignacion,
                    a.Estado,
                    a.UsuarioAsignador,
                    a.UsuarioADNombre,
                    a.UsuarioADEmail
                FROM Asignaciones a
                INNER JOIN ProductosCorporativos p ON a.ProductoId = p.ProductoId
                INNER JOIN CategoriasProductos c ON p.CategoriaId = c.CategoriaId
                INNER JOIN Oficinas o ON a.OficinaId = o.OficinaId
                WHERE a.UsuarioADNombre LIKE ? AND a.Activo = 1
                ORDER BY a.FechaAsignacion DESC
            """, (f'%{usuario_ad_nombre}%',))
            
            cols = [c[0] for c in cursor.description]
            return [dict(zip(cols, r)) for r in cursor.fetchall()]
            
        except Exception as e:
            logger.error(f"Error obteniendo asignaciones por usuario: {e}")
            return []
        finally:
            if cursor: cursor.close()
            if conn: conn.close()
    
    @staticmethod
    def historial_asignaciones_extendido(producto_id):
        """
        Obtiene el historial de asignaciones con información extendida del usuario AD.
        
        Args:
            producto_id: ID del producto
            
        Returns:
            list: Lista de movimientos del historial
        """
        conn = get_database_connection()
        if not conn:
            return []
        
        cursor = None
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    h.HistorialId,
                    h.ProductoId,
                    h.OficinaId,
                    o.NombreOficina AS oficina,
                    h.Accion,
                    h.Cantidad,
                    h.UsuarioAccion,
                    h.Fecha,
                    h.UsuarioAsignadoNombre,
                    h.UsuarioAsignadoEmail,
                    h.Observaciones
                FROM AsignacionesCorporativasHistorial h
                LEFT JOIN Oficinas o ON o.OficinaId = h.OficinaId
                WHERE h.ProductoId = ?
                ORDER BY h.Fecha DESC
            """, (int(producto_id),))
            
            cols = [c[0] for c in cursor.description]
            return [dict(zip(cols, r)) for r in cursor.fetchall()]
            
        except Exception as e:
            logger.error(f"Error historial_asignaciones_extendido: {e}")
            return []
        finally:
            if cursor: cursor.close()
            if conn: conn.close()