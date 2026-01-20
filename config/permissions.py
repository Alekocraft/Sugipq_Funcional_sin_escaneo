# -*- coding: utf-8 -*-
# config/permissions.py
"""
Sistema centralizado de permisos basado en roles y oficinas.

✅ Objetivos del ajuste (sin romper funcionalidades existentes):
- Mantener accesos actuales (reportes, préstamos, solicitudes, etc.)
- Habilitar a TODAS las oficinas (roles que comienzan por `oficina_`) el acceso mínimo a:
    /inventario-corporativo/oficinas-servicio
  con acciones únicamente:
    - solicitar devolución
    - solicitar traslado
- Evitar problemas por nombres “alias” de módulos (p.ej. `prestamo_material` vs `prestamos`,
  `material_pop` vs `materiales`), para que los botones del dashboard y los templates funcionen.
"""

from __future__ import annotations

from typing import Dict, List, Optional

# --------------------------------------------------------------------------------------
# PERMISOS POR ROL
# --------------------------------------------------------------------------------------

ROLE_PERMISSIONS: Dict[str, dict] = {
    'administrador': {
        'modules': [
            'dashboard', 'material_pop', 'inventario_corporativo', 'prestamo_material',
            'reportes', 'solicitudes', 'oficinas', 'novedades'
        ],
        'actions': {
            'materiales': ['view', 'create', 'edit', 'delete'],
            'solicitudes': ['view', 'create', 'edit', 'delete', 'approve', 'reject', 'partial_approve', 'return'],
            'oficinas': ['view', 'manage'],
            'aprobadores': ['view', 'manage'],
            'reportes': ['view_all'],

            # Inventario corporativo (administrador = todo)
            'inventario_corporativo': [
                'view', 'create', 'edit', 'delete', 'assign',
                'manage_sedes', 'manage_oficinas',

                # extras (para no perder opciones de UI existentes)
                'view_oficinas_servicio',
                'request_return', 'request_transfer',
                'create_devolucion', 'create_devolucion_coq',
                'manage_devoluciones', 'approve_devolucion', 'reject_devolucion',
                'create_traslado', 'manage_traslados', 'approve_traslado', 'reject_traslado',
            ],

            'prestamos': ['view', 'create', 'approve', 'reject', 'return', 'manage_materials'],
            'novedades': ['create', 'view', 'manage', 'approve', 'reject']
        },
        'office_filter': 'all'
    },

    'lider_inventario': {
        'modules': [
            'dashboard', 'material_pop', 'inventario_corporativo', 'prestamo_material',
            'reportes', 'solicitudes', 'oficinas', 'novedades'
        ],
        'actions': {
            'materiales': ['view', 'create', 'edit', 'delete'],
            'solicitudes': ['view', 'create', 'edit', 'delete', 'approve', 'reject', 'partial_approve', 'return'],
            'oficinas': ['view'],
            'aprobadores': ['view'],
            'reportes': ['view_all'],
            'inventario_corporativo': [
                'view', 'create', 'edit', 'delete', 'assign', 'manage_sedes', 'manage_oficinas',
                'view_oficinas_servicio',
                'request_return', 'request_transfer',
                'create_devolucion', 'create_devolucion_coq',
                'manage_devoluciones', 'approve_devolucion', 'reject_devolucion',
                'create_traslado', 'manage_traslados', 'approve_traslado', 'reject_traslado',
            ],
            'prestamos': ['view', 'create', 'approve', 'reject', 'return', 'manage_materials'],
            'novedades': ['create', 'view', 'manage', 'approve', 'reject']
        },
        'office_filter': 'all'
    },

    'aprobador': {
        'modules': [
            'dashboard', 'material_pop', 'inventario_corporativo', 'prestamo_material',
            'reportes', 'solicitudes', 'oficinas', 'novedades'
        ],
        'actions': {
            'materiales': ['view'],
            'solicitudes': ['view', 'create', 'edit', 'delete', 'approve', 'reject', 'partial_approve', 'return'],
            'oficinas': ['view'],
            'aprobadores': ['view'],
            'reportes': ['view_all'],
            'inventario_corporativo': [
                'view',
                'view_oficinas_servicio',
                'request_return', 'request_transfer',
                'manage_devoluciones', 'manage_traslados'
            ],
            'prestamos': ['view', 'create', 'approve', 'reject', 'return'],
            'novedades': ['create', 'view', 'manage', 'approve', 'reject']
        },
        'office_filter': 'all'
    },

    'tesoreria': {
        'modules': ['dashboard', 'material_pop', 'inventario_corporativo', 'prestamo_material', 'reportes'],
        'actions': {
            'materiales': [],
            'solicitudes': ['view'],
            'oficinas': ['view'],
            'aprobadores': ['view'],
            'reportes': ['view_all'],
            'inventario_corporativo': ['view', 'view_oficinas_servicio'],
            'prestamos': ['view'],
            'novedades': ['view']
        },
        'office_filter': 'all'
    },

    # --------------------------
    # OFICINAS (se complementan automáticamente más abajo con permisos mínimos
    # de inventario corporativo -> oficinas-servicio)
    # --------------------------

    'oficina_coq': {
        'modules': ['dashboard', 'material_pop', 'prestamo_material', 'reportes', 'oficinas', 'solicitudes', 'novedades'],
        'actions': {
            'materiales': [],
            'solicitudes': ['view', 'create', 'return'],
            'oficinas': ['view'],
            'aprobadores': ['view'],
            'prestamos': ['view_own', 'create'],
            'reportes': ['view_own'],
            'novedades': ['create', 'view', 'return']
        },
        'office_filter': 'COQ'
    },

    'oficina_cali': {
        'modules': ['dashboard', 'material_pop', 'prestamo_material', 'reportes', 'oficinas', 'solicitudes', 'novedades'],
        'actions': {
            'materiales': [],
            'solicitudes': ['view', 'create', 'return'],
            'oficinas': ['view'],
            'aprobadores': ['view'],
            'prestamos': ['view_own', 'create'],
            'reportes': ['view_own'],
            'novedades': ['create', 'view', 'return']
        },
        'office_filter': 'CALI'
    },

    'oficina_pereira': {
        'modules': ['dashboard', 'material_pop', 'prestamo_material', 'reportes', 'oficinas', 'solicitudes', 'novedades'],
        'actions': {
            'materiales': [],
            'solicitudes': ['view', 'create', 'return'],
            'oficinas': ['view'],
            'aprobadores': ['view'],
            'prestamos': ['view_own', 'create'],
            'reportes': ['view_own'],
            'novedades': ['create', 'view', 'return']
        },
        'office_filter': 'PEREIRA'
    },

    'oficina_neiva': {
        'modules': ['dashboard', 'material_pop', 'prestamo_material', 'reportes', 'oficinas', 'solicitudes', 'novedades'],
        'actions': {
            'materiales': [],
            'solicitudes': ['view', 'create', 'return'],
            'oficinas': ['view'],
            'aprobadores': ['view'],
            'prestamos': ['view_own', 'create'],
            'reportes': ['view_own'],
            'novedades': ['create', 'view', 'return']
        },
        'office_filter': 'NEIVA'
    },

    'oficina_kennedy': {
        'modules': ['dashboard', 'material_pop', 'prestamo_material', 'reportes', 'oficinas', 'solicitudes', 'novedades'],
        'actions': {
            'materiales': [],
            'solicitudes': ['view', 'create', 'return'],
            'oficinas': ['view'],
            'aprobadores': ['view'],
            'prestamos': ['view_own', 'create'],
            'reportes': ['view_own'],
            'novedades': ['create', 'view', 'return']
        },
        'office_filter': 'KENNEDY'
    },

    'oficina_bucaramanga': {
        'modules': ['dashboard', 'material_pop', 'prestamo_material', 'reportes', 'oficinas', 'solicitudes', 'novedades'],
        'actions': {
            'materiales': [],
            'solicitudes': ['view', 'create', 'return'],
            'oficinas': ['view'],
            'aprobadores': ['view'],
            'prestamos': ['view_own', 'create'],
            'reportes': ['view_own'],
            'novedades': ['create', 'view', 'return']
        },
        'office_filter': 'BUCARAMANGA'
    },

    'oficina_polo_club': {
        'modules': ['dashboard', 'material_pop', 'prestamo_material', 'reportes', 'oficinas', 'solicitudes', 'novedades'],
        'actions': {
            'materiales': [],
            'solicitudes': ['view', 'create', 'return'],
            'oficinas': ['view'],
            'aprobadores': ['view'],
            'prestamos': ['view_own', 'create'],
            'reportes': ['view_own'],
            'novedades': ['create', 'view', 'return']
        },
        'office_filter': 'POLO CLUB'
    },

    'oficina_nogal': {
        'modules': ['dashboard', 'material_pop', 'prestamo_material', 'reportes', 'oficinas', 'solicitudes', 'novedades'],
        'actions': {
            'materiales': [],
            'solicitudes': ['view', 'create', 'return'],
            'oficinas': ['view'],
            'aprobadores': ['view'],
            'prestamos': ['view_own', 'create'],
            'reportes': ['view_own'],
            'novedades': ['create', 'view', 'return']
        },
        'office_filter': 'NOGAL'
    },

    'oficina_tunja': {
        'modules': ['dashboard', 'material_pop', 'prestamo_material', 'reportes', 'oficinas', 'solicitudes', 'novedades'],
        'actions': {
            'materiales': [],
            'solicitudes': ['view', 'create', 'return'],
            'oficinas': ['view'],
            'aprobadores': ['view'],
            'prestamos': ['view_own', 'create'],
            'reportes': ['view_own'],
            'novedades': ['create', 'view', 'return']
        },
        'office_filter': 'TUNJA'
    },

    'oficina_cartagena': {
        'modules': ['dashboard', 'material_pop', 'prestamo_material', 'reportes', 'oficinas', 'solicitudes', 'novedades'],
        'actions': {
            'materiales': [],
            'solicitudes': ['view', 'create', 'return'],
            'oficinas': ['view'],
            'aprobadores': ['view'],
            'prestamos': ['view_own', 'create'],
            'reportes': ['view_own'],
            'novedades': ['create', 'view', 'return']
        },
        'office_filter': 'CARTAGENA'
    },

    'oficina_morato': {
        'modules': ['dashboard', 'material_pop', 'prestamo_material', 'reportes', 'oficinas', 'solicitudes', 'novedades'],
        'actions': {
            'materiales': [],
            'solicitudes': ['view', 'create', 'return'],
            'oficinas': ['view'],
            'aprobadores': ['view'],
            'prestamos': ['view_own', 'create'],
            'reportes': ['view_own'],
            'novedades': ['create', 'view', 'return']
        },
        'office_filter': 'MORATO'
    },

    'oficina_medellin': {
        'modules': ['dashboard', 'material_pop', 'prestamo_material', 'reportes', 'oficinas', 'solicitudes', 'novedades'],
        'actions': {
            'materiales': [],
            'solicitudes': ['view', 'create', 'return'],
            'oficinas': ['view'],
            'aprobadores': ['view'],
            'prestamos': ['view_own', 'create'],
            'reportes': ['view_own'],
            'novedades': ['create', 'view', 'return']
        },
        'office_filter': 'MEDELLÍN'
    },

    'oficina_cedritos': {
        'modules': ['dashboard', 'material_pop', 'prestamo_material', 'reportes', 'oficinas', 'solicitudes', 'novedades'],
        'actions': {
            'materiales': [],
            'solicitudes': ['view', 'create', 'return'],
            'oficinas': ['view'],
            'aprobadores': ['view'],
            'prestamos': ['view_own', 'create'],
            'reportes': ['view_own'],
            'novedades': ['create', 'view', 'return']
        },
        'office_filter': 'CEDRITOS'
    },

    'oficina_lourdes': {
        'modules': ['dashboard', 'material_pop', 'prestamo_material', 'reportes', 'oficinas', 'solicitudes', 'novedades'],
        'actions': {
            'materiales': [],
            'solicitudes': ['view', 'create', 'return'],
            'oficinas': ['view'],
            'aprobadores': ['view'],
            'prestamos': ['view_own', 'create'],
            'reportes': ['view_own'],
            'novedades': ['create', 'view', 'return']
        },
        'office_filter': 'LOURDES'
    },

    # fallback genérico (si llega un rol oficina_* no definido)
    'oficina_regular': {
        'modules': ['dashboard', 'reportes', 'solicitudes', 'novedades', 'material_pop', 'prestamo_material'],
        'actions': {
            'solicitudes': ['view', 'create', 'return'],
            'reportes': ['view_own'],
            'prestamos': ['view_own', 'create'],
            'novedades': ['create', 'view', 'return'],
            'materiales': ['view']
        },
        'office_filter': 'own'
    }
}

# --------------------------------------------------------------------------------------
# COMPLEMENTO AUTOMÁTICO PARA TODAS LAS OFICINAS
# (no rompe reportes / préstamos, solo añade inventario mínimo)
# --------------------------------------------------------------------------------------

_MIN_INV_OFFICE_ACTIONS = ['view_oficinas_servicio', 'request_return', 'request_transfer']

for role, data in list(ROLE_PERMISSIONS.items()):
    if not role.startswith('oficina_'):
        continue

    modules = data.setdefault('modules', [])
    if 'inventario_corporativo' not in modules:
        modules.append('inventario_corporativo')

    actions = data.setdefault('actions', {})
    inv_actions = actions.setdefault('inventario_corporativo', [])

    # merge sin duplicar
    for a in _MIN_INV_OFFICE_ACTIONS:
        if a not in inv_actions:
            inv_actions.append(a)

# --------------------------------------------------------------------------------------
# ALIASES DE MÓDULOS (para compatibilidad con templates existentes)
# --------------------------------------------------------------------------------------

MODULE_ALIASES: Dict[str, List[str]] = {
    # Dashboard usa "prestamo_material" para mostrar tarjeta, pero acciones usan "prestamos"
    'prestamos': ['prestamo_material'],
    'prestamo_material': ['prestamos'],

    # Dashboard usa "material_pop" para módulo, pero acciones usan "materiales"
    'materiales': ['material_pop'],
    'material_pop': ['materiales'],
}

# --------------------------------------------------------------------------------------
# MAPEO DE OFICINAS (si lo usas en filtros)
# --------------------------------------------------------------------------------------

OFFICE_MAPPING = {
    'COQ': 'COQ',
    'POLO CLUB': 'POLO CLUB',
    'NOGAL': 'NOGAL',
    'TUNJA': 'TUNJA',
    'CARTAGENA': 'CARTAGENA',
    'MORATO': 'MORATO',
    'MEDELLÍN': 'MEDELLÍN',
    'CEDRITOS': 'CEDRITOS',
    'LOURDES': 'LOURDES',
    'CALI': 'CALI',
    'PEREIRA': 'PEREIRA',
    'NEIVA': 'NEIVA',
    'KENNEDY': 'KENNEDY',
    'BUCARAMANGA': 'BUCARAMANGA',
}

def get_office_key(office_name: str) -> str:
    """Normaliza el nombre de oficina y lo mapea si existe en OFFICE_MAPPING."""
    key = (office_name or '').upper().strip()
    return OFFICE_MAPPING.get(key, key)

# --------------------------------------------------------------------------------------
# HELPERS DE PERMISOS
# --------------------------------------------------------------------------------------

def _resolve_role(raw_role: str) -> str:
    role = (raw_role or '').lower().strip()
    if role in ROLE_PERMISSIONS:
        return role
    # Cualquier rol "oficina_*" no declarado cae al rol base
    if role.startswith('oficina_'):
        return 'oficina_regular'
    return role

def _candidate_permission_keys(module: str) -> List[str]:
    m = (module or '').strip()
    keys = [m]
    for alias in MODULE_ALIASES.get(m, []):
        if alias not in keys:
            keys.append(alias)
    return keys

def can_access(module: str, action: Optional[str] = None) -> bool:
    """Verifica si el usuario actual tiene acceso a un módulo/acción."""
    from flask import session

    if 'rol' not in session or 'usuario_id' not in session:
        return False

    rol = _resolve_role(session.get('rol', ''))
    permissions = ROLE_PERMISSIONS.get(rol)
    if not permissions:
        return False

    modules = permissions.get('modules', [])
    actions = permissions.get('actions', {})

    # Keys de compatibilidad
    keys = _candidate_permission_keys(module)

    # 1) Si no se pide acción, basta con estar en módulos (o ser alias) o estar definido en actions
    if action is None:
        if any(k in modules for k in keys):
            return True
        # compatibilidad: algunos templates consultan solo el módulo pero realmente se rigen por actions
        return any(k in actions for k in keys)

    # 2) Si se pide acción, buscamos el módulo (o alias) dentro de actions
    for k in keys:
        module_actions = actions.get(k, [])
        if action in module_actions:
            return True

    return False

def get_accessible_modules() -> List[str]:
    """Obtiene los módulos accesibles para el usuario actual."""
    from flask import session

    rol = _resolve_role(session.get('rol', ''))
    permissions = ROLE_PERMISSIONS.get(rol, {})
    modules = list(permissions.get('modules', []))

    # Añadir módulos alias que sean relevantes (para que no se “pierdan” botones del dashboard)
    # Ej: si tiene prestamo_material, considerar prestamos para checks simples.
    for m in list(modules):
        for alias in MODULE_ALIASES.get(m, []):
            if alias not in modules:
                modules.append(alias)

    return modules

def can_view_actions(module: str) -> List[str]:
    """Retorna acciones visibles para un módulo (o alias) para el usuario actual."""
    from flask import session

    rol = _resolve_role(session.get('rol', ''))
    permissions = ROLE_PERMISSIONS.get(rol, {})
    actions = permissions.get('actions', {})

    keys = _candidate_permission_keys(module)
    for k in keys:
        if k in actions:
            return actions.get(k, [])
    return []

def get_user_permissions() -> dict:
    """Obtiene todos los permisos del usuario actual."""
    from flask import session

    rol = _resolve_role(session.get('rol', ''))
    return ROLE_PERMISSIONS.get(rol, {'modules': [], 'actions': {}, 'office_filter': 'none'})

# --------------------------------------------------------------------------------------
# ACCESOS ESPECÍFICOS (solicitudes / novedades)
# --------------------------------------------------------------------------------------

def can_create_novedad() -> bool:
    return can_access('novedades', 'create')

def can_manage_novedad() -> bool:
    return can_access('novedades', 'manage')

def can_view_novedades() -> bool:
    return can_access('novedades', 'view')

def can_approve_novedad() -> bool:
    return can_access('novedades', 'approve')

def can_reject_novedad() -> bool:
    return can_access('novedades', 'reject')

def can_approve_solicitud() -> bool:
    return can_access('solicitudes', 'approve')

def can_approve_partial_solicitud() -> bool:
    return can_access('solicitudes', 'partial_approve')

def can_reject_solicitud() -> bool:
    return can_access('solicitudes', 'reject')

def can_return_solicitud() -> bool:
    return can_access('solicitudes', 'return')

# --------------------------------------------------------------------------------------
# INVENTARIO CORPORATIVO - helpers de lectura en templates
# --------------------------------------------------------------------------------------

def can_view_inventario_full() -> bool:
    """Acceso completo al inventario corporativo (listar general / sede principal)."""
    return can_access('inventario_corporativo', 'view')

def can_view_oficinas_servicio() -> bool:
    """Acceso mínimo para oficinas (solo oficinas-servicio)."""
    return can_access('inventario_corporativo', 'view_oficinas_servicio')

def can_request_devolucion_inventario() -> bool:
    return can_access('inventario_corporativo', 'request_return')

def can_request_traslado_inventario() -> bool:
    return can_access('inventario_corporativo', 'request_transfer')
