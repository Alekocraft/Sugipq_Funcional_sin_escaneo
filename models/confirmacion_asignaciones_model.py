"""
Modelo para gestionar confirmaciones de asignaciones con tokens temporales.
Incluye autenticación contra Active Directory y validación de cédula.
CORREGIDO: Usa authenticate_user en lugar de authenticate
"""
from database import get_database_connection
import logging
from utils.helpers import sanitizar_username, sanitizar_log_text
import secrets
import hashlib
from datetime import datetime, timedelta
import re

logger = logging.getLogger(__name__)

# Intentar importar LDAP
try:
    from utils.ldap_auth import ad_auth
    LDAP_AVAILABLE = True
except ImportError:
    LDAP_AVAILABLE = False
    logger.warning("LDAP no disponible - autenticación AD deshabilitada")


class ConfirmacionAsignacionesModel:
    """
    Modelo para gestionar confirmaciones de asignaciones de inventario.
    """
    
    @staticmethod
    def validar_cedula_colombiana(cedula):
        """
        Valida un número de cédula colombiana.
        
        Args:
            cedula: Número de cédula a validar
            
        Returns:
            bool: True si es válida, False si no
        """
        if not cedula or not isinstance(cedula, str):
            return False
        
        # Limpiar espacios y guiones
        cedula = cedula.strip().replace('-', '').replace('.', '').replace(' ', '')
        
        # Validar que solo tenga dígitos
        if not cedula.isdigit():
            return False
        
        # Longitudes válidas para cédulas colombianas
        if len(cedula) not in [8, 10]:
            return False
        
        # Validación básica de formato
        # Para cédulas de 8 dígitos (antiguas)
        if len(cedula) == 8:
            # Validar que no empiece con 0
            if cedula[0] == '0':
                return False
            
            # Validar rango general
            try:
                num_cedula = int(cedula)
                if num_cedula < 1000000 or num_cedula > 99999999:
                    return False
            except:
                return False
        
        # Para cédulas de 10 dígitos (nuevas)
        elif len(cedula) == 10:
            # Validar que empiece con dígitos válidos
            primer_digito = int(cedula[0])
            if primer_digito not in [1, 2, 3, 4, 5, 6, 7, 8, 9]:
                return False
            
            # Validar rango general
            try:
                num_cedula = int(cedula)
                if num_cedula < 1000000000 or num_cedula > 9999999999:
                    return False
            except:
                return False
        
        return True
    
    @staticmethod
    def autenticar_usuario_ad(username, password):
        """
        Autentica un usuario contra Active Directory.
        
        Args:
            username: Nombre de usuario AD
            password: Contraseña
            
        Returns:
            dict: Resultado de autenticación con 'success', 'message', 'user_info'
        """
        if not LDAP_AVAILABLE:
            return {
                'success': False,
                'message': 'Servicio de autenticación no disponible'
            }
        
        if not username or not password:
            return {
                'success': False,
                'message': 'Usuario y contraseña son requeridos'
            }
        
        try:
            logger.info("Intentando autenticar usuario AD: %s", sanitizar_username(username))
            
            # CORREGIDO: Usar authenticate_user en lugar de authenticate
            user_info = ad_auth.authenticate_user(username, password)
            
            if user_info:
                return {
                    'success': True,
                    'message': 'Autenticación exitosa',
                    'user_info': user_info
                }
            else:
                logger.warning("Autenticación fallida para usuario: %s", sanitizar_username(username))
                return {
                    'success': False,
                    'message': 'Credenciales inválidas'
                }
                
        except Exception as e:
            logger.error("Error autenticando usuario AD: [error](%s)", type(e).__name__)
            return {
                'success': False,
                'message': f'Error de autenticación: {sanitizar_log_text(str(e))}'
            }
    
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
            logger.error("Error generando token: [error](%s)", type(e).__name__)
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
            dict: Información del token
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
                    t.FechaUtilizacion,
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
            fecha_utilizacion = row[5]
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
                    'fecha_confirmacion': fecha_utilizacion,
                    'ya_confirmado': True
                }
            
            # Verificar expiración
            if fecha_expiracion and datetime.now() > fecha_expiracion:
                return {
                    'es_valido': False, 
                    'mensaje_error': 'El enlace ha expirado',
                    'fecha_expiracion': fecha_expiracion,
                    'expirado': True
                }
            
            # Calcular días restantes
            if fecha_expiracion:
                dias_restantes = (fecha_expiracion - datetime.now()).days
            else:
                dias_restantes = 0
            
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
                'fecha_expiracion': fecha_expiracion,
                'dias_restantes': dias_restantes
            }
            
        except Exception as e:
            logger.error("Error validando token: [error](%s)", type(e).__name__)
            return {'es_valido': False, 'mensaje_error': f'Error al validar: {str(e)}'}
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
    
    @staticmethod
    def verificar_usuario_asignacion(asignacion_id, username):
        """
        Verifica que el usuario sea el correcto para la asignación.
        
        Args:
            asignacion_id: ID de la asignación
            username: Nombre de usuario AD
            
        Returns:
            dict: Resultado de verificación
        """
        conn = get_database_connection()
        if not conn:
            return {'coincide': False, 'message': 'Error de conexión'}
        
        cursor = None
        try:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT UsuarioADNombre, UsuarioADEmail 
                FROM Asignaciones 
                WHERE AsignacionId = ? AND Activo = 1
            """, (asignacion_id,))
            
            asignacion = cursor.fetchone()
            
            if not asignacion:
                return {'coincide': False, 'message': 'Asignación no encontrada'}
            
            usuario_ad_nombre = asignacion[0]
            usuario_ad_email = asignacion[1]
            
            # Verificar por nombre de usuario AD
            if usuario_ad_nombre and username.lower() == usuario_ad_nombre.lower():
                return {
                    'coincide': True,
                    'message': 'Usuario válido',
                    'usuario_ad_nombre': usuario_ad_nombre,
                    'usuario_ad_email': usuario_ad_email
                }
            
            # Si no coincide por nombre, verificar por email
            if usuario_ad_email:
                # Buscar usuario en AD por email para verificar
                if LDAP_AVAILABLE:
                    user_info = ad_auth.search_user_by_email(usuario_ad_email)
                    if user_info and user_info.get('usuario', '').lower() == username.lower():
                        return {
                            'coincide': True,
                            'message': 'Usuario válido (verificado por email)',
                            'usuario_ad_nombre': usuario_ad_nombre,
                            'usuario_ad_email': usuario_ad_email
                        }
            
            return {
                'coincide': False,
                'message': 'El usuario no coincide con la asignación'
            }
            
        except Exception as e:
            logger.error("Error verificando usuario de asignación: [error](%s)", type(e).__name__)
            return {'coincide': False, 'message': f'Error de verificación: {str(e)}'}
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
    
    @staticmethod
    def confirmar_asignacion(token, username, password, numero_identificacion, direccion_ip=None, user_agent=None):
        """
        Confirma una asignación con autenticación AD y cédula.
        
        Args:
            token: Token de confirmación
            username: Nombre de usuario AD
            password: Contraseña AD
            numero_identificacion: Número de cédula
            direccion_ip: IP desde donde se confirma
            user_agent: User agent del navegador
            
        Returns:
            dict: Resultado de la confirmación
        """
        # 1. Validar token
        validacion_token = ConfirmacionAsignacionesModel.validar_token(token)
        
        if not validacion_token.get('es_valido'):
            return {
                'success': False, 
                'message': validacion_token.get('mensaje_error', 'Token inválido')
            }
        
        asignacion_id = validacion_token.get('asignacion_id')
        usuario_email = validacion_token.get('usuario_email')
        
        # 2. Verificar cédula
        if not ConfirmacionAsignacionesModel.validar_cedula_colombiana(numero_identificacion):
            return {
                'success': False,
                'message': 'Número de cédula inválido. Debe ser un número de 8 o 10 dígitos válido.'
            }
        
        # 3. Autenticar usuario contra AD
        auth_result = ConfirmacionAsignacionesModel.autenticar_usuario_ad(username, password)
        
        if not auth_result.get('success'):
            return {
                'success': False,
                'message': f'Error de autenticación: {auth_result.get("message", "Credenciales inválidas")}'
            }
        
        # 4. Verificar que el usuario autenticado es el correcto para la asignación
        verificacion = ConfirmacionAsignacionesModel.verificar_usuario_asignacion(asignacion_id, username)
        
        if not verificacion.get('coincide'):
            return {
                'success': False,
                'message': verificacion.get('message', 'Usuario no autorizado para confirmar esta asignación')
            }
        
        # 5. Procesar confirmación en la base de datos
        conn = get_database_connection()
        if not conn:
            return {'success': False, 'message': 'Error de conexión a la base de datos'}
        
        cursor = None
        try:
            cursor = conn.cursor()
            
            # Obtener token_id usando el hash
            token_hash = hashlib.sha256(token.encode()).hexdigest()
            cursor.execute("""
                SELECT TokenId FROM TokensConfirmacionAsignacion 
                WHERE TokenHash = ? AND AsignacionId = ?
            """, (token_hash, asignacion_id))
            
            token_row = cursor.fetchone()
            if not token_row:
                return {'success': False, 'message': 'Token no encontrado'}
            
            token_id = token_row[0]
            
            # Marcar token como utilizado
            cursor.execute("""
                UPDATE TokensConfirmacionAsignacion
                SET Utilizado = 1,
                    FechaUtilizacion = GETDATE(),
                    NumeroIdentificacion = ?,
                    DireccionIP = ?,
                    UserAgent = ?,
                    UsuarioConfirmacion = ?
                WHERE TokenId = ?
            """, (numero_identificacion, direccion_ip, user_agent, username, token_id))
            
            # Actualizar estado de la asignación
            cursor.execute("""
                UPDATE Asignaciones
                SET Estado = 'CONFIRMADO',
                    FechaConfirmacion = GETDATE(),
                    UsuarioConfirmacion = ?
                WHERE AsignacionId = ?
            """, (username, asignacion_id))
            
            conn.commit()
            
            # Registrar en log
            logger.info(f"""
                ✅ Confirmación exitosa:
                - Asignación: {asignacion_id}
                - Usuario: {username}
                - Cédula: {numero_identificacion[:3]}***
                - Producto: {validacion_token.get('producto_nombre')}
                - IP: {direccion_ip}
            """)
            
            return {
                'success': True,
                'message': 'Asignación confirmada exitosamente',
                'asignacion_id': asignacion_id,
                'producto_nombre': validacion_token.get('producto_nombre'),
                'oficina_nombre': validacion_token.get('oficina_nombre'),
                'usuario_nombre': username,
                'cedula': numero_identificacion,
                'fecha_confirmacion': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
        except Exception as e:
            logger.error("Error confirmando asignación: [error](%s)", type(e).__name__)
            if conn:
                try:
                    conn.rollback()
                except:
                    pass
            return {'success': False, 'message': f'Error al procesar confirmación: {str(e)}'}
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
                if item.get('FechaExpiracion'):
                    dias_restantes = (item['FechaExpiracion'] - datetime.now()).days
                    item['dias_restantes'] = max(0, dias_restantes)
                resultados.append(item)
            
            return resultados
            
        except Exception as e:
            logger.error("Error obteniendo confirmaciones pendientes: [error](%s)", type(e).__name__)
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
            logger.error("Error limpiando tokens expirados: [error](%s)", type(e).__name__)
            return 0
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()