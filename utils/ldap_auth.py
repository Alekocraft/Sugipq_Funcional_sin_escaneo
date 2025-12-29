# utils/ldap_auth.py - REEMPLAZAR contenido completo
"""
Autenticación con Active Directory Qualitas
"""
import ldap3
from ldap3 import Server, Connection, ALL, NTLM
import logging
from config.config import Config

logger = logging.getLogger(__name__)

class ADAuth:
    """Clase para autenticación con Active Directory"""
    
    def __init__(self):
        self.server_ip = Config.LDAP_SERVER
        self.domain = Config.LDAP_DOMAIN
        self.search_base = Config.LDAP_SEARCH_BASE
        
    def test_connection(self):
        """Prueba básica de conexión al servidor LDAP"""
        try:
            server = Server(self.server_ip, port=389, get_info=ALL)
            conn = Connection(server, auto_bind=True)
            conn.unbind()
            return True
        except Exception as e:
            logger.error(f"❌ Error conexión LDAP: {e}")
            return False
    
    def authenticate_user(self, username, password):
        """
        Autentica usuario contra Active Directory
    
        Args:
            username: Nombre de usuario (sin dominio)
            password: Contraseña
        
        Returns:
            dict: Información del usuario o None si falla
        """
        if not username or not password:
            return None
        
        try:
            # 1. Configurar servidor
            server = Server(
                self.server_ip,
                port=389,
                use_ssl=False,
                get_info=ALL
            )
        
            # 2. CORREGIDO: Usar formato domain\username para NTLM
            user_dn = f"{self.domain}\\{username}"
            logger.info(f"🔐 LDAP intentando autenticación con: {user_dn}")
        
            # 3. Intentar conexión y autenticación
            conn = Connection(
                server,
                user=user_dn,
                password=password,
                authentication=NTLM,
                auto_bind=True
            )
        
            if conn.bound:
                logger.info(f"✅ LDAP: Autenticación exitosa para {username}")
            
                # 4. Buscar información adicional del usuario
                user_info = self._get_user_details(conn, username)
                conn.unbind()
            
                if user_info:
                    # Asignar rol basado en departamento/grupos
                    user_info['role'] = self._assign_role(user_info)
                    return user_info
                else:
                    logger.warning(f"⚠️ LDAP: Usuario {username} autenticado pero no encontrado en búsqueda")
                    return {
                        'username': username,
                        'full_name': username,
                        'email': f"{username}@{self.domain}",
                        'department': 'No especificado',
                        'role': 'usuario'
                    }
            else:
                logger.error(f"❌ LDAP: Autenticación fallida para {username}")
                return None
            
        except Exception as e:
            logger.error(f"❌ LDAP: Error autenticando {username}: {e}")
            return None
    
    def _get_user_details(self, connection, username):
        """
        Obtiene detalles del usuario desde AD
        
        Args:
            connection: Conexión LDAP activa
            username: Nombre de usuario
            
        Returns:
            dict: Información del usuario
        """
        try:
            # Buscar usuario por sAMAccountName
            search_filter = f"(&(objectClass=user)(sAMAccountName={username}))"
            
            connection.search(
                search_base=self.search_base,
                search_filter=search_filter,
                attributes=['cn', 'mail', 'givenName', 'sn', 'department', 'memberOf']
            )
            
            if connection.entries:
                entry = connection.entries[0]
                
                # Extraer información
                user_info = {
                    'username': username,
                    'full_name': str(entry.cn) if 'cn' in entry else username,
                    'email': str(entry.mail) if 'mail' in entry else f"{username}@{self.domain}",
                    'first_name': str(entry.givenName) if 'givenName' in entry else '',
                    'last_name': str(entry.sn) if 'sn' in entry else '',
                    'department': str(entry.department) if 'department' in entry else 'No especificado',
                    'groups': [str(group) for group in entry.memberOf] if 'memberOf' in entry else []
                }
                
                return user_info
            else:
                logger.warning(f"⚠️ LDAP: Usuario {username} no encontrado en búsqueda")
                return None
                
        except Exception as e:
            logger.error(f"❌ LDAP: Error obteniendo detalles de {username}: {e}")
            return None
    
    def _assign_role(self, user_info):
        """
        Asigna rol del sistema basado en información AD
        
        Args:
            user_info: Diccionario con información del usuario
            
        Returns:
            str: Rol asignado
        """
        department = (user_info.get('department') or '').lower()
        groups = user_info.get('groups', [])
        
        # Verificar si es administrador (por grupo o departamento)
        if any('administradores' in g.lower() or 'domain admins' in g.lower() for g in groups):
            return 'admin'
        elif 'gerencia' in department or 'administracion' in department:
            return 'admin'
        elif 'finanzas' in department or 'contabilidad' in department:
            return 'finanzas'
        elif 'almacen' in department or 'logistica' in department:
            return 'almacen'
        elif 'rrhh' in department or 'recursos humanos' in department:
            return 'rrhh'
        else:
            return 'usuario'
    
    def search_user_by_name(self, search_term):
        """
        Busca usuarios en AD por nombre o usuario
        
        Args:
            search_term: Término de búsqueda
            
        Returns:
            list: Usuarios encontrados
        """
        try:
            # Conexión con usuario de servicio
            server = Server(self.server_ip, port=389, get_info=ALL)
            
            conn = Connection(
                server,
                user=f"{self.domain}\\{Config.LDAP_SERVICE_USER}",
                password=Config.LDAP_SERVICE_PASSWORD,
                authentication=NTLM,
                auto_bind=True
            )
            
            # Buscar usuarios que coincidan
            search_filter = f"(|(cn=*{search_term}*)(sAMAccountName=*{search_term}*))"
            
            conn.search(
                search_base=self.search_base,
                search_filter=search_filter,
                attributes=['cn', 'sAMAccountName', 'mail', 'department'],
                size_limit=10
            )
            
            users = []
            for entry in conn.entries:
                users.append({
                    'nombre': str(entry.cn),
                    'usuario': str(entry.sAMAccountName),
                    'email': str(entry.mail) if 'mail' in entry else '',
                    'departamento': str(entry.department) if 'department' in entry else ''
                })
            
            conn.unbind()
            return users
            
        except Exception as e:
            logger.error(f"❌ LDAP: Error buscando usuarios: {e}")
            return []

# Instancia global para usar en toda la aplicación
ad_auth = ADAuth()