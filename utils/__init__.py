# utils/__init__.py
"""
Paquete de utilidades del sistema
"""

# Exportar helpers
from .helpers import *

# Exportar otras utilidades si existen
try:
    from .filters import *
    from .permissions import *
    from .auth import *
    from .ldap_auth import *
    from .initialization import *
    from .permissions_functions import *
except ImportError:
    pass

# Lista de exportaciones
__all__ = [
    # Helpers
    'allowed_file', 'save_uploaded_file', 'get_user_permissions', 'can_access',
    'format_currency', 'format_date', 'get_pagination_params', 'flash_errors',
    'generate_codigo_unico', 'calcular_valor_total', 'validar_stock', 
    'obtener_mes_actual', 'sanitizar_email', 'sanitizar_username', 'sanitizar_ip',
]