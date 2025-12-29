# config/ldap_config.py
"""
Configuración para conexión con Active Directory Qualitas Colombia
"""

# Configuración LDAP
LDAP_SERVER = '10.60.0.30'  # IP del servidor AD
LDAP_PORT = 389
LDAP_DOMAIN = 'qualitascolombia.com.co'
LDAP_SEARCH_BASE = 'DC=qualitascolombia,DC=com,DC=co'

# Credenciales de servicio para búsquedas
LDAP_SERVICE_USER = 'userauge'
LDAP_SERVICE_PASSWORD = 'QC4ug3*24'

# Configuración de mapeo de roles AD -> Sistema
AD_ROLE_MAPPING = {
    'administrador': ['gerencia', 'admin', 'administrador'],
    'lider_inventario': ['almacen', 'logistica', 'inventario'],
    'tesoreria': ['contabilidad', 'tesoreria'],
}

# Timeout en segundos
LDAP_CONNECTION_TIMEOUT = 10