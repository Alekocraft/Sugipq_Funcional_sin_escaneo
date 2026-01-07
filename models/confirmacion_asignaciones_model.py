"""
Modelo para gestionar confirmaciones de asignaciones con tokens temporales.
Incluye generación de tokens, validación y registro de confirmaciones.
MODIFICADO: Incluye campo de número de identificación (cédula)
"""
from database import get_database_connection
import logging
import secrets
import hashlib
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class ConfirmacionAsignacionesModel:
    """
    Modelo para gestionar confirmaciones de asignaciones de inventario.
    """
    
    @staticmethod
    def generar_token_confirmacion(asignacion_id, usuario_ad_email, dias_validez=8):
        """
        Genera un token único para confirmar una asignación.
        
        Args:
            asignacion_id: ID de la asignación
            usuario_ad_email: Email del usuario asignado
            dias_validez: Días de validez del token (default: 8)
            
        Returns:
            str: Token generado o None si hay error
        """
        conn = get_database_connection()
        if not conn:
            logger.error("Error de conexión a la base de datos")
            return None
        
        cursor = None
        try:
            cursor = conn.cursor()
            
            # Generar token único y seguro
            token_raw = secrets.token_urlsafe(32)
            token_hash = hashlib.sha256(token_raw.encode()).hexdigest()
            
            # Calcular fecha de expiración
            fecha_expiracion = datetime.now() + timedelta(days=dias_validez)
            
            # Eliminar tokens anteriores de esta asignación
            cursor.execute("""
                DELETE FROM TokensConfirmacionAsignacion 
                WHERE AsignacionId = ?
            """, (asignacion_id,))
            
            # Insertar nuevo token
            cursor.execute("""
                INSERT INTO TokensConfirmacionAsignacion 
                (AsignacionId, Token, TokenHash, UsuarioEmail, FechaExpiracion, Utilizado, FechaCreacion)
                VALUES (?, ?, ?, ?, ?, 0, GETDATE())
            """, (asignacion_id, token_raw, token_hash, usuario_ad_email, fecha_expiracion))
            
            conn.commit()
            logger.info(f"Token generado para asignación {asignacion_id}")
            
            return token_raw
            
        except Exception as e:
            logger.error(f"Error generando token: {e}")
            if conn:
                try:
                    conn.rollback()
                except:
                    pass
            return None
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
    
    @staticmethod
    def validar_token(token):
        """
        Valida un token de confirmación.
        
        Args:
            token: Token a validar
            
        Returns:
            dict: Información del token o None si es inválido
                - asignacion_id
                - usuario_email
                - producto_nombre
                - cantidad
                - oficina
                - fecha_asignacion
                - es_valido
                - mensaje_error
        """
        conn = get_database_connection()
        if not conn:
            return {'es_valido': False, 'mensaje_error': 'Error de conexión a la base de datos'}
        
        cursor = None
        try:
            cursor = conn.cursor()
            token_hash = hashlib.sha256(token.encode()).hexdigest()
            
            # Buscar token
            cursor.execute("""
                SELECT 
                    t.TokenId,
                    t.AsignacionId,
                    t.UsuarioEmail,
                    t.FechaExpiracion,
                    t.Utilizado,
                    t.FechaUtilizacion,
                    a.ProductoId,
                    a.OficinaId,
                    a.FechaAsignacion,
                    a.UsuarioADNombre,
                    a.Estado,
                    p.NombreProducto,
                    p.CodigoUnico,
                    o.NombreOficina,
                    c.NombreCategoria
                FROM TokensConfirmacionAsignacion t
                INNER JOIN Asignaciones a ON t.AsignacionId = a.AsignacionId
                INNER JOIN ProductosCorporativos p ON a.ProductoId = p.ProductoId
                INNER JOIN Oficinas o ON a.OficinaId = o.OficinaId
                LEFT JOIN CategoriasProductos c ON p.CategoriaId = c.CategoriaId
                WHERE t.TokenHash = ? AND a.Activo = 1
            """, (token_hash,))
            
            row = cursor.fetchone()
            
            if not row:
                return {'es_valido': False, 'mensaje_error': 'Token no válido o asignación no encontrada'}
            
            token_id = row[0]
            asignacion_id = row[1]
            usuario_email = row[2]
            fecha_expiracion = row[3]
            utilizado = row[4]
            fecha_utilizacion = row[5]
            producto_id = row[6]
            oficina_id = row[7]
            fecha_asignacion = row[8]
            usuario_nombre = row[9]
            estado = row[10]
            producto_nombre = row[11]
            codigo_unico = row[12]
            oficina_nombre = row[13]
            categoria = row[14]
            
            # Validar si ya fue utilizado
            if utilizado:
                return {
                    'es_valido': False,
                    'mensaje_error': f'Este token ya fue utilizado el {fecha_utilizacion.strftime("%d/%m/%Y %H:%M")}',
                    'ya_confirmado': True
                }
            
            # Validar fecha de expiración
            if datetime.now() > fecha_expiracion:
                return {
                    'es_valido': False,
                    'mensaje_error': f'Token expirado. Venció el {fecha_expiracion.strftime("%d/%m/%Y %H:%M")}',
                    'expirado': True
                }
            
            # Token válido
            return {
                'es_valido': True,
                'token_id': token_id,
                'asignacion_id': asignacion_id,
                'producto_id': producto_id,
                'producto_nombre': producto_nombre,
                'codigo_unico': codigo_unico,
                'categoria': categoria,
                'oficina_id': oficina_id,
                'oficina_nombre': oficina_nombre,
                'usuario_email': usuario_email,
                'usuario_nombre': usuario_nombre,
                'fecha_asignacion': fecha_asignacion,
                'fecha_expiracion': fecha_expiracion,
                'estado': estado,
                'dias_restantes': (fecha_expiracion - datetime.now()).days
            }
            
        except Exception as e:
            logger.error(f"Error validando token: {e}")
            return {'es_valido': False, 'mensaje_error': f'Error al validar token: {str(e)}'}
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
    
    @staticmethod
    def confirmar_asignacion(token, usuario_ad_username, numero_identificacion, direccion_ip=None, user_agent=None):
        """
        Confirma una asignación y marca el token como utilizado.
        
        Args:
            token: Token de confirmación
            usuario_ad_username: Username del usuario que confirma
            numero_identificacion: Número de cédula o identificación del usuario
            direccion_ip: IP del usuario (opcional)
            user_agent: User agent del navegador (opcional)
            
        Returns:
            dict: Resultado de la operación
        """
        conn = get_database_connection()
        if not conn:
            return {'success': False, 'message': 'Error de conexión a la base de datos'}
        
        cursor = None
        try:
            cursor = conn.cursor()
            
            # Validar token primero
            validacion = ConfirmacionAsignacionesModel.validar_token(token)
            if not validacion.get('es_valido'):
                return {'success': False, 'message': validacion.get('mensaje_error', 'Token inválido')}
            
            token_id = validacion['token_id']
            asignacion_id = validacion['asignacion_id']
            token_hash = hashlib.sha256(token.encode()).hexdigest()
            
            # Validar número de identificación
            if not numero_identificacion or not numero_identificacion.strip():
                return {'success': False, 'message': 'El número de identificación es obligatorio'}
            
            # Limpiar y validar formato del número de identificación
            numero_identificacion = numero_identificacion.strip()
            if not numero_identificacion.isdigit():
                return {'success': False, 'message': 'El número de identificación debe contener solo números'}
            
            if len(numero_identificacion) < 6 or len(numero_identificacion) > 20:
                return {'success': False, 'message': 'El número de identificación debe tener entre 6 y 20 dígitos'}
            
            # Marcar token como utilizado e incluir número de identificación
            cursor.execute("""
                UPDATE TokensConfirmacionAsignacion
                SET Utilizado = 1,
                    FechaUtilizacion = GETDATE(),
                    UsuarioConfirmacion = ?,
                    NumeroIdentificacion = ?,
                    DireccionIP = ?,
                    UserAgent = ?
                WHERE TokenHash = ?
            """, (usuario_ad_username, numero_identificacion, direccion_ip, user_agent, token_hash))
            
            # Actualizar estado de la asignación
            cursor.execute("""
                UPDATE Asignaciones
                SET Estado = 'CONFIRMADO',
                    FechaConfirmacion = GETDATE(),
                    UsuarioConfirmacion = ?
                WHERE AsignacionId = ?
            """, (usuario_ad_username, asignacion_id))
            
            # Registrar en historial
            cursor.execute("""
                INSERT INTO AsignacionesCorporativasHistorial
                (ProductoId, OficinaId, Accion, Cantidad, UsuarioAccion, Fecha, 
                 UsuarioAsignadoNombre, UsuarioAsignadoEmail, Observaciones)
                VALUES (?, ?, 'CONFIRMACION', 1, ?, GETDATE(), ?, ?, ?)
            """, (
                validacion['producto_id'],
                validacion['oficina_id'],
                usuario_ad_username,
                validacion['usuario_nombre'],
                validacion['usuario_email'],
                f"Confirmación realizada desde IP: {direccion_ip or 'N/A'}. Cédula: {numero_identificacion}"
            ))
            
            conn.commit()
            
            logger.info(f"Asignación {asignacion_id} confirmada por {usuario_ad_username} (CC: {numero_identificacion})")
            
            return {
                'success': True,
                'message': 'Asignación confirmada exitosamente',
                'asignacion_id': asignacion_id,
                'producto_nombre': validacion['producto_nombre'],
                'oficina_nombre': validacion['oficina_nombre']
            }
            
        except Exception as e:
            logger.error(f"Error confirmando asignación: {e}")
            if conn:
                try:
                    conn.rollback()
                except:
                    pass
            return {'success': False, 'message': f'Error al confirmar: {str(e)}'}
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
    
    @staticmethod
    def obtener_confirmaciones_pendientes(usuario_email=None):
        """
        Obtiene asignaciones pendientes de confirmación.
        
        Args:
            usuario_email: Email del usuario (opcional, para filtrar)
            
        Returns:
            list: Lista de asignaciones pendientes
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
                    p.NombreProducto,
                    p.CodigoUnico,
                    o.NombreOficina,
                    a.FechaAsignacion,
                    a.UsuarioADNombre,
                    a.UsuarioADEmail,
                    t.FechaExpiracion,
                    t.Utilizado,
                    DATEDIFF(day, GETDATE(), t.FechaExpiracion) AS DiasRestantes
                FROM Asignaciones a
                INNER JOIN TokensConfirmacionAsignacion t ON a.AsignacionId = t.AsignacionId
                INNER JOIN ProductosCorporativos p ON a.ProductoId = p.ProductoId
                INNER JOIN Oficinas o ON a.OficinaId = o.OficinaId
                WHERE a.Estado = 'ASIGNADO' 
                    AND a.Activo = 1
                    AND t.Utilizado = 0
                    AND t.FechaExpiracion > GETDATE()
            """
            
            if usuario_email:
                query += " AND a.UsuarioADEmail = ?"
                cursor.execute(query, (usuario_email,))
            else:
                cursor.execute(query)
            
            cols = [c[0] for c in cursor.description]
            return [dict(zip(cols, row)) for row in cursor.fetchall()]
            
        except Exception as e:
            logger.error(f"Error obteniendo confirmaciones pendientes: {e}")
            return []
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
    
    @staticmethod
    def limpiar_tokens_expirados():
        """
        Elimina tokens expirados de la base de datos (tarea de mantenimiento).
        
        Returns:
            int: Número de tokens eliminados
        """
        conn = get_database_connection()
        if not conn:
            return 0
        
        cursor = None
        try:
            cursor = conn.cursor()
            
            cursor.execute("""
                DELETE FROM TokensConfirmacionAsignacion
                WHERE FechaExpiracion < DATEADD(day, -30, GETDATE())
            """)
            
            eliminados = cursor.rowcount
            conn.commit()
            
            logger.info(f"Tokens expirados eliminados: {eliminados}")
            return eliminados
            
        except Exception as e:
            logger.error(f"Error limpiando tokens expirados: {e}")
            if conn:
                try:
                    conn.rollback()
                except:
                    pass
            return 0
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
    
    @staticmethod
    def obtener_estadisticas_confirmaciones():
        """
        Obtiene estadísticas generales de confirmaciones.
        
        Returns:
            dict: Diccionario con estadísticas
        """
        conn = get_database_connection()
        if not conn:
            return {}
        
        cursor = None
        try:
            cursor = conn.cursor()
            
            estadisticas = {}
            
            # Total de tokens generados
            cursor.execute("""
                SELECT COUNT(*) FROM TokensConfirmacionAsignacion
            """)
            estadisticas['total_tokens_generados'] = cursor.fetchone()[0] or 0
            
            # Tokens utilizados
            cursor.execute("""
                SELECT COUNT(*) FROM TokensConfirmacionAsignacion WHERE Utilizado = 1
            """)
            estadisticas['tokens_utilizados'] = cursor.fetchone()[0] or 0
            
            # Tokens pendientes (no expirados)
            cursor.execute("""
                SELECT COUNT(*) FROM TokensConfirmacionAsignacion 
                WHERE Utilizado = 0 AND FechaExpiracion > GETDATE()
            """)
            estadisticas['tokens_pendientes'] = cursor.fetchone()[0] or 0
            
            # Tokens expirados
            cursor.execute("""
                SELECT COUNT(*) FROM TokensConfirmacionAsignacion 
                WHERE Utilizado = 0 AND FechaExpiracion <= GETDATE()
            """)
            estadisticas['tokens_expirados'] = cursor.fetchone()[0] or 0
            
            # Confirmaciones por mes (últimos 6 meses)
            cursor.execute("""
                SELECT 
                    FORMAT(FechaUtilizacion, 'yyyy-MM') AS Mes,
                    COUNT(*) AS Confirmaciones
                FROM TokensConfirmacionAsignacion 
                WHERE Utilizado = 1 
                    AND FechaUtilizacion >= DATEADD(month, -6, GETDATE())
                GROUP BY FORMAT(FechaUtilizacion, 'yyyy-MM')
                ORDER BY Mes DESC
            """)
            
            estadisticas['confirmaciones_por_mes'] = [
                {'mes': row[0], 'cantidad': row[1]} 
                for row in cursor.fetchall()
            ]
            
            return estadisticas
            
        except Exception as e:
            logger.error(f"Error obteniendo estadísticas: {e}")
            return {}
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()