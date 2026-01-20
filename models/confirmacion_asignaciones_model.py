"""
Modelo para gestionar confirmaciones de asignaciones con tokens temporales.
Incluye generación de tokens, validación y registro de confirmaciones.
MODIFICADO: Incluye campo de número de identificación (cédula)
CORREGIDO: Se eliminó sanitizar_email en INSERT (causaba NULL en TokenHash)
"""
from database import get_database_connection
import logging
import secrets
import hashlib
from datetime import datetime, timedelta
from utils.helpers import sanitizar_username, sanitizar_email, sanitizar_ip

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
            
            # === DEBUG LOGS ===
            logger.info(f"[DEBUG TOKEN] Generando token para asignacion_id={asignacion_id}")
            logger.info(f"[DEBUG TOKEN] token_raw generado: {token_raw[:10]}... (len={len(token_raw)})")
            logger.info(f"[DEBUG TOKEN] token_hash generado: {token_hash[:10]}... (len={len(token_hash)})")
            logger.info(f"[DEBUG TOKEN] usuario_ad_email: {usuario_ad_email}")
            
            # Validar que los valores no sean None o vacíos
            if not token_raw:
                logger.error("[DEBUG TOKEN] ERROR: token_raw es None o vacío!")
                return None
            if not token_hash:
                logger.error("[DEBUG TOKEN] ERROR: token_hash es None o vacío!")
                return None
            if not usuario_ad_email:
                logger.error("[DEBUG TOKEN] ERROR: usuario_ad_email es None o vacío!")
                return None
            
            # Calcular fecha de expiración
            fecha_expiracion = datetime.now() + timedelta(days=dias_validez)
            logger.info(f"[DEBUG TOKEN] fecha_expiracion: {fecha_expiracion}")
            
            # Eliminar tokens anteriores de esta asignación
            cursor.execute("""
                DELETE FROM TokensConfirmacionAsignacion 
                WHERE AsignacionId = ?
            """, (asignacion_id,))
            logger.info(f"[DEBUG TOKEN] Tokens anteriores eliminados")
            
            # === INSERTAR NUEVO TOKEN ===
            # IMPORTANTE: NO usar sanitizar_email aquí - esa función es SOLO para logs
            # y devuelve un email enmascarado como "jo***@gmail.com"
            logger.info(f"[DEBUG TOKEN] Ejecutando INSERT con valores:")
            logger.info(f"[DEBUG TOKEN]   - AsignacionId: {asignacion_id}")
            logger.info(f"[DEBUG TOKEN]   - Token (primeros 10): {token_raw[:10]}")
            logger.info(f"[DEBUG TOKEN]   - TokenHash (primeros 10): {token_hash[:10]}")
            logger.info(f"[DEBUG TOKEN]   - UsuarioEmail: {usuario_ad_email}")
            logger.info(f"[DEBUG TOKEN]   - FechaExpiracion: {fecha_expiracion}")
            
            cursor.execute("""
                INSERT INTO TokensConfirmacionAsignacion 
                (AsignacionId, Token, TokenHash, UsuarioEmail, FechaExpiracion, Utilizado, FechaCreacion)
                VALUES (?, ?, ?, ?, ?, 0, GETDATE())
            """, (asignacion_id, token_raw, token_hash, usuario_ad_email, fecha_expiracion))
            
            conn.commit()
            logger.info(f"[DEBUG TOKEN] INSERT exitoso! Token generado para asignación {asignacion_id}")
            return token_raw
            
        except Exception as e:
            logger.error(f"[DEBUG TOKEN] ERROR en generar_token_confirmacion: {e}")
            logger.error(f"[DEBUG TOKEN] Tipo de error: {type(e).__name__}")
            import traceback
            logger.error(f"[DEBUG TOKEN] Traceback: {traceback.format_exc()}")
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
            return {'es_valido': False, 'mensaje_error': 'Error de conexión'}
        
        cursor = None
        try:
            cursor = conn.cursor()
            
            # Calcular hash del token para buscar
            token_hash = hashlib.sha256(token.encode()).hexdigest()
            
            # Buscar token en la base de datos
            cursor.execute("""
                SELECT 
                    t.TokenId,
                    t.AsignacionId,
                    t.UsuarioEmail,
                    t.FechaExpiracion,
                    t.Utilizado,
                    t.FechaConfirmacion,
                    a.ProductoId,
                    p.NombreProducto,
                    a.OficinaId,
                    o.NombreOficina,
                    a.FechaAsignacion,
                    a.UsuarioADNombre,
                    a.UsuarioADEmail
                FROM TokensConfirmacionAsignacion t
                INNER JOIN Asignaciones a ON t.AsignacionId = a.AsignacionId
                INNER JOIN ProductosCorporativos p ON a.ProductoId = p.ProductoId
                LEFT JOIN Oficinas o ON a.OficinaId = o.OficinaId
                WHERE t.TokenHash = ?
            """, (token_hash,))
            
            row = cursor.fetchone()
            
            if not row:
                return {'es_valido': False, 'mensaje_error': 'Token no encontrado o inválido'}
            
            # Extraer datos
            token_id = row[0]
            asignacion_id = row[1]
            usuario_email = row[2]
            fecha_expiracion = row[3]
            utilizado = row[4]
            fecha_confirmacion = row[5]
            producto_id = row[6]
            producto_nombre = row[7]
            oficina_id = row[8]
            oficina_nombre = row[9]
            fecha_asignacion = row[10]
            usuario_ad_nombre = row[11]
            usuario_ad_email = row[12]
            
            # Verificar si ya fue utilizado
            if utilizado:
                return {
                    'es_valido': False, 
                    'mensaje_error': 'Este enlace ya fue utilizado',
                    'fecha_confirmacion': fecha_confirmacion
                }
            
            # Verificar expiración
            if fecha_expiracion and datetime.now() > fecha_expiracion:
                return {
                    'es_valido': False, 
                    'mensaje_error': 'El enlace ha expirado',
                    'fecha_expiracion': fecha_expiracion
                }
            
            return {
                'es_valido': True,
                'token_id': token_id,
                'asignacion_id': asignacion_id,
                'usuario_email': usuario_email,
                'producto_id': producto_id,
                'producto_nombre': producto_nombre,
                'oficina_id': oficina_id,
                'oficina_nombre': oficina_nombre,
                'fecha_asignacion': fecha_asignacion,
                'usuario_ad_nombre': usuario_ad_nombre,
                'usuario_ad_email': usuario_ad_email,
                'fecha_expiracion': fecha_expiracion
            }
            
        except Exception as e:
            logger.error(f"Error validando token: {e}")
            return {'es_valido': False, 'mensaje_error': f'Error al validar: {str(e)}'}
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
    
    @staticmethod
    def confirmar_asignacion(token, numero_identificacion=None, ip_confirmacion=None):
        """
        Confirma una asignación usando el token.
        
        Args:
            token: Token de confirmación
            numero_identificacion: Número de cédula/identificación del usuario
            ip_confirmacion: IP desde donde se confirma
            
        Returns:
            dict: Resultado de la confirmación
        """
        conn = get_database_connection()
        if not conn:
            return {'success': False, 'message': 'Error de conexión'}
        
        cursor = None
        try:
            cursor = conn.cursor()
            
            # Primero validar el token
            validacion = ConfirmacionAsignacionesModel.validar_token(token)
            
            if not validacion.get('es_valido'):
                return {
                    'success': False, 
                    'message': validacion.get('mensaje_error', 'Token inválido')
                }
            
            token_id = validacion.get('token_id')
            asignacion_id = validacion.get('asignacion_id')
            
            # Marcar token como utilizado
            cursor.execute("""
                UPDATE TokensConfirmacionAsignacion
                SET Utilizado = 1,
                    FechaConfirmacion = GETDATE(),
                    NumeroIdentificacion = ?,
                    IPConfirmacion = ?
                WHERE TokenId = ?
            """, (numero_identificacion, ip_confirmacion, token_id))
            
            # Actualizar estado de la asignación
            cursor.execute("""
                UPDATE Asignaciones
                SET Estado = 'CONFIRMADO',
                    FechaConfirmacion = GETDATE()
                WHERE AsignacionId = ?
            """, (asignacion_id,))
            
            conn.commit()
            
            logger.info(f"Asignación {asignacion_id} confirmada exitosamente")
            
            return {
                'success': True,
                'message': 'Asignación confirmada exitosamente',
                'asignacion_id': asignacion_id,
                'producto_nombre': validacion.get('producto_nombre'),
                'oficina_nombre': validacion.get('oficina_nombre')
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
        Obtiene las asignaciones pendientes de confirmación.
        
        Args:
            usuario_email: Filtrar por email de usuario (opcional)
            
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
                    t.TokenId,
                    t.AsignacionId,
                    t.UsuarioEmail,
                    t.FechaExpiracion,
                    t.FechaCreacion,
                    a.ProductoId,
                    p.NombreProducto,
                    p.CodigoUnico,
                    a.OficinaId,
                    o.NombreOficina,
                    a.FechaAsignacion,
                    a.UsuarioAsignador,
                    a.UsuarioADNombre
                FROM TokensConfirmacionAsignacion t
                INNER JOIN Asignaciones a ON t.AsignacionId = a.AsignacionId
                INNER JOIN ProductosCorporativos p ON a.ProductoId = p.ProductoId
                LEFT JOIN Oficinas o ON a.OficinaId = o.OficinaId
                WHERE t.Utilizado = 0
                  AND t.FechaExpiracion > GETDATE()
            """
            
            params = []
            if usuario_email:
                query += " AND t.UsuarioEmail = ?"
                params.append(usuario_email)
            
            query += " ORDER BY t.FechaCreacion DESC"
            
            cursor.execute(query, params)
            
            columnas = [desc[0] for desc in cursor.description]
            resultados = []
            
            for row in cursor.fetchall():
                item = dict(zip(columnas, row))
                resultados.append(item)
            
            return resultados
            
        except Exception as e:
            logger.error(f"Error obteniendo confirmaciones pendientes: {e}")
            return []
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
    
    @staticmethod
    def obtener_historial_confirmaciones(dias=30):
        """
        Obtiene el historial de confirmaciones.
        
        Args:
            dias: Número de días hacia atrás (default: 30)
            
        Returns:
            list: Lista de confirmaciones
        """
        conn = get_database_connection()
        if not conn:
            return []
        
        cursor = None
        try:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT 
                    t.TokenId,
                    t.AsignacionId,
                    t.UsuarioEmail,
                    t.FechaCreacion,
                    t.FechaConfirmacion,
                    t.Utilizado,
                    t.NumeroIdentificacion,
                    t.IPConfirmacion,
                    a.ProductoId,
                    p.NombreProducto,
                    p.CodigoUnico,
                    o.NombreOficina,
                    a.UsuarioAsignador,
                    a.UsuarioADNombre
                FROM TokensConfirmacionAsignacion t
                INNER JOIN Asignaciones a ON t.AsignacionId = a.AsignacionId
                INNER JOIN ProductosCorporativos p ON a.ProductoId = p.ProductoId
                LEFT JOIN Oficinas o ON a.OficinaId = o.OficinaId
                WHERE t.FechaCreacion >= DATEADD(day, -?, GETDATE())
                ORDER BY t.FechaCreacion DESC
            """, (dias,))
            
            columnas = [desc[0] for desc in cursor.description]
            resultados = []
            
            for row in cursor.fetchall():
                item = dict(zip(columnas, row))
                resultados.append(item)
            
            return resultados
            
        except Exception as e:
            logger.error(f"Error obteniendo historial de confirmaciones: {e}")
            return []
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
    
    @staticmethod
    def limpiar_tokens_expirados():
        """
        Elimina tokens expirados de la base de datos.
        
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
                WHERE FechaExpiracion < GETDATE()
                  AND Utilizado = 0
            """)
            
            eliminados = cursor.rowcount
            conn.commit()
            
            if eliminados > 0:
                logger.info(f"Se eliminaron {eliminados} tokens expirados")
            
            return eliminados
            
        except Exception as e:
            logger.error(f"Error limpiando tokens expirados: {e}")
            return 0
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    @staticmethod
    def reenviar_token(asignacion_id, usuario_ad_email):
        """
        Genera un nuevo token para una asignación existente.
        
        Args:
            asignacion_id: ID de la asignación
            usuario_ad_email: Email del usuario
            
        Returns:
            str: Nuevo token o None si hay error
        """
        return ConfirmacionAsignacionesModel.generar_token_confirmacion(
            asignacion_id=asignacion_id,
            usuario_ad_email=usuario_ad_email,
            dias_validez=8
        )