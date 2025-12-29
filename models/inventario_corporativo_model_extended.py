# models/inventario_corporativo_model_extended.py
"""
Extensiones al modelo de inventario corporativo para soportar:
- Asignación a usuarios del Active Directory
- Búsqueda de usuarios AD
- Notificaciones por email
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
                    "SELECT UsuarioId FROM Usuarios WHERE CorreoElectronico  = ? AND Activo = 1",
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
                    h.UsuarioAsignadoEmail
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


# ============================================================================
# SQL para agregar columnas necesarias a las tablas existentes
# ============================================================================
"""
-- Ejecutar estos scripts SQL si las columnas no existen:

-- Agregar columnas a tabla Asignaciones
IF NOT EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID('Asignaciones') AND name = 'UsuarioADNombre')
BEGIN
    ALTER TABLE Asignaciones ADD UsuarioADNombre NVARCHAR(255) NULL;
END

IF NOT EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID('Asignaciones') AND name = 'UsuarioADEmail')
BEGIN
    ALTER TABLE Asignaciones ADD UsuarioADEmail NVARCHAR(255) NULL;
END

-- Agregar columnas a tabla AsignacionesCorporativasHistorial
IF NOT EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID('AsignacionesCorporativasHistorial') AND name = 'UsuarioAsignadoNombre')
BEGIN
    ALTER TABLE AsignacionesCorporativasHistorial ADD UsuarioAsignadoNombre NVARCHAR(255) NULL;
END

IF NOT EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID('AsignacionesCorporativasHistorial') AND name = 'UsuarioAsignadoEmail')
BEGIN
    ALTER TABLE AsignacionesCorporativasHistorial ADD UsuarioAsignadoEmail NVARCHAR(255) NULL;
END

-- Agregar columna UsuarioAD a tabla Usuarios si no existe
IF NOT EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID('Usuarios') AND name = 'UsuarioAD')
BEGIN
    ALTER TABLE Usuarios ADD UsuarioAD NVARCHAR(100) NULL;
END
"""
