# -*- coding: utf-8 -*-
"""config/permissions.py"""

from __future__ import annotations

from copy import deepcopy

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_office_key(role_key: str) -> str:
    """Retorna el filtro de oficina configurado para el rol.

    - 'all' => puede ver todas las oficinas
    - Cualquier otro string => se usa como filtro por oficina (p.ej. 'CALI')
    """
    role = (role_key or "").strip().lower()
    cfg = ROLE_PERMISSIONS.get(role)
    if not cfg:
        # Fallback: si es una oficina no registrada, aplica filtro por defecto
        if role.startswith("oficina_"):
            return "OFFICE_ONLY"
        return "all"
    return cfg.get("office_filter", "all")


# ---------------------------------------------------------------------------
# Plantillas base por tipo de rol
# ---------------------------------------------------------------------------

# Administrador: acceso total (incluye gestión de usuarios).
ADMIN_PERMS = {
    "modules": [
        "dashboard",
        "material_pop",
        "inventario_corporativo",
        "prestamo_material",
        "reportes",
        "solicitudes",
        "oficinas",
        "novedades",
        "usuarios",
        "aprobadores",
    ],
    "actions": {
        "materiales": ["view", "create", "edit", "delete"],
        "solicitudes": [
            "view",
            "create",
            "edit",
            "delete",
            "approve",
            "reject",
            "partial_approve",
            "return",
        ],
        "oficinas": ["view", "create", "edit", "delete"],
        "aprobadores": ["view", "create", "edit", "delete"],
        "prestamos": [
            "view",
            "view_all",
            "view_own",
            "create",
            "approve",
            "reject",
            "return",
            "manage_materials",
        ],
        "reportes": ["view_all", "view_own"],
        "inventario_corporativo": [
            "view",
            "create",
            "edit",
            "delete",
            "assign",
            "manage_sedes",
            "manage_oficinas",
            "manage_returns",
            "manage_transfers",
            "create_return",
            "create_transfer",
            "request_return",
            "request_transfer",
            "view_reports",
        ],
        "usuarios": ["view", "create", "edit", "delete"],
        "novedades": ["create", "view", "manage", "approve", "reject", "return"],
    },
    "office_filter": "all",
}

# Aprobador y Líder de inventario: aprobar solicitudes de todos los módulos,
# EXCEPTO gestión de usuarios. (pueden ver todo por oficina=all)
APPROVER_LIKE_PERMS = {
    "modules": [
        "dashboard",
        "material_pop",
        "inventario_corporativo",
        "prestamo_material",
        "reportes",
        "solicitudes",
        "oficinas",
        "novedades",
        "aprobadores",
    ],
    "actions": {
        "materiales": ["view"],
        "solicitudes": [
            "view",
            "create",
            "approve",
            "reject",
            "partial_approve",
            "return",
        ],
        "oficinas": ["view"],
        "aprobadores": ["view"],
        "prestamos": [
            "view",
            "view_all",
            "view_own",
            "create",
            "approve",
            "reject",
            "return",
            "manage_materials",
        ],
        "reportes": ["view_all"],
        # Inventario corporativo: acceso de gestión típico de inventario
        "inventario_corporativo": [
            "view",
            "create",
            "edit",
            "delete",
            "assign",
            "manage_sedes",
            "manage_oficinas",
            "manage_returns",
            "manage_transfers",
            "create_return",
            "create_transfer",
            "view_reports",
        ],
        "novedades": ["create", "view", "manage", "approve", "reject", "return"],
    },
    "office_filter": "all",
}

# Tesorería: solo reportes
TREASURY_PERMS = {
    "modules": ["dashboard", "reportes"],
    "actions": {"reportes": ["view_all"]},
    "office_filter": "all",
}

# Oficinas: modales separados (material pop, inventario corporativo, préstamos),
# y solo ven lo propio (office_filter específico)
OFFICE_BASE_PERMS = {
    "modules": [
        "dashboard",
        "material_pop",
        "inventario_corporativo",
        "prestamo_material",
        "reportes",
        "solicitudes",
        "novedades",
        "oficinas",
        "aprobadores",
    ],
    "actions": {
        # Material POP
        "materiales": [],
        "solicitudes": ["view", "create", "return"],
        "novedades": ["create", "view", "return"],
        "reportes": ["view_own"],
        "oficinas": ["view"],
        "aprobadores": ["view"],
        # Préstamos
        "prestamos": ["view_own", "create"],
        # Inventario corporativo
        "inventario_corporativo": ["view", "return", "transfer", "request_return", "request_transfer", "view_reports"],
    },
    "office_filter": "OFFICE_ONLY",
}


# ---------------------------------------------------------------------------
# ROLE_PERMISSIONS final
# ---------------------------------------------------------------------------

ROLE_PERMISSIONS = {
    "administrador": deepcopy(ADMIN_PERMS),
    "aprobador": deepcopy(APPROVER_LIKE_PERMS),
    "lider_inventario": deepcopy(APPROVER_LIKE_PERMS),
    "tesoreria": deepcopy(TREASURY_PERMS),
}

# Oficinas conocidas
OFFICE_FILTERS = {
    "oficina_coq": "COQ",
    "oficina_cali": "CALI",
    "oficina_pereira": "PEREIRA",
    "oficina_neiva": "NEIVA",
    "oficina_kennedy": "KENNEDY",
    "oficina_bucaramanga": "BUCARAMANGA",
    "oficina_barranquilla": "BARRANQUILLA",
    "oficina_cartagena": "CARTAGENA",
    "oficina_medellin": "MEDELLIN",
    "oficina_manizales": "MANIZALES",
    "oficina_armenia": "ARMENIA",
    "oficina_ibague": "IBAGUE",
    "oficina_villavicencio": "VILLAVICENCIO",
    "oficina_polo_club": "POLO CLUB",
}

for role_key, office_name in OFFICE_FILTERS.items():
    cfg = deepcopy(OFFICE_BASE_PERMS)
    cfg["office_filter"] = office_name
    ROLE_PERMISSIONS[role_key] = cfg
