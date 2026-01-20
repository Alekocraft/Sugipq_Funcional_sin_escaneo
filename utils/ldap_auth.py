"""
Autenticación con Active Directory Qualitas
Versión segura - DÍA 5: Sanitización de usernames en logs
"""
import ldap3
from ldap3 import Server, Connection, ALL, NTLM
import logging
from config.config import Config
from utils.helpers import sanitizar_username  # ✅ DÍA 5 - Sanitizar usernames en logs

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
            logger.error("❌ Error conexión LDAP: [error](%s)", type(e).__name__)
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
            # ✅ DÍA 5 - Sanitizar username en log
            logger.info(f"🔐 LDAP intentando autenticación con: {self.domain}\\{sanitizar_username(username)}")
        
            # 3. Intentar conexión y autenticación
            conn = Connection(
                server,
                user=user_dn,
                password=password,
                authentication=NTLM,
                auto_bind=True
            )
        
            if conn.bound:
                # ✅ DÍA 5 - Sanitizar username en log
                logger.info(f"✅ LDAP: Autenticación exitosa para {sanitizar_username(username)}")
            
                # 4. Buscar información adicional del usuario
                user_info = self._get_user_details(conn, username)
                conn.unbind()
            
                if user_info:
                    # Asignar rol basado en departamento/grupos
                    user_info['role'] = self._assign_role(user_info)
                    return user_info
                else:
                    # ✅ DÍA 5 - Sanitizar username en log
                    logger.warning(f"⚠️ LDAP: Usuario {sanitizar_username(username)} autenticado pero no encontrado en búsqueda")
                    return {
                        'username': username,
                        'full_name': username,
                        'email': f"{username}@{self.domain}",
                        'department': 'No especificado',
                        'role': 'usuario'
                    }
            else:
                # ✅ DÍA 5 - Sanitizar username en log
                logger.error(f"❌ LDAP: Autenticación fallida para {sanitizar_username(username)}")
                return None
            
        except Exception as e:
            # ✅ DÍA 5 - Sanitizar username en log
            logger.error("❌ LDAP: Error autenticando {sanitizar_username(username)}: [error](%s)", type(e).__name__)
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
                # ✅ DÍA 5 - Sanitizar username en log
                logger.warning(f"⚠️ LDAP: Usuario {sanitizar_username(username)} no encontrado en búsqueda")
                return None
                
        except Exception as e:
            # ✅ DÍA 5 - Sanitizar username en log
            logger.error("❌ LDAP: Error obteniendo detalles de {sanitizar_username(username)}: [error](%s)", type(e).__name__)
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
            logger.error("❌ LDAP: Error buscando usuarios: [error](%s)", type(e).__name__)
            return []
    
    def search_user_by_email(self, email):
        """
        Busca usuario en AD por email
        
        Args:
            email: Email del usuario
            
        Returns:
            dict: Información del usuario encontrado o None
        """
        if not email:
            return None
            
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
            
            # Buscar usuario por email (correo electrónico)
            search_filter = f"(&(objectClass=user)(mail={email}))"
            
            conn.search(
                search_base=self.search_base,
                search_filter=search_filter,
                attributes=['cn', 'sAMAccountName', 'mail', 'department', 'givenName', 'sn'],
                size_limit=1
            )
            
            if conn.entries:
                entry = conn.entries[0]
                user_info = {
                    'nombre': str(entry.cn),
                    'usuario': str(entry.sAMAccountName),
                    'email': str(entry.mail) if 'mail' in entry else email,
                    'departamento': str(entry.department) if 'department' in entry else '',
                    'first_name': str(entry.givenName) if 'givenName' in entry else '',
                    'last_name': str(entry.sn) if 'sn' in entry else ''
                }
                conn.unbind()
                return user_info
            else:
                # También buscar por userPrincipalName (alternativo)
                search_filter = f"(&(objectClass=user)(userPrincipalName={email}))"
                conn.search(
                    search_base=self.search_base,
                    search_filter=search_filter,
                    attributes=['cn', 'sAMAccountName', 'mail', 'department', 'givenName', 'sn'],
                    size_limit=1
                )
                
                if conn.entries:
                    entry = conn.entries[0]
                    user_info = {
                        'nombre': str(entry.cn),
                        'usuario': str(entry.sAMAccountName),
                        'email': str(entry.mail) if 'mail' in entry else email,
                        'departamento': str(entry.department) if 'department' in entry else '',
                        'first_name': str(entry.givenName) if 'givenName' in entry else '',
                        'last_name': str(entry.sn) if 'sn' in entry else ''
                    }
                    conn.unbind()
                    return user_info
            
            conn.unbind()
            return None
            
        except Exception as e:
            logger.error("❌ LDAP: Error buscando usuario por email {email}: [error](%s)", type(e).__name__)
            return None
    
    def get_user_details(self, username):
        """
        Obtiene detalles de usuario sin autenticar (solo lectura)
        
        Args:
            username: Nombre de usuario
            
        Returns:
            dict: Información del usuario o None
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
            
            # Buscar usuario por sAMAccountName
            search_filter = f"(&(objectClass=user)(sAMAccountName={username}))"
            
            conn.search(
                search_base=self.search_base,
                search_filter=search_filter,
                attributes=['cn', 'mail', 'givenName', 'sn', 'department', 'memberOf'],
                size_limit=1
            )
            
            if conn.entries:
                entry = conn.entries[0]
                user_info = {
                    'username': username,
                    'full_name': str(entry.cn) if 'cn' in entry else username,
                    'email': str(entry.mail) if 'mail' in entry else f"{username}@{self.domain}",
                    'first_name': str(entry.givenName) if 'givenName' in entry else '',
                    'last_name': str(entry.sn) if 'sn' in entry else '',
                    'department': str(entry.department) if 'department' in entry else 'No especificado',
                    'groups': [str(group) for group in entry.memberOf] if 'memberOf' in entry else []
                }
                conn.unbind()
                return user_info
            else:
                conn.unbind()
                return None
                
        except Exception as e:
            logger.error("❌ LDAP: Error obteniendo detalles de {username}: [error](%s)", type(e).__name__)
            return None


# Instancia global para usar en toda la aplicación
ad_auth = ADAuth()