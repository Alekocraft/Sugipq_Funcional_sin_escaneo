# -*- coding: utf-8 -*-
from flask import Blueprint, request, session, flash, redirect
from models.solicitudes_model import SolicitudModel
from utils.filters import verificar_acceso_oficina
import logging
import os
from services.notification_service import NotificationService
from utils.helpers import sanitizar_log_text

logger = logging.getLogger(__name__)

NOTIFICACIONES_ACTIVAS = os.getenv('NOTIFICATIONS_ENABLED', 'true').strip().lower() not in ('0','false','no','n')

aprobacion_bp = Blueprint('aprobacion', __name__)

def _usuario_gestion_desde_sesion():
    return (
        session.get('username')
        or session.get('usuario')
        or session.get('usuario_ad')
        or session.get('nombre_usuario')
        or str(session.get('usuario_id', ''))
    )


@aprobacion_bp.route('/solicitudes/aprobar/<int:solicitud_id>', methods=['POST'])
def aprobar_solicitud(solicitud_id):
    if 'usuario_id' not in session:
        return redirect('/login')

    rol = session.get('rol', '')
    if rol == 'tesorería':
        flash('No tiene permisos para acceder a esta sección.', 'danger')
        return redirect('/reportes')

    try:
        solicitud = SolicitudModel.obtener_por_id(solicitud_id)
        if not solicitud or not verificar_acceso_oficina(solicitud.get('oficina_id')):
            flash('No tiene permisos para aprobar esta solicitud.', 'danger')
            return redirect('/solicitudes')

        usuario_id = session['usuario_id']
        success, message = SolicitudModel.aprobar(solicitud_id, usuario_id)
        if success:
            flash(message, 'success')
            if NOTIFICACIONES_ACTIVAS:
                try:
                    info = SolicitudModel.obtener_por_id(solicitud_id) or {}
                    info['id'] = solicitud_id
                    ok = NotificationService.notificar_cambio_estado_solicitud(
                        info,
                        estado_anterior=str(info.get('estado') or info.get('Estado') or ''),
                        estado_nuevo="APROBADA",
                        usuario_gestion=_usuario_gestion_desde_sesion(),
                        observaciones=None,
                    )
                    if ok:
                        logger.info("📧 Notificación OK: solicitud %s -> APROBADA", solicitud_id)
                    else:
                        logger.warning("📧 Notificación FAIL: solicitud %s -> APROBADA", solicitud_id)
                except Exception:
                    logger.exception("Error enviando notificación de APROBADA (solicitud %s)", solicitud_id)
        else:
            flash(message, 'danger')
    except Exception as e:
        logger.error("❌ Error aprobando solicitud: %s", sanitizar_log_text('Error interno'))
        flash('Error al aprobar la solicitud.', 'danger')
    return redirect('/solicitudes')

@aprobacion_bp.route('/solicitudes/aprobar_parcial/<int:solicitud_id>', methods=['POST'])
def aprobar_parcial_solicitud(solicitud_id):
    if 'usuario_id' not in session:
        return redirect('/login')

    rol = session.get('rol', '')
    if rol == 'tesorería':
        flash('No tiene permisos para acceder a esta sección.', 'danger')
        return redirect('/reportes')

    try:
        solicitud = SolicitudModel.obtener_por_id(solicitud_id)
        if not solicitud or not verificar_acceso_oficina(solicitud.get('oficina_id')):
            flash('No tiene permisos para aprobar esta solicitud.', 'danger')
            return redirect('/solicitudes')

        usuario_id = session['usuario_id']
        cantidad_aprobada = int(request.form.get('cantidad_aprobada', 0))

        if cantidad_aprobada <= 0:
            flash('La cantidad aprobada debe ser mayor que 0.', 'danger')
            return redirect('/solicitudes')

        success, message = SolicitudModel.aprobar_parcial(solicitud_id, usuario_id, cantidad_aprobada)
        if success:
            flash(message, 'success')
            if NOTIFICACIONES_ACTIVAS:
                try:
                    info = SolicitudModel.obtener_por_id(solicitud_id) or {}
                    info['id'] = solicitud_id
                    ok = NotificationService.notificar_cambio_estado_solicitud(
                        info,
                        estado_anterior=str(info.get('estado') or info.get('Estado') or ''),
                        estado_nuevo="APROBACIÓN PARCIAL",
                        usuario_gestion=_usuario_gestion_desde_sesion(),
                        observaciones=f"Cantidad aprobada: {cantidad_aprobada}",
                    )
                    if ok:
                        logger.info("📧 Notificación OK: solicitud %s -> APROBACIÓN PARCIAL", solicitud_id)
                    else:
                        logger.warning("📧 Notificación FAIL: solicitud %s -> APROBACIÓN PARCIAL", solicitud_id)
                except Exception:
                    logger.exception("Error enviando notificación de APROBACIÓN PARCIAL (solicitud %s)", solicitud_id)
        else:
            flash(message, 'danger')
    except ValueError:
        flash('La cantidad aprobada debe ser un número válido.', 'danger')
    except Exception as e:
        logger.error("❌ Error aprobando parcialmente la solicitud: %s", sanitizar_log_text('Error interno'))
        flash('Error al aprobar parcialmente la solicitud.', 'danger')
    return redirect('/solicitudes')

@aprobacion_bp.route('/solicitudes/rechazar/<int:solicitud_id>', methods=['POST'])
def rechazar_solicitud(solicitud_id):
    if 'usuario_id' not in session:
        return redirect('/login')

    rol = session.get('rol', '')
    if rol == 'tesorería':
        flash('No tiene permisos para acceder a esta sección.', 'danger')
        return redirect('/reportes')

    try:
        solicitud = SolicitudModel.obtener_por_id(solicitud_id)
        if not solicitud or not verificar_acceso_oficina(solicitud.get('oficina_id')):
            flash('No tiene permisos para rechazar esta solicitud.', 'danger')
            return redirect('/solicitudes')

        usuario_id = session['usuario_id']
        observación = request.form.get('observación', '')
        if SolicitudModel.rechazar(solicitud_id, usuario_id, observación):
            flash('Solicitud rechazada exitosamente.', 'success')
            if NOTIFICACIONES_ACTIVAS:
                try:
                    info = SolicitudModel.obtener_por_id(solicitud_id) or {}
                    info['id'] = solicitud_id
                    ok = NotificationService.notificar_cambio_estado_solicitud(
                        info,
                        estado_anterior=str(info.get('estado') or info.get('Estado') or ''),
                        estado_nuevo="RECHAZADA",
                        usuario_gestion=_usuario_gestion_desde_sesion(),
                        observaciones=observación,
                    )
                    if ok:
                        logger.info("📧 Notificación OK: solicitud %s -> RECHAZADA", solicitud_id)
                    else:
                        logger.warning("📧 Notificación FAIL: solicitud %s -> RECHAZADA", solicitud_id)
                except Exception:
                    logger.exception("Error enviando notificación de RECHAZO (solicitud %s)", solicitud_id)
        else:
            flash('Error al rechazar la solicitud.', 'danger')
    except Exception as e:
        logger.error("❌ Error rechazando solicitud: %s", sanitizar_log_text('Error interno'))
        flash('Error al rechazar la solicitud.', 'danger')
    return redirect('/solicitudes')