# models/usuarios_model.py 

from database import get_database_connection
import logging
from config.config import Config
import bcrypt
import os
from utils.helpers import sanitizar_username, sanitizar_email, sanitizar_ip, sanitizar_log_text  # ✅ CORRECCIÓN: Importar funciones de sanitización

logger = logging.getLogger(__name__)

class UsuarioModel:
    
    @staticmethod
    def verificar_credenciales(usuario, contraseña):
        """
        Verifica credenciales PRIORIZANDO BD local, luego LDAP como fallback
        Maneja usuarios LDAP pendientes de sincronización
        """
        logger.info(f"🔐 Intentando autenticación para: {sanitizar_username(usuario)}")   
        
        # 1. PRIMERO: Intentar autenticación local
        logger.info(f"🔄 1. Intentando autenticación LOCAL para: {sanitizar_username(usuario)}")   
        usuario_local = UsuarioModel._verificar_localmente_corregido(usuario, contraseña)
        
        if usuario_local:
            logger.info(f"✅ Autenticación LOCAL exitosa para: {sanitizar_username(usuario)}")   
            return usuario_local
        
        logger.info(f"❌ Autenticación LOCAL falló para: {sanitizar_username(usuario)}")   
        
        # 2. Verificar si es usuario LDAP pendiente
        conn = get_database_connection()
        if conn:
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT UsuarioId, ContraseñaHash, Activo 
                    FROM Usuarios 
                    WHERE (NombreUsuario = ? OR UsuarioAD = ?) AND EsLDAP = 1
                """, (usuario, usuario))
                
                usuario_ldap = cursor.fetchone()
                conn.close()
                
                if usuario_ldap:
                    logger.info(f"🔄 Usuario LDAP encontrado: {sanitizar_username(usuario)}")   
                    
                    # Si está pendiente o es usuario LDAP
                    if usuario_ldap[1] in ['LDAP_PENDING', 'LDAP_USER']:
                        logger.info(f"🔄 2. Intentando LDAP para usuario registrado: {sanitizar_username(usuario)}")   
                        
                        if Config.LDAP_ENABLED:
                            try:
                                from utils.ldap_auth import ad_auth
                                ad_user = ad_auth.authenticate_user(usuario, contraseña)
                                
                                if ad_user:
                                    logger.info(f"✅ LDAP exitoso para usuario registrado: {sanitizar_username(usuario)}")  
                                    
                                    # Completar sincronización si estaba pendiente
                                    if usuario_ldap[1] == 'LDAP_PENDING':
                                        UsuarioModel.completar_sincronizacion_ldap(usuario, ad_user)
                                    
                                    # Obtener información del usuario
                                    usuario_info = UsuarioModel._obtener_info_usuario(usuario)
                                    if usuario_info:
                                        return usuario_info
                                    else:
                                        # Si no se puede obtener info, crear sesión básica
                                        return {
                                            'id': usuario_ldap[0],
                                            'usuario': usuario,
                                            'nombre': usuario,
                                            'rol': 'usuario',  # Rol por defecto hasta que se sincronice
                                            'oficina_id': 1,
                                            'oficina_nombre': ''
                                        }
                            except Exception as ldap_error:
                                logger.error(f"❌ Error en LDAP para usuario registrado: {ldap_error}")
                        
                        # Si LDAP falla pero el usuario existe
                        if usuario_ldap[2] == 1:  # Si está activo
                            logger.warning(f"⚠️ Usuario LDAP no pudo autenticarse: {sanitizar_username(usuario)}")  # ✅ CORRECCIÓN
                            return None
            
            except Exception as e:
                logger.error("❌ Error verificando usuario LDAP: [error](%s)", type(e).__name__)
                if conn:
                    conn.close()
        
        # 3. SEGUNDO: Solo si LDAP está habilitado y no es usuario registrado
        if Config.LDAP_ENABLED:
            logger.info(f"🔄 3. Intentando LDAP para usuario nuevo: {sanitizar_username(usuario)}")  # ✅ CORRECCIÓN
            try:
                from utils.ldap_auth import ad_auth
                ad_user = ad_auth.authenticate_user(usuario, contraseña)
                
                if ad_user:
                    logger.info(f"✅ LDAP exitoso para usuario nuevo: {sanitizar_username(usuario)}")  # ✅ CORRECCIÓN
                    # Sincronizar con BD local
                    usuario_info = UsuarioModel.sync_user_from_ad(ad_user)
                    
                    if usuario_info:
                        return usuario_info
                    else:
                        logger.error(f"❌ Error sincronizando usuario LDAP nuevo: {sanitizar_username(usuario)}")  # ✅ CORRECCIÓN
                else:
                    logger.warning(f"❌ LDAP también falló para: {sanitizar_username(usuario)}")  # ✅ CORRECCIÓN
            except Exception as ldap_error:
                logger.error(f"❌ Error en LDAP para usuario nuevo: {ldap_error}")
        
        # 4. Si todo falla
        logger.error(f"❌ TODAS las autenticaciones fallaron para: {sanitizar_username(usuario)}")  # ✅ CORRECCIÓN
        return None

    @staticmethod
    def _obtener_info_usuario(username):
        """
        Obtiene información completa del usuario desde BD
        """
        conn = get_database_connection()
        if not conn:
            return None
            
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    u.UsuarioId, 
                    u.NombreUsuario, 
                    u.CorreoElectronico,
                    u.Rol, 
                    u.OficinaId, 
                    o.NombreOficina,
                    u.EsLDAP
                FROM Usuarios u
                LEFT JOIN Oficinas o ON u.OficinaId = o.OficinaId
                WHERE (u.NombreUsuario = ? OR u.UsuarioAD = ?) AND u.Activo = 1
            """, (username, username))
            
            row = cursor.fetchone()
            
            if row:
                usuario_info = {
                    'id': row[0],
                    'usuario': row[1],
                    'nombre': row[2] if row[2] else row[1],
                    'rol': row[3],
                    'oficina_id': row[4],
                    'oficina_nombre': row[5] if row[5] else '',
                    'es_ldap': bool(row[6])
                }
                return usuario_info
            return None
                
        except Exception as e:
            logger.error("❌ Error obteniendo info usuario: [error](%s)", type(e).__name__)
            return None
        finally:
            if conn:
                conn.close()


    @staticmethod
    def get_by_username(username):
        """Obtiene un usuario por username (NombreUsuario o UsuarioAD).

        Devuelve un diccionario compatible con el resto del proyecto o None si no existe.
        Este método se agrega para compatibilidad con funcionalidades LDAP (test/sync).
        """
        if not username:
            return None

        conn = get_database_connection()
        if not conn:
            return None

        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT
                    u.UsuarioId,
                    u.NombreUsuario,
                    u.CorreoElectronico,
                    u.Rol,
                    u.OficinaId,
                    o.NombreOficina,
                    u.Activo,
                    u.EsLDAP,
                    u.UsuarioAD
                FROM Usuarios u
                LEFT JOIN Oficinas o ON u.OficinaId = o.OficinaId
                WHERE (u.NombreUsuario = ? OR u.UsuarioAD = ?)
            """, (username, username))

            row = cursor.fetchone()
            if not row:
                return None

            return {
                'id': row[0],
                'usuario': row[1],
                'nombre': row[2] if row[2] else row[1],
                'rol': row[3],
                'oficina_id': row[4],
                'oficina_nombre': row[5] if row[5] else '',
                'activo': int(row[6]) if row[6] is not None else 0,
                'es_ldap': int(row[7]) if row[7] is not None else 0,
                'usuario_ad': row[8] if row[8] else None,
            }
        except Exception as e:
            logger.error(f"❌ Error en get_by_username: {e}")
            return None
        finally:
            try:
                conn.close()
            except Exception:
                pass
    @staticmethod
    def _verificar_localmente_corregido(usuario, contraseña):
        """
        Autenticación local CORREGIDA - compatible con tu BD exacta
        """
        conn = get_database_connection()
        if not conn:
            logger.error("❌ No hay conexión a la BD")
            return None
            
        try:
            cursor = conn.cursor()
            
            # CONSULTA CORREGIDA según tu estructura exacta de BD
            cursor.execute("""
                SELECT 
                    u.UsuarioId, 
                    u.NombreUsuario, 
                    u.CorreoElectronico,
                    u.Rol, 
                    u.OficinaId, 
                    o.NombreOficina,
                    u.ContraseñaHash
                FROM Usuarios u
                LEFT JOIN Oficinas o ON u.OficinaId = o.OficinaId
                WHERE (u.NombreUsuario = ? OR u.UsuarioAD = ?) AND u.Activo = 1
            """, (usuario, usuario))
            
            row = cursor.fetchone()
            
            if row:
                logger.info(f"✅ Usuario encontrado en BD: {sanitizar_username(usuario)}")  # ✅ CORRECCIÓN
                logger.info(f"📋 Datos fila: UsuarioId={row[0]}, Rol={row[3]}, OficinaId={row[4]}")
                
                # Verificar contraseña hash
                stored_hash = row[6]  # ContraseñaHash está en posición 7 (índice 6)
                
                if not stored_hash:
                    logger.error(f"❌ Hash de contraseña vacío para: {sanitizar_username(usuario)}")  # ✅ CORRECCIÓN
                    return None
                
                logger.info(f"🔑 Hash almacenado (primeros 30 chars): {stored_hash[:30]}...")
                logger.info(f"🔑 Longitud hash: {len(stored_hash)}")
                
                try:
                    # IMPORTANTE: bcrypt.checkpw necesita ambos parámetros como bytes
                    password_bytes = contraseña.encode('utf-8')
                    hash_bytes = stored_hash.encode('utf-8')
                    
                    logger.info(f"🔑 Verificando contraseña...")
                    if bcrypt.checkpw(password_bytes, hash_bytes):
                        usuario_info = {
                            'id': row[0],           # UsuarioId
                            'usuario': row[1],      # NombreUsuario
                            'nombre': row[2] if row[2] else row[1],  # CorreoElectronico o NombreUsuario
                            'rol': row[3],          # Rol
                            'oficina_id': row[4],   # OficinaId
                            'oficina_nombre': row[5] if row[5] else ''  # NombreOficina
                        }
                        logger.info(f"✅ Contraseña CORRECTA para: {sanitizar_username(usuario)}")  # ✅ CORRECCIÓN
                        logger.info(f"📊 Info usuario final: usuario_id={usuario_info['id']}, rol={usuario_info['rol']}")  # ✅ CORRECCIÓN: No mostrar nombre completo
                        return usuario_info
                    else:
                        logger.error(f"❌ Contraseña INCORRECTA para: {sanitizar_username(usuario)}")  # ✅ CORRECCIÓN
                        return None
                        
                except Exception as bcrypt_error:
                    logger.error(f"❌ Error en bcrypt.checkpw: {bcrypt_error}")
                    logger.error(f"❌ Tipo de hash: {type(stored_hash)}")
                    logger.error(f"❌ Contraseña proporcionada: '[PROTEGIDA]'")  # ✅ CORRECCIÓN: No mostrar contraseña
                    return None
            else:
                logger.warning(f"⚠️ Usuario NO encontrado en BD local: {sanitizar_username(usuario)}")  # ✅ CORRECCIÓN
                return None
                
        except Exception as e:
            logger.error("❌ Error en _verificar_localmente_corregido: [error](%s)", type(e).__name__)
            return None
        finally:
            if conn:
                conn.close()
    
    @staticmethod
    def sync_user_from_ad(ad_user):
        """
        Sincroniza usuario desde AD a la base de datos local
        SOLO para usuarios que no existan localmente
        """
        conn = get_database_connection()
        if not conn:
            return None
        
        try:
            cursor = conn.cursor()
        
            # Verificar si el usuario ya existe
            cursor.execute("""
                SELECT 
                    UsuarioId, 
                    NombreUsuario, 
                    CorreoElectronico, 
                    Rol, 
                    OficinaId
                FROM Usuarios 
                WHERE NombreUsuario = ? AND Activo = 1
            """, (ad_user['username'],))  # CAMBIADO: 'username' no 'samaccountname'
        
            existing = cursor.fetchone()
        
            if existing:
                # Usuario ya existe localmente
                usuario_info = {
                    'id': existing[0],
                    'usuario': existing[1],
                    'nombre': existing[2] if existing[2] else existing[1],
                    'rol': existing[3],
                    'oficina_id': existing[4],
                    'oficina_nombre': ''
                }
                logger.info(f"ℹ️ Usuario ya existía en BD local: {sanitizar_username(ad_user['username'])}")  # ✅ CORRECCIÓN
                return usuario_info
            else:
                # Crear nuevo usuario desde AD
                default_rol = 'usuario'
                if 'role' in ad_user:  # CAMBIADO: 'role' no 'grupos'
                    default_rol = ad_user['role']
                else:
                    # Verificar grupos para determinar rol
                    groups = ad_user.get('groups', [])
                    if any('administradores' in g.lower() for g in groups):
                        default_rol = 'admin'  # Tu sistema usa 'admin'
                    elif any('aprobadores' in g.lower() for g in groups):
                        default_rol = 'aprobador'
                    elif any('tesorer' in g.lower() for g in groups):
                        default_rol = 'tesoreria'
            
                # Obtener oficina por defecto
                departamento = ad_user.get('department', '')
                oficina_id = UsuarioModel.get_default_office(departamento)
            
                # Si no hay oficina, usar la primera
                if not oficina_id:
                    cursor.execute("SELECT TOP 1 OficinaId FROM Oficinas WHERE Activo = 1")
                    oficina_result = cursor.fetchone()
                    oficina_id = oficina_result[0] if oficina_result else 1
            
                # Insertar nuevo usuario
                cursor.execute("""
                    INSERT INTO Usuarios (
                        NombreUsuario, 
                        CorreoElectronico, 
                        Rol, 
                        OficinaId, 
                        Activo, 
                        FechaCreacion,
                        ContraseñaHash,
                        EsLDAP
                    ) VALUES (?, ?, ?, ?, 1, GETDATE(), 'LDAP_USER', 1)
                """, (
                    ad_user['username'],
                    sanitizar_email(ad_user.get('email', f"{ad_user['username']}@qualitascolombia.com.co")),  # ✅ CORRECCIÓN
                    default_rol,
                    oficina_id
                ))
            
                conn.commit()
            
                # Obtener el ID del usuario creado
                cursor.execute("SELECT UsuarioId FROM Usuarios WHERE NombreUsuario = ?", (ad_user['username'],))
                new_id = cursor.fetchone()[0]
            
                usuario_info = {
                    'id': new_id,
                    'usuario': ad_user['username'],
                    'nombre': ad_user.get('full_name', ad_user['username']),
                    'rol': default_rol,
                    'oficina_id': oficina_id,
                    'oficina_nombre': '',
                    'es_ldap': True
                }
            
                logger.info(f"✅ Nuevo usuario sincronizado desde AD: {sanitizar_username(ad_user['username'])}")  # ✅ CORRECCIÓN
                return usuario_info
        except Exception as e:
            logger.error("❌ Error sincronizando usuario AD: [error](%s)", type(e).__name__)
            if conn:
                conn.rollback()
            return None
        finally:
            if conn:
                conn.close()
    
    @staticmethod
    def get_default_office(department):
        """
        Obtiene el ID de oficina por defecto basado en departamento AD
        """
        conn = get_database_connection()
        if not conn:
            return None
        
        try:
            cursor = conn.cursor()
        
            # Mapeo de departamentos Qualitas a oficinas
            department_mapping = {
                'tesorería': 'Tesoreria',
                'finanzas': 'Tesoreria',
                'contabilidad': 'Tesoreria',
                'administración': 'Administración',
                'gerencia': 'Gerencia',
                'sistemas': 'Sistemas',
                'tecnología': 'Sistemas',
                'rrhh': 'Recursos Humanos',
                'recursos humanos': 'Recursos Humanos',
                'comercial': 'Comercial',
                'ventas': 'Comercial',
                'operaciones': 'Operaciones',
                'logística': 'Logística',
                'almacén': 'Logística'
            }
        
            department_lower = (department or '').lower()
        
            # Buscar oficina por mapeo de departamento
            for dept_key, dept_name in department_mapping.items():
                if dept_key in department_lower:
                    cursor.execute("""
                        SELECT OficinaId FROM Oficinas 
                        WHERE NombreOficina LIKE ? AND Activo = 1
                    """, (f'%{dept_name}%',))
                    result = cursor.fetchone()
                    if result:
                        return result[0]
        
            # Si no encuentra, buscar oficina por nombre similar al departamento
            if department:
                cursor.execute("""
                    SELECT OficinaId FROM Oficinas 
                    WHERE (NombreOficina LIKE ? OR Ubicacion LIKE ?) 
                    AND Activo = 1
                    ORDER BY OficinaId
                """, (f'%{department}%', f'%{department}%'))
                result = cursor.fetchone()
                if result:
                    return result[0]
        
            # Si todo falla, usar la primera oficina activa
            cursor.execute("SELECT TOP 1 OficinaId FROM Oficinas WHERE Activo = 1 ORDER BY OficinaId")
            default_office = cursor.fetchone()
        
            return default_office[0] if default_office else 1
            
        except Exception as e:
            logger.error("❌ Error obteniendo oficina por defecto: [error](%s)", type(e).__name__)
            return 1
        finally:
            if conn:
                conn.close()
    
    @staticmethod
    def obtener_aprobadores():
        """
        Obtiene usuarios con rol de aprobación
        """
        conn = get_database_connection()
        if not conn:
            return []
            
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    UsuarioId, 
                    CorreoElectronico, 
                    NombreUsuario, 
                    OficinaId
                FROM Usuarios 
                WHERE Rol IN ('aprobador', 'administrador') AND Activo = 1
                ORDER BY CorreoElectronico
            """)
            
            aprobadores = []
            for row in cursor.fetchall():
                aprobadores.append({
                    'id': row[0],
                    'nombre': row[1] if row[1] else row[2],  # CorreoElectronico o NombreUsuario
                    'usuario': row[2],
                    'oficina_id': row[3]
                })
            
            return aprobadores
            
        except Exception as e:
            logger.error("❌ Error obteniendo aprobadores: [error](%s)", type(e).__name__)
            return []
        finally:
            if conn:
                conn.close()
    
    @staticmethod
    def crear_usuario_manual(usuario_data):
        """
        Crea usuario manualmente (para casos especiales)
        
        Args:
            usuario_data: Dict con datos del usuario
            
        Returns:
            bool: True si éxito
        """
        conn = get_database_connection()
        if not conn:
            return False
            
        try:
            cursor = conn.cursor()
            
            # Generar hash de contraseña
            password_hash = bcrypt.hashpw(
                usuario_data['password'].encode('utf-8'), 
                bcrypt.gensalt()
            ).decode('utf-8')
            
            # Insertar usuario
            cursor.execute("""
                INSERT INTO Usuarios (
                    NombreUsuario, 
                    CorreoElectronico, 
                    Rol, 
                    OficinaId, 
                    ContraseñaHash, 
                    Activo, 
                    FechaCreacion
                ) VALUES (?, ?, ?, ?, ?, 1, GETDATE())
            """, (
                usuario_data['usuario'],
                usuario_data.get('nombre', usuario_data['usuario']),
                usuario_data['rol'],
                usuario_data['oficina_id'],
                password_hash
            ))
            
            conn.commit()
            logger.info(f"✅ Usuario manual creado: {sanitizar_username(usuario_data['usuario'])}")  # ✅ CORRECCIÓN
            return True
            
        except Exception as e:
            logger.error("❌ Error creando usuario manual: [error](%s)", type(e).__name__)
            conn.rollback()
            return False
        finally:
            if conn:
                conn.close()
    
    @staticmethod
    def crear_usuario_admin_inicial():
        """
        Crea un usuario administrador inicial si no existe ninguno
        Ahora usa contraseña desde variable de entorno
        """
        conn = get_database_connection()
        if not conn:
            return False
            
        try:
            cursor = conn.cursor()
            
            # Verificar si ya existe un usuario admin
            cursor.execute("SELECT COUNT(*) FROM Usuarios WHERE Rol = 'administrador' AND Activo = 1")
            admin_count = cursor.fetchone()[0]
            
            if admin_count > 0:
                logger.info("✅ Ya existe al menos un usuario administrador")
                return True
            
            # Verificar si existe la oficina por defecto
            cursor.execute("SELECT TOP 1 OficinaId FROM Oficinas WHERE Activo = 1 ORDER BY OficinaId")
            default_office = cursor.fetchone()
            
            oficina_id = default_office[0] if default_office else None
            
            if not oficina_id:
                logger.error("❌ No hay oficinas activas para asignar al usuario admin")
                return False
            
           
            admin_password = os.getenv('ADMIN_DEFAULT_PASSWORD')
            
            if not admin_password:
                logger.error("❌ ADMIN_DEFAULT_PASSWORD no configurado en variables de entorno")
                logger.error("   Configurar en .env: ADMIN_DEFAULT_PASSWORD=tu_contraseña_segura")
                return False
            
            # Generar hash para contraseña del administrador
            password_hash = bcrypt.hashpw(
                admin_password.encode('utf-8'), 
                bcrypt.gensalt()
            ).decode('utf-8')
            
            # Crear usuario admin - USANDO 'administrador' como rol (no 'admin')
            cursor.execute("""
                INSERT INTO Usuarios (
                    NombreUsuario, 
                    CorreoElectronico, 
                    Rol, 
                    OficinaId, 
                    ContraseñaHash, 
                    Activo, 
                    FechaCreacion
                ) VALUES ('admin', 'Administrador del Sistema', 'administrador', ?, ?, 1, GETDATE())
            """, (oficina_id, password_hash))
            
            conn.commit()
            logger.info("✅ Usuario administrador creado exitosamente")
            logger.info("🔑 Credenciales: usuario=admin, contraseña=[PROTEGIDA]")  # ✅ CORRECCIÓN: No mostrar contraseña
            logger.info("ℹ️ La contraseña se obtuvo de la variable de entorno ADMIN_DEFAULT_PASSWORD")
            return True
            
        except Exception as e:
            logger.error("❌ Error creando usuario admin: [error](%s)", type(e).__name__)
            if conn:
                conn.rollback()
            return False
        finally:
            if conn:
                conn.close()
    
    @staticmethod
    def obtener_por_id(usuario_id):
        """
        Obtiene usuario por ID
        """
        conn = get_database_connection()
        if not conn:
            return None
            
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    u.UsuarioId, 
                    u.NombreUsuario, 
                    u.CorreoElectronico,
                    u.Rol, 
                    u.OficinaId, 
                    o.NombreOficina
                FROM Usuarios u
                LEFT JOIN Oficinas o ON u.OficinaId = o.OficinaId
                WHERE u.UsuarioId = ? AND u.Activo = 1
            """, (usuario_id,))
            
            row = cursor.fetchone()
            
            if row:
                return {
                    'id': row[0],
                    'usuario': row[1],
                    'nombre': row[2] if row[2] else row[1],
                    'rol': row[3],
                    'oficina_id': row[4],
                    'oficina_nombre': row[5] if row[5] else ''
                }
            return None
            
        except Exception as e:
            logger.error("❌ Error obteniendo usuario por ID: [error](%s)", type(e).__name__)
            return None
        finally:
            if conn:
                conn.close()
    
    @staticmethod
    def obtener_todos():
        """
        Obtiene todos los usuarios activos
        """
        conn = get_database_connection()
        if not conn:
            return []
            
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    u.UsuarioId, 
                    u.NombreUsuario, 
                    u.CorreoElectronico,
                    u.Rol, 
                    u.OficinaId, 
                    o.NombreOficina,
                    u.FechaCreacion,
                    u.EsLDAP
                FROM Usuarios u
                LEFT JOIN Oficinas o ON u.OficinaId = o.OficinaId
                WHERE u.Activo = 1
                ORDER BY u.NombreUsuario
            """)
            
            usuarios = []
            for row in cursor.fetchall():
                usuarios.append({
                    'id': row[0],
                    'usuario': row[1],
                    'nombre': row[2] if row[2] else row[1],
                    'rol': row[3],
                    'oficina_id': row[4],
                    'oficina_nombre': row[5] if row[5] else '',
                    'fecha_creacion': row[6],
                    'es_ldap': bool(row[7])
                })
            
            return usuarios
            
        except Exception as e:
            logger.error("❌ Error obteniendo todos los usuarios: [error](%s)", type(e).__name__)
            return []
        finally:
            if conn:
                conn.close()
    
    @staticmethod
    def map_ad_role_to_system_role(ad_user):
        """
        Mapea el rol de AD al rol del sistema según la configuración de permisos
    
        Args:
            ad_user: Diccionario con información del usuario de AD
        
        Returns:
            str: Rol del sistema (debe coincidir con ROLE_PERMISSIONS en config/permissions.py)
        """
        # Verificar si ldap_auth ya asignó un rol
        if 'role' in ad_user:
            ad_role = ad_user['role']
        
            # Mapear roles de AD a roles del sistema
            role_mapping = {
                'admin': 'administrador',  # AD dice 'admin', sistema dice 'administrador'
                'finanzas': 'tesoreria',
                'almacen': 'lider_inventario',
                'rrhh': 'usuario',
                'usuario': 'usuario'
            }
        
            # Si está mapeado, usar el mapeo
            if ad_role in role_mapping:
                return role_mapping[ad_role]
        
            # Si no, verificar si coincide con algún rol del sistema
            from config.permissions import ROLE_PERMISSIONS
            if ad_role in ROLE_PERMISSIONS:
                return ad_role
    
        # Si no hay rol de AD o no está mapeado, usar grupos/departamento
        groups = ad_user.get('groups', [])
        department = (ad_user.get('department') or '').lower()
    
        # Verificar por grupos
        if any('administradores' in g.lower() for g in groups):
            return 'administrador'
        elif any('tesorer' in g.lower() or 'financ' in g.lower() for g in groups):
            return 'tesoreria'
        elif any('lider' in g.lower() and 'invent' in g.lower() for g in groups):
            return 'lider_inventario'
        elif any('aprobador' in g.lower() for g in groups):
            return 'aprobador'
        elif any('coq' in g.lower() for g in groups):
            return 'oficina_coq'
        elif any('polo' in g.lower() for g in groups):
            return 'oficina_polo_club'
    
        # Verificar por departamento
        if 'tesorer' in department or 'financ' in department:
            return 'tesoreria'
        elif 'admin' in department:
            return 'administrador'
        elif 'logist' in department or 'almacen' in department:
            return 'lider_inventario'
    
        # Por defecto
        return 'usuario'

    @staticmethod
    def crear_usuario_ldap_manual(usuario_data):
        """
        Crea usuario LDAP manualmente (para administradores)
        El usuario debe autenticarse primero con LDAP para activarse
        
        Args:
            usuario_data: Dict con datos del usuario LDAP
            
        Returns:
            dict: Información del usuario creado o None si error
        """
        conn = get_database_connection()
        if not conn:
            return None
            
        try:
            cursor = conn.cursor()
            
            # Verificar si ya existe
            cursor.execute("""
                SELECT UsuarioId FROM Usuarios 
                WHERE NombreUsuario = ? AND Activo = 1
            """, (usuario_data['usuario'],))
            
            if cursor.fetchone():
                logger.warning(f"⚠️ Usuario LDAP ya existe: {sanitizar_username(usuario_data['usuario'])}")  # ✅ CORRECCIÓN
                return None
            
            # Insertar usuario LDAP (con hash especial)
            cursor.execute("""
                INSERT INTO Usuarios (
                    NombreUsuario, 
                    CorreoElectronico, 
                    Rol, 
                    OficinaId, 
                    ContraseñaHash, 
                    Activo, 
                    FechaCreacion,
                    EsLDAP
                ) VALUES (?, ?, ?, ?, 'LDAP_PENDING', 1, GETDATE(), 1)
            """, (
                usuario_data['usuario'],
                sanitizar_email(usuario_data.get('email', f"{usuario_data['usuario']}@qualitascolombia.com.co")),  # ✅ CORRECCIÓN
                usuario_data.get('rol', 'usuario'),
                usuario_data.get('oficina_id', 1)
            ))
            
            conn.commit()
            
            # Obtener el ID del usuario creado
            cursor.execute("SELECT UsuarioId FROM Usuarios WHERE NombreUsuario = ?", (usuario_data['usuario'],))
            new_id = cursor.fetchone()[0]
            
            usuario_info = {
                'id': new_id,
                'usuario': usuario_data['usuario'],
                'email': usuario_data.get('email', ''),
                'rol': usuario_data.get('rol', 'usuario'),
                'oficina_id': usuario_data.get('oficina_id', 1)
            }
            
            logger.info(f"✅ Usuario LDAP manual creado: {sanitizar_username(usuario_data['usuario'])} (pendiente de autenticación)")  # ✅ CORRECCIÓN
            return usuario_info
                
        except Exception as e:
            logger.error("❌ Error creando usuario LDAP manual: [error](%s)", type(e).__name__)
            if conn:
                conn.rollback()
            return None
        finally:
            if conn:
                conn.close()

    @staticmethod
    def completar_sincronizacion_ldap(username, ad_user_info):
        """
        Completa la sincronización de un usuario LDAP después de autenticación exitosa
        
        Args:
            username: Nombre de usuario
            ad_user_info: Información del usuario desde AD
            
        Returns:
            bool: True si éxito
        """
        conn = get_database_connection()
        if not conn:
            return False
            
        try:
            cursor = conn.cursor()
            
            # Actualizar información del usuario LDAP
            cursor.execute("""
                UPDATE Usuarios 
                SET CorreoElectronico = ?,
                    ContraseñaHash = 'LDAP_USER',
                    EsLDAP = 1,
                    FechaActualizacion = GETDATE()
                WHERE NombreUsuario = ? AND ContraseñaHash = 'LDAP_PENDING'
            """, (
                sanitizar_email(ad_user_info.get('email', f"{username}@qualitascolombia.com.co")),  # ✅ CORRECCIÓN
                username
            ))
            
            if cursor.rowcount == 0:
                # Si no estaba pendiente, actualizar igual
                cursor.execute("""
                    UPDATE Usuarios 
                    SET CorreoElectronico = ?,
                        EsLDAP = 1,
                        FechaActualizacion = GETDATE()
                    WHERE NombreUsuario = ?
                """, (
                    sanitizar_email(ad_user_info.get('email', f"{username}@qualitascolombia.com.co")),  # ✅ CORRECCIÓN
                    username
                ))
            
            conn.commit()
            logger.info(f"✅ Sincronización LDAP completada para: {sanitizar_username(username)}")  # ✅ CORRECCIÓN
            return True
                
        except Exception as e:
            logger.error("❌ Error completando sincronización LDAP: [error](%s)", type(e).__name__)
            if conn:
                conn.rollback()
            return False
        finally:
            if conn:
                conn.close()    
    
    @staticmethod
    def obtener_aprobadores_desde_tabla():
        """
        Obtiene aprobadores desde la tabla Aprobadores (no desde Usuarios)
        """
        conn = get_database_connection()
        if not conn:
            return []
            
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    AprobadorId,
                    NombreAprobador,
                    Email,
                    Activo,
                    FechaCreacion
                FROM Aprobadores 
                WHERE Activo = 1
                ORDER BY NombreAprobador
            """)
            
            aprobadores = []
            for row in cursor.fetchall():
                aprobadores.append({
                    'AprobadorId': row[0],
                    'NombreAprobador': row[1],
                    'Email': sanitizar_email(row[2]) if row[2] else '',  # ✅ CORRECCIÓN
                    'Activo': row[3],
                    'FechaCreacion': row[4]
                })
            
            logger.info(f"✅ Se encontraron {len(aprobadores)} aprobadores desde tabla Aprobadores")  # ✅ CORRECCIÓN: Línea 859 ahora está segura
            return aprobadores
            
        except Exception as e:
            logger.error("❌ Error obteniendo aprobadores desde tabla: [error](%s)", type(e).__name__)
            return []
        finally:
            if conn:
                conn.close()