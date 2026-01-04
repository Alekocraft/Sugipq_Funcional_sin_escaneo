# services/auth_service.py
"""
Servicio de autenticación que integra LDAP con la base de datos local
"""
from utils.ldap_auth import ADAuth  # ✅ CORREGIDO: Usar ADAuth en lugar de LDAPAuth
from models.usuarios_model import UsuarioModel
from flask_login import login_user
import bcrypt
import logging

logger = logging.getLogger(__name__)

class AuthService:
    """
    Servicio centralizado de autenticación
    Prioriza LDAP, con fallback a base de datos local
    """
    
    def __init__(self):
        self.ad_auth = ADAuth()  # ✅ CORREGIDO: Instanciar ADAuth
    
    def authenticate(self, username, password, remember=False):
        """
        Autentica usuario usando LDAP primero, luego base de datos como fallback
        
        Args:
            username: Nombre de usuario
            password: Contraseña
            remember: Si debe recordar la sesión
            
        Returns:
            tuple: (success, user, message)
        """
        # 1. Intentar autenticación LDAP
        logger.info(f"🔐 Intentando autenticación LDAP para: {username}")
        
        try:
            user_data = self.ad_auth.authenticate_user(username, password)
            
            if user_data:
                logger.info(f"✅ LDAP: Autenticación exitosa para {username}")
                
                # Buscar o crear usuario en base de datos
                user = UsuarioModel.get_by_username(username)
                
                if not user:
                    logger.info(f"📝 Creando nuevo usuario desde LDAP: {username}")
                    # Crear nuevo usuario desde LDAP
                    user = UsuarioModel.create_from_ldap(user_data)
                else:
                    logger.info(f"🔄 Actualizando usuario existente desde LDAP: {username}")
                    # Actualizar información desde LDAP
                    user.update_from_ldap(user_data)
                
                # Login con Flask-Login (si está configurado)
                try:
                    login_user(user, remember=remember)
                except:
                    logger.warning("Flask-Login no está configurado, continuando sin login_user()")
                
                return True, user, "Autenticación LDAP exitosa"
        
        except Exception as ldap_error:
            logger.warning(f"⚠️ LDAP falló para {username}: {ldap_error}")
        
        # 2. Fallback a autenticación de base de datos local
        logger.info(f"🔄 Intentando autenticación local para {username}")
        
        try:
            user = UsuarioModel.get_by_username(username)
            
            if user and user.check_password(password):
                logger.info(f"✅ Autenticación local exitosa para {username}")
                
                # Login con Flask-Login (si está configurado)
                try:
                    login_user(user, remember=remember)
                except:
                    logger.warning("Flask-Login no está configurado, continuando sin login_user()")
                
                return True, user, "Autenticación local exitosa"
        
        except Exception as db_error:
            logger.error(f"❌ Error en autenticación local: {db_error}")
        
        # 3. Autenticación fallida
        logger.warning(f"❌ Autenticación fallida para {username}")
        return False, None, "Credenciales inválidas"
    
    def test_ldap_connection(self):
        """
        Prueba la conexión al servidor LDAP
        
        Returns:
            bool: True si la conexión es exitosa
        """
        try:
            return self.ad_auth.test_connection()
        except Exception as e:
            logger.error(f"❌ Error probando conexión LDAP: {e}")
            return False
    
    def search_ldap_users(self, search_term):
        """
        Busca usuarios en LDAP
        
        Args:
            search_term: Término de búsqueda
            
        Returns:
            list: Lista de usuarios encontrados
        """
        try:
            return self.ad_auth.search_user_by_name(search_term)
        except Exception as e:
            logger.error(f"❌ Error buscando usuarios en LDAP: {e}")
            return []
