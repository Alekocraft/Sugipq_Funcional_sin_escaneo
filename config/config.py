# -*- coding: utf-8 -*-
import os
from datetime import timedelta

class Config:
    """Configuración base para toda la aplicación"""
    
    # Clave secreta
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    
    # Configuración de Flask
    JSON_AS_ASCII = False
    TEMPLATES_AUTO_RELOAD = True
    SESSION_COOKIE_SECURE = False 
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)
    
    
    # Uploads
    UPLOAD_FOLDER = 'static/uploads'
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'doc', 'docx', 'xls', 'xlsx'}
    
    # Rutas
    BASE_DIR = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
    TEMPLATE_FOLDER = os.path.join(BASE_DIR, 'templates')
    STATIC_FOLDER = os.path.join(BASE_DIR, 'static')
    
    # Configuración de roles y permisos
    ROLES = {
        'administrador': ['dashboard', 'materiales', 'solicitudes', 'oficinas', 'aprobadores', 'reportes', 'inventario_corporativo', 'prestamos'],
        'lider_inventario': ['dashboard', 'materiales', 'solicitudes', 'oficinas', 'aprobadores', 'reportes', 'inventario_corporativo', 'prestamos'],
        'oficina_principal': ['dashboard', 'materiales', 'solicitudes'],
        'aprobador': ['dashboard', 'solicitudes'],
        'tesoreria': ['dashboard', 'reportes'],
        'inventario_corporativo': ['dashboard', 'inventario_corporativo']
    }
    
    # Configuración LDAP
    LDAP_ENABLED = True
    LDAP_SERVER = '10.60.0.30'
    LDAP_DOMAIN = 'qualitascolombia.com.co'
    LDAP_SEARCH_BASE = 'DC=qualitascolombia,DC=com,DC=co'
    LDAP_SERVICE_USER = 'userauge'
    LDAP_SERVICE_PASSWORD = 'QC4ug3*24'
    
    # Fallback a autenticación local si LDAP falla
    LDAP_FALLBACK_LOCAL = True


class DevelopmentConfig(Config):
    """Configuración para desarrollo"""
    DEBUG = True
    TESTING = False
    ENV = 'development'


class ProductionConfig(Config):
    """Configuración para producción"""
    DEBUG = False
    TESTING = False
    ENV = 'production'
    
    # Seguridad en producción
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True


class TestingConfig(Config):
    """Configuración para testing"""
    DEBUG = True
    TESTING = True
    ENV = 'testing'
    WTF_CSRF_ENABLED = False


# Configuración por entorno
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}