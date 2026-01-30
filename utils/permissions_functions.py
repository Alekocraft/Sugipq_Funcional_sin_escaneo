# -*- coding: utf-8 -*-
# utils/permissions_functions.py
"""Funciones de permisos para templates de Solicitudes y Novedades.

Estas funciones controlan la visibilidad de botones en UI.
La seguridad REAL debe mantenerse en backend (decoradores / validaciones).
"""

from __future__ import annotations

from flask import session
from config.permissions import OFFICE_FILTERS
import logging

logger = logging.getLogger(__name__)

# ROLES CON PERMISOS COMPLETOS (pueden aprobar/rechazar, gestionar novedades/devoluciones)
ROLES_GESTION_COMPLETA = ['administrador', 'lider_inventario', 'aprobador']

# ROLES DE OFICINA (pueden crear novedades, solicitar devoluciones, ver detalles)
EXTRA_OFICINA_ROLES = ['gerencia_talento_humano','gerencia_comercial','comunicaciones','presidencia']

ROLES_OFICINA = sorted(list(OFFICE_FILTERS.keys()) + ['oficina_regular'] + EXTRA_OFICINA_ROLES)

def get_user_role() -> str:
    """Obtiene el rol del usuario actual en minúsculas."""
    rol = (session.get('rol') or '').lower()
    logger.debug("get_user_role: %s", rol)
    return rol


def has_gestion_completa() -> bool:
    """Verifica si el usuario tiene permisos de gestión completa."""
    rol = get_user_role()
    result = rol in ROLES_GESTION_COMPLETA
    logger.debug("has_gestion_completa: rol=%s result=%s", rol, result)
    return result


def is_oficina_role() -> bool:
    """Verifica si el usuario tiene rol de oficina."""
    rol = get_user_role()
    result = rol in ROLES_OFICINA or rol.startswith('oficina')
    logger.debug("is_oficina_role: rol=%s result=%s", rol, result)
    return result


def can_create_or_view() -> bool:
    """Puede crear novedades o ver detalles (roles gestión completa u oficina)."""
    rol = get_user_role()
    result = rol in ROLES_GESTION_COMPLETA or rol in ROLES_OFICINA or rol.startswith('oficina')
    logger.debug("can_create_or_view: rol=%s result=%s", rol, result)
    return result


# -----------------------------------------------------------------------------
# Funciones should_show_* para templates
# -----------------------------------------------------------------------------

def should_show_devolucion_button(solicitud: dict) -> bool:
    """Mostrar botón de devolución.

    Estados permitidos: 2 (Aprobada), 4 (Entregada Parcial), 5 (Completada)
    y que exista saldo para devolver.
    """
    if not solicitud:
        return False

    if not can_create_or_view():
        return False

    estado_id = solicitud.get('estado_id') or 1
    if estado_id not in (2, 4, 5):
        return False

    cantidad_entregada = solicitud.get('cantidad_entregada', 0) or 0
    cantidad_devuelta = solicitud.get('cantidad_devuelta', 0) or 0

    result = cantidad_entregada > cantidad_devuelta
    logger.debug(
        "should_show_devolucion_button: estado_id=%s entregada=%s devuelta=%s result=%s",
        estado_id, cantidad_entregada, cantidad_devuelta, result
    )
    return result


def should_show_gestion_devolucion_button(solicitud: dict) -> bool:
    """Mostrar botón de gestionar devolución.

    Requiere gestión completa (admin/líder/aprobador) y que exista una devolución pendiente.
    """
    if not solicitud:
        return False

    if not has_gestion_completa():
        return False

    solicitud_id = solicitud.get('id') or solicitud.get('solicitud_id')
    if not solicitud_id:
        return False

    # Intentar validar contra el modelo (si está disponible)
    try:
        from models.solicitudes_model import SolicitudModel
        result = bool(SolicitudModel.tiene_devolucion_pendiente(int(solicitud_id)))
        logger.debug("should_show_gestion_devolucion_button: solicitud_id=%s result=%s", solicitud_id, result)
        return result
    except Exception as e:
        # Fallback: si viene marcado desde el backend, úsalo.
        fallback = bool(solicitud.get('devolucion_pendiente'))
        logger.debug(
            "should_show_gestion_devolucion_button fallback: solicitud_id=%s devolucion_pendiente=%s err=%s",
            solicitud_id, fallback, e
        )
        return fallback


def should_show_novedad_button(solicitud: dict) -> bool:
    """Mostrar botón de crear novedad.

    Estados permitidos: 2, 4, 5. No mostrar si ya está en estados con novedad (7,8,9).
    """
    if not solicitud:
        return False

    if not can_create_or_view():
        return False

    estado_id = solicitud.get('estado_id') or 1

    if estado_id in (7, 8, 9):
        return False

    result = estado_id in (2, 4, 5)
    logger.debug("should_show_novedad_button: estado_id=%s result=%s", estado_id, result)
    return result


def should_show_gestion_novedad_button(solicitud: dict) -> bool:
    """Mostrar botón de gestionar novedad (aprobar/rechazar). Solo gestión completa, estado 7."""
    if not solicitud:
        return False

    if not has_gestion_completa():
        return False

    estado_id = solicitud.get('estado_id') or 1
    result = estado_id == 7
    logger.debug("should_show_gestion_novedad_button: estado_id=%s result=%s", estado_id, result)
    return result


def should_show_aprobacion_buttons(solicitud: dict) -> bool:
    """Mostrar botones de aprobar/rechazar solicitudes. Solo gestión completa, estado 1."""
    if not solicitud:
        return False

    if not has_gestion_completa():
        return False

    estado_id = solicitud.get('estado_id') or 1
    result = estado_id == 1
    logger.debug("should_show_aprobacion_buttons: estado_id=%s result=%s", estado_id, result)
    return result


def should_show_detalle_button(solicitud: dict) -> bool:
    """Mostrar botón de ver detalle."""
    return solicitud is not None and can_create_or_view()


# -----------------------------------------------------------------------------
# Compatibilidad: diccionario inyectable en templates
# -----------------------------------------------------------------------------

PERMISSION_FUNCTIONS = {
    'should_show_devolucion_button': should_show_devolucion_button,
    'should_show_gestion_devolucion_button': should_show_gestion_devolucion_button,
    'should_show_novedad_button': should_show_novedad_button,
    'should_show_gestion_novedad_button': should_show_gestion_novedad_button,
    'should_show_aprobacion_buttons': should_show_aprobacion_buttons,
    'should_show_detalle_button': should_show_detalle_button,

    'has_gestion_completa': has_gestion_completa,
    'is_oficina_role': is_oficina_role,
    'can_create_or_view': can_create_or_view,
    'get_user_role': get_user_role,
}
