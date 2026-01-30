"""
utils/persmissions
Módulo de permisos para el sistema.
Wrapper para el PermissionManager con funciones específicas.
"""

import logging
from flask import session
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


# ==============================================
# PERMISSION MANAGER - Definición completa
# ==============================================

class PermissionManager:
    """Gestor centralizado de permisos de usuario"""
    
    @staticmethod
    def normalize_role_key(role_raw: str) -> str:
        """
        Normaliza el rol obtenido de sesión para que coincida con las claves definidas
        
        Args:
            role_raw: Rol en formato crudo desde la sesión
            
        Returns:
            str: Clave normalizada del rol para búsqueda en ROLE_PERMISSIONS
        """
        if not role_raw:
            logger.debug("Rol vacío recibido para normalización")
            return ''

        role = role_raw.strip().lower()
        
        # Normalización de caracteres especiales
        replacements = {
            'á': 'a', 'é': 'e', 'í': 'i', 'ó': 'o', 'ú': 'u',
            'ü': 'u', 'ñ': 'n'
        }
        
        for old, new in replacements.items():
            role = role.replace(old, new)
        
        role_normalized = role.replace(' ', '_')
        
        # Importar configuraciones de permisos
        try:
            from config.permissions import ROLE_PERMISSIONS
        except ImportError:
            logger.error("No se pudo importar ROLE_PERMISSIONS de config.permissions")
            return role_normalized
        
        # Búsqueda directa en permisos definidos
        if role_normalized in ROLE_PERMISSIONS:
            logger.debug(f"Rol encontrado directamente: {role_normalized}")
            return role_normalized
        
        # Búsqueda ignorando guiones bajos
        role_flat = role_normalized.replace('_', '')
        for key in ROLE_PERMISSIONS.keys():
            key_flat = key.replace('_', '')
            if role_flat == key_flat:
                logger.debug(f"Rol encontrado por comparación plana: {key}")
                return key
        
        # Detección por contenido específico
        # Ahora 'admin' se mapea a 'administrador'
        if 'admin' in role_normalized:
            logger.debug(f"Rol detectado como administrador: {role_raw}")
            return 'administrador'
        if 'lider' in role_normalized and 'invent' in role_normalized:
            logger.debug(f"Rol detectado como líder de inventario: {role_raw}")
            return 'lider_inventario'
        if 'tesorer' in role_normalized:
            logger.debug(f"Rol detectado como tesorería: {role_raw}")
            return 'tesoreria'
        if 'coq' in role_normalized:
            logger.debug(f"Rol detectado como oficina COQ: {role_raw}")
            return 'oficina_coq'
        
        logger.warning(f"Rol no reconocido: {role_raw}. Usando versión normalizada: {role_normalized}")
        return role_normalized
    
    @staticmethod
    def get_user_permissions() -> Dict[str, Any]:
        """
        Obtiene todos los permisos del usuario actual basados en rol y oficina
        
        Returns:
            dict: Permisos del usuario incluyendo rol, oficina y filtros
        """
        role_raw = session.get('rol', '')
        role_key = PermissionManager.normalize_role_key(role_raw)
        
        # Importar configuraciones
        try:
            from config.permissions import ROLE_PERMISSIONS, get_office_key
        except ImportError as e:
            logger.error("Error importando configuraciones: [error](%s)", type(e).__name__)
            return {
                'role_key': role_key,
                'role': {'modules': [], 'actions': {}, 'office_filter': 'own'},
                'office_key': '',
                'office_filter': 'own'
            }
        role_perms = ROLE_PERMISSIONS.get(role_key, {})

        # En config.permissions, los roles de oficina suelen venir con office_filter != 'all'.
        # Para consultas, normalizamos a:
        #   - office_filter='all'  -> sin filtro
        #   - office_filter='own'  -> filtrar por oficina_id de la sesión
        office_id = session.get('oficina_id')
        office_filter_cfg = role_perms.get('office_filter', 'all')

        if office_filter_cfg == 'all':
            office_filter = 'all'
            office_key = None
        else:
            office_filter = 'own'
            office_key = office_id

        permissions = {
            'role_key': role_key,
            'role': role_perms,
            'office_key': office_key,
            'office_filter': office_filter,
        }
        logger.debug(f"Permisos obtenidos para usuario: {permissions}")
        return permissions
    @staticmethod
    def has_module_access(module_name: str) -> bool:
        """Verifica si el usuario tiene acceso a un módulo completo"""
        perms = PermissionManager.get_user_permissions()
        role_modules = perms.get('role', {}).get('modules', [])

        module_norm = (module_name or '').strip().lower()
        module_aliases = {
            # alias UI -> clave usada en config.permissions['modules']
            'materiales': 'material_pop',
            'material_pop': 'material_pop',
            'prestamos': 'prestamo_material',
            'prestamo_material': 'prestamo_material',
        }
        candidates = {module_norm, module_aliases.get(module_norm, module_norm)}

        has_access = any(m in role_modules for m in candidates)
        logger.debug("Acceso a módulo '%s' (candidatos=%s): %s", module_name, list(candidates), has_access)
        return has_access

    @staticmethod
    def has_action_permission(module: str, action: str) -> bool:
        """Verifica permiso para acción específica en módulo"""
        perms = PermissionManager.get_user_permissions()
        role_actions = perms['role'].get('actions', {}).get(module, [])
        has_permission = action in role_actions
        logger.debug(f"Permiso para acción '{action}' en módulo '{module}': {has_permission}")
        return has_permission


# ==============================================
# FUNCIONES PRINCIPALES DE PERMISOS
# ==============================================

def can_access(module: str, action: Optional[str] = None) -> bool:
    """
    Función principal para verificar permisos.
    
    Args:
        module: Nombre del módulo
        action: Acción específica (opcional). Si no se especifica, verifica acceso al módulo completo.
    
    Returns:
        bool: True si tiene acceso, False de lo contrario
    """
    if action:
        # Verificar permiso para acción específica
        has_permission = PermissionManager.has_action_permission(module, action)
        logger.debug(f"can_access: {module}.{action} = {has_permission}")
        return has_permission
    else:
        # Verificar acceso al módulo completo
        has_access = PermissionManager.has_module_access(module)
        logger.debug(f"can_access: módulo {module} = {has_access}")
        return has_access


def can_view_actions() -> bool:
    """Determina si el usuario puede ver columnas de acciones en interfaces"""
    # Esta función debería verificar si el rol tiene permiso para ver acciones
    # Por ahora, asumimos que si tiene algún permiso de aprobación puede ver acciones
    return can_approve_solicitud() or can_manage_novedad() or can_return_solicitud()


def can_approve_partial_solicitud() -> bool:
    """Verifica permiso para aprobar parcialmente solicitudes"""
    can_partial = PermissionManager.has_action_permission('solicitudes', 'partial_approve')
    logger.debug(f"Usuario puede aprobar parcialmente solicitudes: {can_partial}")
    return can_partial


def can_return_solicitud() -> bool:
    """Verifica permiso para registrar devoluciones"""
    can_return = PermissionManager.has_action_permission('solicitudes', 'return')
    logger.debug(f"Usuario puede registrar devoluciones: {can_return}")
    return can_return


def can_manage_inventario_corporativo() -> bool:
    """Verifica permisos de gestión en inventario corporativo"""
    has_create = can_access('inventario_corporativo', 'create')
    has_edit = can_access('inventario_corporativo', 'edit')
    has_delete = can_access('inventario_corporativo', 'delete')
    can_manage = has_create or has_edit or has_delete
    logger.debug(f"Usuario puede gestionar inventario corporativo: {can_manage}")
    return can_manage


def can_view_inventario_actions() -> bool:
    """Verifica si puede ver acciones en inventario corporativo"""
    return can_manage_inventario_corporativo()


def should_show_materiales_menu() -> bool:
    """Determina si debe mostrar el menú de materiales en la interfaz"""
    should_show = can_access('materiales', 'view')
    logger.debug(f"Mostrar menú de materiales: {should_show}")
    return should_show


def get_visible_modules() -> list:
    """Obtiene lista de módulos visibles para el usuario actual"""
    perms = PermissionManager.get_user_permissions()
    all_modules = perms.get('role', {}).get('modules', [])
    
    visible_modules = []
    
    for module in all_modules:
        if module == 'materiales':
            if can_access('materiales', 'view'):
                visible_modules.append(module)
        elif module == 'inventario_corporativo':
            if can_access('inventario_corporativo', 'view'):
                visible_modules.append(module)
        else:
            visible_modules.append(module)
    
    logger.debug(f"Módulos visibles para usuario: {visible_modules}")
    return visible_modules


def get_accessible_modules() -> list:
    """Obtiene todos los módulos accesibles para el usuario"""
    perms = PermissionManager.get_user_permissions()
    modules = perms.get('role', {}).get('modules', [])
    logger.debug(f"Módulos accesibles para usuario: {modules}")
    return modules


def get_office_filter():
    """Obtiene filtro de oficina para consultas de base de datos

    Retorna:
        - None: sin filtro (usuario puede ver todas las oficinas)
        - 'own': filtrar por la oficina del usuario (ver utils/filters.py)
    """
    perms = PermissionManager.get_user_permissions()
    office_filter = perms.get('office_filter', 'own')

    if office_filter == 'all':
        logger.debug('Filtro de oficina: todas (sin filtro)')
        return None

    logger.debug('Filtro de oficina: own (oficina del usuario)')
    return 'own'


def user_can_view_all() -> bool:
    """Verifica si el usuario puede ver registros de todas las oficinas"""
    perms = PermissionManager.get_user_permissions()
    can_view_all = perms.get('office_filter') == 'all'
    logger.debug(f"Usuario puede ver todas las oficinas: {can_view_all}")
    return can_view_all


# ==============================================
# FUNCIONES DE PERMISOS ESPECÍFICOS (mantener las existentes)
# ==============================================

def can_create_solicitud() -> bool:
    """Verifica permiso para crear solicitudes"""
    can_create = PermissionManager.has_action_permission('solicitudes', 'create')
    logger.debug(f"Usuario puede crear solicitudes: {can_create}")
    return can_create


def can_create_novedad() -> bool:
    """Verifica permiso para crear novedades - TODOS los roles pueden crear"""
    perms = PermissionManager.get_user_permissions()
    role_key = perms.get('role_key', '')
    
    # TODOS los roles pueden crear novedades según la configuración en config/permissions.py
    # Verificar si el rol tiene la acción 'create' en el módulo 'novedades'
    can_create = PermissionManager.has_action_permission('novedades', 'create')
    
    if can_create:
        logger.debug(f"Rol {role_key} puede crear novedades")
        return True
    
    # También verificar acceso al módulo
    has_module_access = PermissionManager.has_module_access('novedades')
    logger.debug(f"Rol {role_key} tiene acceso al módulo novedades: {has_module_access}")
    
    return has_module_access


def can_manage_novedad() -> bool:
    """Verifica permiso para gestionar novedades (aprobar/rechazar)"""
    perms = PermissionManager.get_user_permissions()
    role_key = perms.get('role_key', '')
    
    # Solo estos roles pueden gestionar novedades según config/permissions.py
    roles_gestion_novedad = ['administrador', 'lider_inventario', 'aprobador']
    
    if role_key in roles_gestion_novedad:
        logger.debug(f"Rol {role_key} puede gestionar novedades")
        return True
    
    # También verificar permisos específicos
    can_approve = PermissionManager.has_action_permission('novedades', 'approve')
    can_reject = PermissionManager.has_action_permission('novedades', 'reject')
    can_manage = can_approve or can_reject
    
    logger.debug(f"Usuario puede gestionar novedades: {can_manage}")
    return can_manage


def can_view_novedades() -> bool:
    """Verifica permiso para ver novedades"""
    can_view = PermissionManager.has_action_permission('novedades', 'view')
    logger.debug(f"Usuario puede ver novedades: {can_view}")
    return can_view


def can_export_reports() -> bool:
    """Verifica permiso para exportar reportes"""
    perms = PermissionManager.get_user_permissions()
    role_modules = perms.get('role', {}).get('modules', [])
    can_export = 'reportes' in role_modules
    logger.debug(f"Usuario puede exportar reportes: {can_export}")
    return can_export


def can_edit_solicitud() -> bool:
    """Verifica permiso para editar solicitudes"""
    can_edit = PermissionManager.has_action_permission('solicitudes', 'edit')
    logger.debug(f"Usuario puede editar solicitudes: {can_edit}")
    return can_edit


def can_delete_solicitud() -> bool:
    """Verifica permiso para eliminar solicitudes"""
    can_delete = PermissionManager.has_action_permission('solicitudes', 'delete')
    logger.debug(f"Usuario puede eliminar solicitudes: {can_delete}")
    return can_delete


def can_approve_solicitud() -> bool:
    """Verifica permiso para aprobar solicitudes"""
    can_approve = PermissionManager.has_action_permission('solicitudes', 'approve')
    logger.debug(f"Usuario puede aprobar solicitudes: {can_approve}")
    return can_approve


def can_reject_solicitud() -> bool:
    """Verifica permiso para rechazar solicitudes"""
    can_reject = PermissionManager.has_action_permission('solicitudes', 'reject')
    logger.debug(f"Usuario puede rechazar solicitudes: {can_reject}")
    return can_reject


def can_view_reportes() -> bool:
    """Verifica permiso para ver reportes"""
    can_view = PermissionManager.has_action_permission('reportes', 'view')
    logger.debug(f"Usuario puede ver reportes: {can_view}")
    return can_view


def can_generate_reportes() -> bool:
    """Verifica permiso para generar reportes"""
    can_generate = PermissionManager.has_action_permission('reportes', 'generate')
    logger.debug(f"Usuario puede generar reportes: {can_generate}")
    return can_generate


def can_manage_usuarios() -> bool:
    """Verifica permiso para gestionar usuarios"""
    can_manage = PermissionManager.has_action_permission('usuarios', 'manage')
    logger.debug(f"Usuario puede gestionar usuarios: {can_manage}")
    return can_manage


def can_view_dashboard() -> bool:
    """Verifica permiso para ver el dashboard"""
    can_view = PermissionManager.has_action_permission('dashboard', 'view')
    logger.debug(f"Usuario puede ver dashboard: {can_view}")
    return can_view


def get_user_role() -> str:
    """Obtiene el rol del usuario actual"""
    perms = PermissionManager.get_user_permissions()
    role_key = perms.get('role_key', '')
    logger.debug(f"Rol del usuario: {role_key}")
    return role_key


def get_user_modules() -> list:
    """Obtiene los módulos disponibles para el usuario actual"""
    perms = PermissionManager.get_user_permissions()
    role_modules = perms.get('role', {}).get('modules', [])
    logger.debug(f"Módulos del usuario: {role_modules}")
    return role_modules


def has_module_access(module_name: str) -> bool:
    """Verifica si el usuario tiene acceso a un módulo específico"""
    modules = get_user_modules()
    has_access = module_name in modules
    logger.debug(f"Usuario tiene acceso a {module_name}: {has_access}")
    return has_access


# Funciones para verificar permisos específicos por módulo
def check_permission(module: str, action: str) -> bool:
    """Verifica un permiso específico de forma genérica"""
    has_perm = PermissionManager.has_action_permission(module, action)
    logger.debug(f"Permiso {action} en módulo {module}: {has_perm}")
    return has_perm


# Función de conveniencia para verificar múltiples permisos
def check_permissions(permissions_list: list) -> bool:
    """
    Verifica si el usuario tiene todos los permisos en la lista.
    
    Args:
        permissions_list: Lista de tuplas (módulo, acción)
    
    Returns:
        bool: True si tiene todos los permisos, False de lo contrario
    """
    for module, action in permissions_list:
        if not PermissionManager.has_action_permission(module, action):
            logger.debug(f"Falta permiso: {action} en {module}")
            return False
    logger.debug("Usuario tiene todos los permisos requeridos")
    return True


# Diccionario de funciones de permisos para fácil acceso
PERMISSION_FUNCTIONS = {
    'create_solicitud': can_create_solicitud,
    'create_novedad': can_create_novedad,
    'manage_novedad': can_manage_novedad,
    'view_novedades': can_view_novedades,
    'export_reports': can_export_reports,
    'edit_solicitud': can_edit_solicitud,
    'delete_solicitud': can_delete_solicitud,
    'approve_solicitud': can_approve_solicitud,
    'reject_solicitud': can_reject_solicitud,
    'view_reportes': can_view_reportes,
    'generate_reportes': can_generate_reportes,
    'manage_usuarios': can_manage_usuarios,
    'view_dashboard': can_view_dashboard,
    'approve_partial_solicitud': can_approve_partial_solicitud,
    'return_solicitud': can_return_solicitud,
    'can_access': can_access,
    'can_view_actions': can_view_actions,
}