# utils/permissions_functions.py
"""
Funciones de permisos para templates de solicitudes y novedades.
Controla la visibilidad de botones seg煤n rol y estado de solicitud.
"""

from flask import session
import logging

logger = logging.getLogger(__name__)

# ============================================================================
# ROLES CON PERMISOS COMPLETOS (pueden aprobar/rechazar novedades y devoluciones)
# ============================================================================
ROLES_GESTION_COMPLETA = ['administrador', 'lider_inventario', 'aprobador']

# ============================================================================
# ROLES DE OFICINA (pueden crear novedades, devolver, ver detalles)
# ============================================================================
ROLES_OFICINA = [
    'oficina_coq', 'oficina_cali', 'oficina_pereira', 'oficina_neiva',
    'oficina_kennedy', 'oficina_bucaramanga', 'oficina_polo_club',
    'oficina_nogal', 'oficina_tunja', 'oficina_cartagena', 'oficina_morato',
    'oficina_medellin', 'oficina_cedritos', 'oficina_lourdes', 'oficina_regular'
]


def get_user_role():
    """Obtiene el rol del usuario actual en min煤sculas"""
    rol = session.get('rol', '').lower()
    logger.debug(f"馃攼 get_user_role: '{rol}'")
    return rol


def has_gestion_completa():
    """Verifica si el usuario tiene permisos de gesti贸n completa"""
    rol = get_user_role()
    result = rol in ROLES_GESTION_COMPLETA
    logger.debug(f"馃攼 has_gestion_completa: rol='{rol}', result={result}")
    return result


def is_oficina_role():
    """Verifica si el usuario tiene rol de oficina"""
    rol = get_user_role()
    result = rol in ROLES_OFICINA
    logger.debug(f"馃攼 is_oficina_role: rol='{rol}', result={result}")
    return result


def can_create_or_view():
    """Verifica si el usuario puede crear novedades o ver detalles"""
    rol = get_user_role()
    result = rol in ROLES_GESTION_COMPLETA or rol in ROLES_OFICINA
    logger.debug(f"馃攼 can_create_or_view: rol='{rol}', result={result}")
    return result


# ============================================================================
# FUNCIONES should_show_* PARA TEMPLATES
# ============================================================================

def should_show_devolucion_button(solicitud):
    """
    Determina si mostrar el bot贸n de devoluci贸n.
    
    Estados permitidos: 2 (Aprobada), 4 (Entregada Parcial), 5 (Completada)
    """
    if not solicitud:
        logger.debug("馃敶 should_show_devolucion_button: solicitud es None")
        return False
    
    # Verificar permisos
    if not can_create_or_view():
        logger.debug("馃敶 should_show_devolucion_button: sin permisos can_create_or_view")
        return False
    
    # Verificar estado
    estado_id = solicitud.get('estado_id') or 1
    estados_permitidos = [2, 4, 5]
    
    if estado_id not in estados_permitidos:
        logger.debug(f"馃敶 should_show_devolucion_button: estado_id={estado_id} no en {estados_permitidos}")
        return False
    
    # Verificar cantidades
    cantidad_entregada = solicitud.get('cantidad_entregada', 0) or 0
    cantidad_devuelta = solicitud.get('cantidad_devuelta', 0) or 0
    
    result = cantidad_entregada > cantidad_devuelta
    logger.debug(f"馃煝 should_show_devolucion_button: estado_id={estado_id}, entregada={cantidad_entregada}, devuelta={cantidad_devuelta}, result={result}")
    return result


def should_show_novedad_button(solicitud):
    """
    Determina si mostrar el bot贸n de crear novedad.
    
    Estados permitidos: 2 (Aprobada), 4 (Entregada Parcial), 5 (Completada)
    NO mostrar si ya tiene novedad (estados 7, 8, 9)
    """
    if not solicitud:
        logger.debug("馃敶 should_show_novedad_button: solicitud es None")
        return False
    
    if not can_create_or_view():
        logger.debug("馃敶 should_show_novedad_button: sin permisos can_create_or_view")
        return False
    
    estado_id = solicitud.get('estado_id') or 1
    estados_permitidos = [2, 4, 5]
    estados_con_novedad = [7, 8, 9]
    
    if estado_id in estados_con_novedad:
        logger.debug(f"馃敶 should_show_novedad_button: estado_id={estado_id} ya tiene novedad")
        return False
    
    result = estado_id in estados_permitidos
    logger.debug(f"馃煝 should_show_novedad_button: estado_id={estado_id}, result={result}")
    return result


def should_show_gestion_novedad_button(solicitud):
    """
    Determina si mostrar el bot贸n de gestionar novedad (aprobar/rechazar).
    
    SOLO roles con gesti贸n completa, estado 7 (Novedad Registrada)
    """
    if not solicitud:
        logger.debug("馃敶 should_show_gestion_novedad_button: solicitud es None")
        return False
    
    if not has_gestion_completa():
        logger.debug("馃敶 should_show_gestion_novedad_button: sin gesti贸n completa")
        return False
    
    estado_id = solicitud.get('estado_id') or 1
    result = estado_id == 7
    logger.debug(f"馃煝 should_show_gestion_novedad_button: estado_id={estado_id}, result={result}")
    return result


def should_show_aprobacion_buttons(solicitud):
    """
    Determina si mostrar los botones de aprobaci贸n/rechazo de SOLICITUDES.
    
    SOLO roles con gesti贸n completa, estado 1 (Pendiente)
    """
    if not solicitud:
        logger.debug("馃敶 should_show_aprobacion_buttons: solicitud es None")
        return False
    
    if not has_gestion_completa():
        logger.debug(f"馃敶 should_show_aprobacion_buttons: sin gesti贸n completa (rol={get_user_role()})")
        return False
    
    estado_id = solicitud.get('estado_id') or 1
    result = estado_id == 1
    logger.debug(f"馃煝 should_show_aprobacion_buttons: estado_id={estado_id}, result={result}")
    return result


def should_show_detalle_button(solicitud):
    """Determina si mostrar el bot贸n de ver detalles - TODOS los roles pueden ver"""
    if solicitud is None:
        return False
    return can_create_or_view()


# ============================================================================
# FUNCIONES ADICIONALES DE PERMISOS
# ============================================================================

def can_approve_novedad():
    """Verifica si el usuario puede aprobar novedades"""
    return has_gestion_completa()


def can_reject_novedad():
    """Verifica si el usuario puede rechazar novedades"""
    return has_gestion_completa()


def can_manage_novedades():
    """Verifica si el usuario puede gestionar novedades"""
    return has_gestion_completa()


def can_view_all_novedades():
    """Verifica si el usuario puede ver todas las novedades"""
    return has_gestion_completa()


def can_create_novedad_check():
    """Verifica si el usuario puede crear novedades"""
    return can_create_or_view()


def can_devolucion_check():
    """Verifica si el usuario puede registrar devoluciones"""
    return can_create_or_view()


# ============================================================================
# DICCIONARIO DE FUNCIONES PARA INYECTAR EN TEMPLATES
# ============================================================================
PERMISSION_FUNCTIONS = {
    # Funciones para mostrar botones
    'should_show_devolucion_button': should_show_devolucion_button,
    'should_show_novedad_button': should_show_novedad_button,
    'should_show_gestion_novedad_button': should_show_gestion_novedad_button,
    'should_show_aprobacion_buttons': should_show_aprobacion_buttons,
    'should_show_detalle_button': should_show_detalle_button,
    
    # Funciones de verificaci贸n de permisos
    'has_gestion_completa': has_gestion_completa,
    'is_oficina_role': is_oficina_role,
    'can_create_or_view': can_create_or_view,
    'can_approve_novedad': can_approve_novedad,
    'can_reject_novedad': can_reject_novedad,
    'can_manage_novedades': can_manage_novedades,
    'can_view_all_novedades': can_view_all_novedades,
    'can_create_novedad_check': can_create_novedad_check,
    'can_devolucion_check': can_devolucion_check,
    'get_user_role': get_user_role,
}
