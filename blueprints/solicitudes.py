# blueprints/solicitudes.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from functools import wraps
import logging
from datetime import datetime
import os
from werkzeug.utils import secure_filename
from models.solicitudes_model import SolicitudModel
from models.materiales_model import MaterialModel
from models.oficinas_model import OficinaModel
from models.usuarios_model import UsuarioModel
from models.novedades_model import NovedadModel
from database import get_database_connection
from utils.filters import filtrar_por_oficina_usuario, verificar_acceso_oficina
from utils.permissions import (
    can_approve_solicitud, can_approve_partial_solicitud, 
    can_reject_solicitud, can_return_solicitud,
    can_create_novedad, can_manage_novedad, can_view_novedades
)

# Importar servicio de notificaciones
try:
    from services.notification_service import NotificationService, notificar_solicitud
    NOTIFICACIONES_ACTIVAS = True
except ImportError:
    NOTIFICACIONES_ACTIVAS = False
    print("âš ï¸ Servicio de notificaciones no disponible")

# ConfiguraciÃ³n de logging
logger = logging.getLogger(__name__)

# Crear blueprint
solicitudes_bp = Blueprint('solicitudes', __name__)

# ConfiguraciÃ³n para carga de imÃ¡genes de novedades
UPLOAD_FOLDER_NOVEDADES = 'static/images/novedades'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

def allowed_file(filename):
    """Valida si la extensiÃ³n del archivo estÃ¡ permitida"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Crear directorio si no existe
os.makedirs(UPLOAD_FOLDER_NOVEDADES, exist_ok=True)


# ============================================================================
# FUNCIONES HELPER PARA MOSTRAR BOTONES (Context Processors)
# ============================================================================

def should_show_devolucion_button(solicitud):
    """Determina si se debe mostrar el botÃ³n de solicitar devoluciÃ³n"""
    if not can_return_solicitud():
        return False
    estado = solicitud.get('estado', '').lower()
    estado_id = solicitud.get('estado_id', 0)
    # Solo mostrar para solicitudes aprobadas, entregadas parcial o completadas
    # y que no tengan devoluciÃ³n pendiente
    return estado_id in (2, 4, 5) or estado in ('aprobada', 'entregada parcial', 'completada')


def should_show_gestion_devolucion_button(solicitud):
    """Determina si se debe mostrar el botÃ³n de gestionar devoluciÃ³n"""
    if not can_manage_novedad():  # Usamos el mismo permiso de gestiÃ³n
        return False
    # Verificar si tiene devoluciÃ³n pendiente
    solicitud_id = solicitud.get('id') or solicitud.get('solicitud_id')
    if solicitud_id:
        return SolicitudModel.tiene_devolucion_pendiente(solicitud_id)
    return False


def should_show_novedad_button(solicitud):
    """Determina si se debe mostrar el botÃ³n de crear novedad"""
    if not can_create_novedad():
        return False
    estado = solicitud.get('estado', '').lower()
    estado_id = solicitud.get('estado_id', 0)
    # Solo mostrar para solicitudes aprobadas, entregadas o completadas
    # y que no tengan novedad activa
    if estado_id in (2, 4, 5) or estado in ('aprobada', 'entregada parcial', 'completada'):
        if 'novedad' not in estado:
            return True
    return False


def should_show_gestion_novedad_button(solicitud):
    """Determina si se debe mostrar el botÃ³n de gestionar novedad"""
    if not can_manage_novedad():
        return False
    estado = solicitud.get('estado', '').lower()
    estado_id = solicitud.get('estado_id', 0)
    # Mostrar para solicitudes con novedad registrada (estado 7)
    return estado_id == 7 or estado == 'novedad registrada'


def should_show_aprobacion_buttons(solicitud):
    """Determina si se deben mostrar los botones de aprobaciÃ³n"""
    estado = solicitud.get('estado', '').lower()
    estado_id = solicitud.get('estado_id', 0)
    # Solo mostrar para solicitudes pendientes
    return estado_id == 1 or estado == 'pendiente'


# Registrar funciones en el contexto del template
@solicitudes_bp.context_processor
def utility_processor():
    """Registra funciones Ãºtiles para usar en templates"""
    return {
        'should_show_devolucion_button': should_show_devolucion_button,
        'should_show_gestion_devolucion_button': should_show_gestion_devolucion_button,
        'should_show_novedad_button': should_show_novedad_button,
        'should_show_gestion_novedad_button': should_show_gestion_novedad_button,
        'should_show_aprobacion_buttons': should_show_aprobacion_buttons,
        'can_approve_solicitud': can_approve_solicitud,
        'can_reject_solicitud': can_reject_solicitud,
        'can_approve_partial_solicitud': can_approve_partial_solicitud,
        'can_return_solicitud': can_return_solicitud,
        'can_create_novedad': can_create_novedad,
        'can_manage_novedad': can_manage_novedad,
        'can_view_novedades': can_view_novedades
    }


# ============================================================================
# DECORADORES
# ============================================================================

def login_required(f):
    """Decorador que verifica autenticaciÃ³n"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'usuario_id' not in session:
            logger.warning(f"Acceso no autorizado a {request.path}. Redirigiendo a login.")
            flash('Debe iniciar sesiÃ³n para acceder a esta pÃ¡gina', 'warning')
            return redirect('/auth/login')
        return f(*args, **kwargs)
    return decorated_function


def approval_required(f):
    """Decorador para verificar permisos de aprobaciÃ³n"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not can_approve_solicitud():
            flash('No tiene permisos para aprobar solicitudes', 'danger')
            return redirect('/solicitudes')
        return f(*args, **kwargs)
    return decorated_function


def return_required(f):
    """Decorador para verificar permisos de devoluciÃ³n"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not can_return_solicitud():
            flash('No tiene permisos para registrar devoluciones', 'danger')
            return redirect('/solicitudes')
        return f(*args, **kwargs)
    return decorated_function


def novedad_create_required(f):
    """Decorador para verificar permisos de crear novedades"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not can_create_novedad():
            flash('No tiene permisos para crear novedades', 'danger')
            return redirect('/solicitudes')
        return f(*args, **kwargs)
    return decorated_function


def novedad_manage_required(f):
    """Decorador para verificar permisos de gestionar novedades"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not can_manage_novedad():
            flash('No tiene permisos para gestionar novedades', 'danger')
            return redirect('/solicitudes')
        return f(*args, **kwargs)
    return decorated_function


def novedad_view_required(f):
    """Decorador para verificar permisos de ver novedades"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not can_view_novedades():
            flash('No tiene permisos para ver novedades', 'danger')
            return redirect('/solicitudes')
        return f(*args, **kwargs)
    return decorated_function


# ============================================================================
# FUNCIÃ“N AUXILIAR PARA MAPEAR CAMPOS
# ============================================================================

def mapear_solicitud(s):
    """
    Mapea los campos del modelo a los nombres esperados por el template.
    """
    return {
        'id': s.get('solicitud_id') or s.get('id'),
        'solicitud_id': s.get('solicitud_id') or s.get('id'),
        'estado_id': s.get('estado_id') or 1,
        'estado': s.get('estado_nombre') or s.get('estado') or 'Pendiente',
        'material_id': s.get('material_id'),
        'material_nombre': s.get('material_nombre'),
        'cantidad_solicitada': s.get('cantidad_solicitada') or 0,
        'cantidad_entregada': s.get('cantidad_entregada') or 0,
        'cantidad_devuelta': s.get('cantidad_devuelta') or 0,
        'oficina_id': s.get('oficina_solicitante_id') or s.get('oficina_id'),
        'oficina_solicitante_id': s.get('oficina_solicitante_id') or s.get('oficina_id'),
        'oficina_nombre': s.get('oficina_nombre'),
        'usuario_solicitante': s.get('usuario_solicitante'),
        'fecha_solicitud': s.get('fecha_solicitud'),
        'fecha_aprobacion': s.get('fecha_aprobacion'),
        'fecha_ultima_entrega': s.get('fecha_ultima_entrega'),
        'porcentaje_oficina': s.get('porcentaje_oficina') or 0,
        'valor_total_solicitado': s.get('valor_total_solicitado') or 0,
        'valor_oficina': s.get('valor_oficina') or 0,
        'valor_sede_principal': s.get('valor_sede_principal') or 0,
        'aprobador_id': s.get('aprobador_id'),
        'aprobador_nombre': s.get('aprobador_nombre'),
        'observacion': s.get('observacion') or '',
        'tiene_novedad': s.get('tiene_novedad') or False,
        'estado_novedad': s.get('estado_novedad'),
        'tipo_novedad': s.get('tipo_novedad'),
        'novedad_descripcion': s.get('novedad_descripcion'),
        'cantidad_afectada': s.get('cantidad_afectada') or 0,
    }


# ============================================================================
# FUNCIONES AUXILIARES PARA NOTIFICACIONES
# ============================================================================

def _obtener_email_solicitante(usuario_id):
    """Obtiene el email del solicitante"""
    conn = get_database_connection()
    if not conn:
        return None
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT CorreoElectronico FROM Usuarios WHERE UsuarioId = ? AND Activo = 1",
            (usuario_id,)
        )
        row = cursor.fetchone()
        return row[0] if row else None
    except Exception as e:
        logger.error(f"Error obteniendo email: {e}")
        return None
    finally:
        cursor.close()
        conn.close()


def _obtener_info_solicitud_completa(solicitud_id):
    """Obtiene informaciÃ³n completa de la solicitud para notificaciones"""
    conn = get_database_connection()
    if not conn:
        return None
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                sm.SolicitudId,
                m.NombreElemento as material_nombre,
                sm.CantidadSolicitada,
                sm.CantidadEntregada,
                o.NombreOficina as oficina_nombre,
                sm.UsuarioSolicitante,
                u.CorreoElectronico as email_solicitante,
                es.NombreEstado as estado
            FROM SolicitudesMaterial sm
            INNER JOIN Materiales m ON sm.MaterialId = m.MaterialId
            INNER JOIN Oficinas o ON sm.OficinaSolicitanteId = o.OficinaId
            LEFT JOIN Usuarios u ON sm.UsuarioSolicitante = u.NombreUsuario
            INNER JOIN EstadosSolicitud es ON sm.EstadoId = es.EstadoId
            WHERE sm.SolicitudId = ?
        """, (solicitud_id,))
        row = cursor.fetchone()
        if row:
            return {
                'id': row[0],
                'material_nombre': row[1],
                'cantidad_solicitada': row[2],
                'cantidad_entregada': row[3],
                'oficina_nombre': row[4],
                'usuario_solicitante': row[5],
                'email_solicitante': row[6],
                'estado': row[7]
            }
        return None
    except Exception as e:
        logger.error(f"Error obteniendo info solicitud: {e}")
        return None
    finally:
        cursor.close()
        conn.close()


# ============================================================================
# RUTAS PRINCIPALES
# ============================================================================

@solicitudes_bp.route('/')
@login_required
def listar():
    """Lista todas las solicitudes con filtros opcionales"""
    try:
        filtro_estado = request.args.get('estado', 'todos')
        filtro_oficina = request.args.get('oficina', 'todas')
        filtro_material = request.args.get('material', '')
        filtro_solicitante = request.args.get('solicitante', '')
        
        if filtro_estado == 'todas_novedades':
            solicitudes_raw = SolicitudModel.obtener_todas(estado='todas_novedades')
        elif filtro_estado != 'todos':
            solicitudes_raw = SolicitudModel.obtener_todas(estado=filtro_estado)
        else:
            solicitudes_raw = SolicitudModel.obtener_todas()
        
        solicitudes = [mapear_solicitud(s) for s in solicitudes_raw]
        
        oficinas_unique = list(set([s.get('oficina_nombre', '') for s in solicitudes if s.get('oficina_nombre')]))
        if filtro_oficina != 'todas':
            solicitudes = [s for s in solicitudes if s.get('oficina_nombre', '') == filtro_oficina]
        
        if filtro_material:
            solicitudes = [s for s in solicitudes if filtro_material.lower() in s.get('material_nombre', '').lower()]
        
        if filtro_solicitante:
            solicitudes = [s for s in solicitudes if filtro_solicitante.lower() in s.get('usuario_solicitante', '').lower()]
        
        solicitudes = filtrar_por_oficina_usuario(solicitudes)
        
        materiales = MaterialModel.obtener_todos()
        materiales_dict = {m['id']: m for m in materiales}
        
        todas_solicitudes = [mapear_solicitud(s) for s in SolicitudModel.obtener_todas()]
        todas_solicitudes = filtrar_por_oficina_usuario(todas_solicitudes)
        
        total_solicitudes = len(todas_solicitudes)
        solicitudes_pendientes = len([s for s in todas_solicitudes if s.get('estado', '').lower() == 'pendiente'])
        solicitudes_aprobadas = len([s for s in todas_solicitudes if s.get('estado', '').lower() == 'aprobada'])
        solicitudes_rechazadas = len([s for s in todas_solicitudes if s.get('estado', '').lower() == 'rechazada'])
        solicitudes_devueltas = len([s for s in todas_solicitudes if s.get('estado', '').lower() == 'devuelta'])
        solicitudes_novedad = len([s for s in todas_solicitudes if 'novedad' in s.get('estado', '').lower()])
        
        mostrar_novedades = can_view_novedades()
        
        return render_template(
            'solicitudes/solicitudes.html',
            solicitudes=solicitudes,
            materiales_dict=materiales_dict,
            total_solicitudes=total_solicitudes,
            solicitudes_pendientes=solicitudes_pendientes,
            solicitudes_aprobadas=solicitudes_aprobadas,
            solicitudes_rechazadas=solicitudes_rechazadas,
            solicitudes_devueltas=solicitudes_devueltas,
            solicitudes_novedad=solicitudes_novedad,
            oficinas_unique=oficinas_unique,
            filtro_estado=filtro_estado,
            filtro_oficina=filtro_oficina,
            filtro_material=filtro_material,
            filtro_solicitante=filtro_solicitante,
            mostrar_novedades=mostrar_novedades
        )
        
    except Exception as e:
        logger.error(f"Error al listar solicitudes: {str(e)}", exc_info=True)
        flash('Error al cargar las solicitudes', 'danger')
        return redirect('/dashboard')


@solicitudes_bp.route('/crear', methods=['GET', 'POST'])
@login_required
def crear():
    """Crear una nueva solicitud"""
    try:
        if request.method == 'POST':
            material_id = request.form.get('material_id')
            cantidad = request.form.get('cantidad_solicitada')
            porcentaje_oficina = request.form.get('porcentaje_oficina', '100')
            observacion = request.form.get('observacion', '')
            
            if not all([material_id, cantidad]):
                flash('Material y cantidad son requeridos', 'danger')
                return redirect('/solicitudes/crear')
            
            usuario_id = session.get('usuario_id')
            oficina_id = session.get('oficina_id')
            
            if not oficina_id:
                flash('No se pudo determinar su oficina', 'danger')
                return redirect('/solicitudes/crear')
            
            solicitud_id = SolicitudModel.crear_solicitud(
                material_id=int(material_id),
                cantidad_solicitada=int(cantidad),
                usuario_solicitante=usuario_id,
                oficina_solicitante=oficina_id,
                porcentaje_oficina=float(porcentaje_oficina),
                observacion=observacion
            )
            
            if solicitud_id:
                # ====== NOTIFICACIÃ“N: Solicitud creada ======
                if NOTIFICACIONES_ACTIVAS:
                    try:
                        solicitud_info = _obtener_info_solicitud_completa(solicitud_id)
                        if solicitud_info:
                            NotificationService.notificar_solicitud_creada(solicitud_info)
                            logger.info(f"ðŸ“§ NotificaciÃ³n enviada: Nueva solicitud #{solicitud_id}")
                    except Exception as e:
                        logger.error(f"Error enviando notificaciÃ³n de solicitud creada: {e}")
                # =============================================
                
                flash('Solicitud creada exitosamente', 'success')
                return redirect('/solicitudes')
            else:
                flash('Error al crear la solicitud', 'danger')
                return redirect('/solicitudes/crear')
        
        materiales = MaterialModel.obtener_todos()
        return render_template('solicitudes/crear.html', materiales=materiales)
        
    except Exception as e:
        logger.error(f"Error al crear solicitud: {str(e)}", exc_info=True)
        flash('Error al crear la solicitud', 'danger')
        return redirect('/solicitudes/crear')


# ============================================================================
# RUTAS DE APROBACIÃ“N
# ============================================================================

@solicitudes_bp.route('/aprobar/<int:solicitud_id>', methods=['POST'])
@login_required
@approval_required
def aprobar_solicitud(solicitud_id):
    """Aprobar una solicitud completamente"""
    try:
        usuario_aprobador = session.get('usuario_id')
        usuario_nombre = session.get('usuario_nombre', 'Sistema')
        
        # Obtener info antes de aprobar
        solicitud_info = _obtener_info_solicitud_completa(solicitud_id)
        estado_anterior = solicitud_info.get('estado', 'Pendiente') if solicitud_info else 'Pendiente'
        
        success, mensaje = SolicitudModel.aprobar(solicitud_id, usuario_aprobador)
        
        if success:
            # ====== NOTIFICACIÃ“N: Solicitud aprobada ======
            if NOTIFICACIONES_ACTIVAS and solicitud_info and solicitud_info.get('email_solicitante'):
                try:
                    NotificationService.notificar_cambio_estado_solicitud(
                        solicitud_info, 
                        estado_anterior, 
                        'Aprobada',
                        usuario_nombre
                    )
                    logger.info(f"ðŸ“§ NotificaciÃ³n enviada: Solicitud #{solicitud_id} aprobada")
                except Exception as e:
                    logger.error(f"Error enviando notificaciÃ³n de aprobaciÃ³n: {e}")
            # =============================================
            
            flash('Solicitud aprobada exitosamente', 'success')
            return jsonify({'success': True, 'message': mensaje})
        else:
            flash(mensaje, 'danger')
            return jsonify({'success': False, 'message': mensaje})
        
    except Exception as e:
        logger.error(f"Error al aprobar solicitud {solicitud_id}: {str(e)}")
        return jsonify({'success': False, 'message': 'Error al procesar la aprobaciÃ³n'})


@solicitudes_bp.route('/aprobar_parcial/<int:solicitud_id>', methods=['POST'])
@login_required
@approval_required
def aprobar_parcial_solicitud(solicitud_id):
    """Aprobar parcialmente una solicitud"""
    try:
        if not can_approve_partial_solicitud():
            return jsonify({'success': False, 'message': 'No tiene permisos para aprobar parcialmente'})
        
        data = request.get_json() if request.is_json else request.form
        cantidad_aprobada = data.get('cantidad_aprobada')
        
        if not cantidad_aprobada:
            return jsonify({'success': False, 'message': 'Debe especificar la cantidad a aprobar'})
        
        usuario_aprobador = session.get('usuario_id')
        usuario_nombre = session.get('usuario_nombre', 'Sistema')
        
        # Obtener info antes de aprobar
        solicitud_info = _obtener_info_solicitud_completa(solicitud_id)
        estado_anterior = solicitud_info.get('estado', 'Pendiente') if solicitud_info else 'Pendiente'
        
        success, mensaje = SolicitudModel.aprobar_parcial(solicitud_id, int(cantidad_aprobada), usuario_aprobador)
        
        if success:
            # ====== NOTIFICACIÃ“N: Entrega parcial ======
            if NOTIFICACIONES_ACTIVAS and solicitud_info and solicitud_info.get('email_solicitante'):
                try:
                    NotificationService.notificar_cambio_estado_solicitud(
                        solicitud_info, 
                        estado_anterior, 
                        'Entregada Parcial',
                        usuario_nombre,
                        f'Cantidad aprobada: {cantidad_aprobada}'
                    )
                    logger.info(f"ðŸ“§ NotificaciÃ³n enviada: Solicitud #{solicitud_id} aprobada parcialmente")
                except Exception as e:
                    logger.error(f"Error enviando notificaciÃ³n de aprobaciÃ³n parcial: {e}")
            # =============================================
            
            return jsonify({'success': True, 'message': f'Solicitud aprobada parcialmente ({cantidad_aprobada} unidades)'})
        else:
            return jsonify({'success': False, 'message': mensaje})
        
    except Exception as e:
        logger.error(f"Error al aprobar parcial solicitud {solicitud_id}: {str(e)}")
        return jsonify({'success': False, 'message': 'Error al procesar la aprobaciÃ³n parcial'})


@solicitudes_bp.route('/rechazar/<int:solicitud_id>', methods=['POST'])
@login_required
@approval_required
def rechazar_solicitud(solicitud_id):
    """Rechazar una solicitud"""
    try:
        if not can_reject_solicitud():
            return jsonify({'success': False, 'message': 'No tiene permisos para rechazar solicitudes'})
        
        data = request.get_json() if request.is_json else request.form
        observacion = data.get('observacion', 'Sin observaciÃ³n')
        
        usuario_rechaza = session.get('usuario_id')
        usuario_nombre = session.get('usuario_nombre', 'Sistema')
        
        # Obtener info antes de rechazar
        solicitud_info = _obtener_info_solicitud_completa(solicitud_id)
        estado_anterior = solicitud_info.get('estado', 'Pendiente') if solicitud_info else 'Pendiente'
        
        success, mensaje = SolicitudModel.rechazar(solicitud_id, usuario_rechaza, observacion)
        
        if success:
            # ====== NOTIFICACIÃ“N: Solicitud rechazada ======
            if NOTIFICACIONES_ACTIVAS and solicitud_info and solicitud_info.get('email_solicitante'):
                try:
                    NotificationService.notificar_cambio_estado_solicitud(
                        solicitud_info, 
                        estado_anterior, 
                        'Rechazada',
                        usuario_nombre,
                        observacion
                    )
                    logger.info(f"ðŸ“§ NotificaciÃ³n enviada: Solicitud #{solicitud_id} rechazada")
                except Exception as e:
                    logger.error(f"Error enviando notificaciÃ³n de rechazo: {e}")
            # =============================================
            
            return jsonify({'success': True, 'message': 'Solicitud rechazada exitosamente'})
        else:
            return jsonify({'success': False, 'message': mensaje})
        
    except Exception as e:
        logger.error(f"Error al rechazar solicitud {solicitud_id}: {str(e)}")
        return jsonify({'success': False, 'message': 'Error al procesar el rechazo'})


# ============================================================================
# RUTAS DE DEVOLUCIÃ“N (CON FLUJO DE APROBACIÃ“N)
# ============================================================================

# ConfiguraciÃ³n para imÃ¡genes de devoluciones
UPLOAD_FOLDER_DEVOLUCIONES = 'static/images/devoluciones'
os.makedirs(UPLOAD_FOLDER_DEVOLUCIONES, exist_ok=True)


@solicitudes_bp.route('/solicitar-devolucion/<int:solicitud_id>', methods=['POST'])
@login_required
def solicitar_devolucion(solicitud_id):
    """Solicitar devoluciÃ³n de material (requiere aprobaciÃ³n)"""
    try:
        # Verificar permiso de solicitar devoluciÃ³n
        if not can_return_solicitud():
            return jsonify({'success': False, 'message': 'No tiene permisos para solicitar devoluciones'}), 403
        
        data = request.form if request.form else request.get_json()
        cantidad_devuelta = data.get('cantidad_devuelta')
        motivo = data.get('motivo', '')
        
        if not cantidad_devuelta:
            return jsonify({'success': False, 'message': 'Debe especificar la cantidad a devolver'})
        
        usuario_solicita = session.get('usuario_nombre', 'Sistema')
        usuario_id = session.get('usuario_id')
        
        # Procesar imagen si se enviÃ³
        imagen = request.files.get('imagen_devolucion') if hasattr(request, 'files') else None
        ruta_imagen = None
        
        if imagen and imagen.filename and allowed_file(imagen.filename):
            filename = secure_filename(imagen.filename)
            name, ext = os.path.splitext(filename)
            filename = f"dev_{solicitud_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}{ext}"
            filepath = os.path.join(UPLOAD_FOLDER_DEVOLUCIONES, filename)
            imagen.save(filepath)
            ruta_imagen = f"images/devoluciones/{filename}"
            logger.info(f'Imagen guardada para devoluciÃ³n: {filename}')
        
        # Registrar solicitud de devoluciÃ³n (estado pendiente)
        success, mensaje = SolicitudModel.solicitar_devolucion(
            solicitud_id=solicitud_id,
            cantidad_devuelta=int(cantidad_devuelta),
            usuario_solicita=usuario_solicita,
            motivo=motivo,
            ruta_imagen=ruta_imagen
        )
        
        if success:
            logger.info(f'DevoluciÃ³n solicitada. Solicitud ID: {solicitud_id}, Cantidad: {cantidad_devuelta}, Usuario: {usuario_solicita}')
            return jsonify({'success': True, 'message': 'Solicitud de devoluciÃ³n registrada. Pendiente de aprobaciÃ³n.'})
        else:
            return jsonify({'success': False, 'message': mensaje})
        
    except Exception as e:
        logger.error(f"Error al solicitar devoluciÃ³n {solicitud_id}: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'message': 'Error al procesar la solicitud de devoluciÃ³n'})


@solicitudes_bp.route('/aprobar-devolucion', methods=['POST'])
@login_required
def aprobar_devolucion():
    """Aprobar una solicitud de devoluciÃ³n"""
    try:
        # Verificar permiso de aprobar devoluciÃ³n
        if not can_manage_novedad():  # Usamos el mismo permiso de gestiÃ³n
            return jsonify({'success': False, 'message': 'No tiene permisos para aprobar devoluciones'}), 403
        
        data = request.get_json() if request.is_json else request.form
        devolucion_id = data.get('devolucion_id')
        observaciones = data.get('observaciones', '')
        
        if not devolucion_id:
            return jsonify({'success': False, 'message': 'ID de devoluciÃ³n requerido'}), 400
        
        usuario_aprueba = session.get('usuario_nombre', 'Sistema')
        
        # Aprobar y procesar la devoluciÃ³n (actualiza stock)
        success, mensaje = SolicitudModel.aprobar_devolucion(
            devolucion_id=int(devolucion_id),
            usuario_aprueba=usuario_aprueba,
            observaciones=observaciones
        )
        
        if success:
            logger.info(f'DevoluciÃ³n aprobada. ID: {devolucion_id}, Usuario: {usuario_aprueba}')
            return jsonify({'success': True, 'message': 'DevoluciÃ³n aprobada y procesada exitosamente'})
        else:
            return jsonify({'success': False, 'message': mensaje})
        
    except Exception as e:
        logger.error(f"Error al aprobar devoluciÃ³n: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'message': 'Error al aprobar la devoluciÃ³n'})


@solicitudes_bp.route('/rechazar-devolucion', methods=['POST'])
@login_required
def rechazar_devolucion():
    """Rechazar una solicitud de devoluciÃ³n"""
    try:
        # Verificar permiso
        if not can_manage_novedad():
            return jsonify({'success': False, 'message': 'No tiene permisos para rechazar devoluciones'}), 403
        
        data = request.get_json() if request.is_json else request.form
        devolucion_id = data.get('devolucion_id')
        observaciones = data.get('observaciones', '')
        
        if not devolucion_id:
            return jsonify({'success': False, 'message': 'ID de devoluciÃ³n requerido'}), 400
        
        usuario_rechaza = session.get('usuario_nombre', 'Sistema')
        
        success, mensaje = SolicitudModel.rechazar_devolucion(
            devolucion_id=int(devolucion_id),
            usuario_rechaza=usuario_rechaza,
            observaciones=observaciones
        )
        
        if success:
            logger.info(f'DevoluciÃ³n rechazada. ID: {devolucion_id}, Usuario: {usuario_rechaza}')
            return jsonify({'success': True, 'message': 'DevoluciÃ³n rechazada'})
        else:
            return jsonify({'success': False, 'message': mensaje})
        
    except Exception as e:
        logger.error(f"Error al rechazar devoluciÃ³n: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'message': 'Error al rechazar la devoluciÃ³n'})


@solicitudes_bp.route('/api/<int:solicitud_id>/devolucion-pendiente')
@login_required
def obtener_devolucion_pendiente(solicitud_id):
    """Obtiene la devoluciÃ³n pendiente de una solicitud"""
    try:
        devolucion = SolicitudModel.obtener_devolucion_pendiente(solicitud_id)
        
        if devolucion:
            return jsonify({
                'success': True,
                'devolucion': devolucion
            })
        else:
            return jsonify({
                'success': False,
                'error': 'No se encontrÃ³ devoluciÃ³n pendiente para esta solicitud'
            })
            
    except Exception as e:
        logger.error(f"Error obteniendo devoluciÃ³n pendiente {solicitud_id}: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


# Mantener ruta antigua por compatibilidad (redirige al nuevo flujo)
@solicitudes_bp.route('/devolucion/<int:solicitud_id>', methods=['POST'])
@login_required
def registrar_devolucion(solicitud_id):
    """Registrar devoluciÃ³n de material - REDIRIGE AL NUEVO FLUJO"""
    return solicitar_devolucion(solicitud_id)


# ============================================================================
# RUTAS DE NOVEDADES
# ============================================================================

@solicitudes_bp.route('/registrar-novedad', methods=['POST'])
@login_required
@novedad_create_required
def registrar_novedad():
    """Registra una nueva novedad asociada a una solicitud"""
    try:
        solicitud_id = request.form.get('solicitud_id')
        tipo_novedad = request.form.get('tipo_novedad')
        descripcion = request.form.get('descripcion')
        cantidad_afectada = request.form.get('cantidad_afectada')
        usuario_id = session.get('usuario_id')
        usuario_nombre = session.get('usuario_nombre', 'Sistema')
        
        if not all([solicitud_id, tipo_novedad, descripcion, cantidad_afectada, usuario_id]):
            logger.warning(f'Intento de registro de novedad con datos incompletos. Usuario: {usuario_id}')
            return jsonify({'success': False, 'error': 'Faltan datos requeridos'}), 400
        
        # âœ… VALIDAR IMAGEN OBLIGATORIA
        imagen = request.files.get('imagen_novedad')
        if not imagen or not imagen.filename:
            logger.warning(f'Intento de registro de novedad sin imagen. Usuario: {usuario_id}')
            return jsonify({'success': False, 'error': 'La imagen de evidencia es obligatoria'}), 400
        
        # Obtener info de la solicitud
        solicitud_info = _obtener_info_solicitud_completa(int(solicitud_id))
        
        ruta_imagen = None
        
        if allowed_file(imagen.filename):
            filename = secure_filename(imagen.filename)
            name, ext = os.path.splitext(filename)
            filename = f"{name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}{ext}"
            filepath = os.path.join(UPLOAD_FOLDER_NOVEDADES, filename)
            imagen.save(filepath)
            ruta_imagen = f"images/novedades/{filename}"
            logger.info(f'Imagen guardada para novedad: {filename}')
        else:
            return jsonify({'success': False, 'error': 'Tipo de archivo no permitido. Use: png, jpg, jpeg, gif, webp'}), 400
        
        success = NovedadModel.crear(
            solicitud_id=int(solicitud_id),
            tipo_novedad=tipo_novedad,
            descripcion=descripcion,
            usuario_reporta=usuario_nombre,  # âœ… Corregido: era usuario_id
            cantidad_afectada=int(cantidad_afectada),
            ruta_imagen=ruta_imagen
        )
        
        if success:
            SolicitudModel.actualizar_estado_solicitud(int(solicitud_id), 7)
            
            # ====== NOTIFICACIÃ“N: Novedad registrada ======
            if NOTIFICACIONES_ACTIVAS and solicitud_info:
                try:
                    novedad_info = {
                        'tipo': tipo_novedad,
                        'descripcion': descripcion,
                        'cantidad_afectada': cantidad_afectada,
                        'usuario_registra': usuario_nombre
                    }
                    NotificationService.notificar_novedad_registrada(solicitud_info, novedad_info)
                    logger.info(f"ðŸ“§ NotificaciÃ³n enviada: Novedad registrada para solicitud #{solicitud_id}")
                except Exception as e:
                    logger.error(f"Error enviando notificaciÃ³n de novedad: {e}")
            # =============================================
            
            logger.info(f'Novedad registrada exitosamente. Solicitud ID: {solicitud_id}, Usuario: {usuario_id}')
            return jsonify({
                'success': True, 
                'message': 'Novedad registrada correctamente'
            })
        else:
            return jsonify({'success': False, 'error': 'Error al registrar novedad'}), 500
        
    except Exception as e:
        logger.error(f'Error al registrar novedad: {str(e)}', exc_info=True)
        return jsonify({'success': False, 'error': 'Error interno del servidor'}), 500


@solicitudes_bp.route('/gestionar-novedad', methods=['POST'])
@login_required
@novedad_manage_required
def gestionar_novedad():
    """Gestiona una novedad existente (aceptar/rechazar)"""
    try:
        if request.is_json:
            data = request.get_json()
            solicitud_id = data.get('solicitud_id')
            accion = data.get('accion')
            observaciones = data.get('observaciones', '')
        else:
            solicitud_id = request.form.get('solicitud_id')
            accion = request.form.get('accion')
            observaciones = request.form.get('observaciones', '')
        
        if not all([solicitud_id, accion]):
            logger.warning(f'Intento de gestiÃ³n de novedad con datos incompletos')
            return jsonify({'success': False, 'message': 'Datos incompletos'}), 400

        novedades = NovedadModel.obtener_por_solicitud(int(solicitud_id))
        
        if not novedades:
            logger.warning(f'No se encontraron novedades para la solicitud ID: {solicitud_id}')
            return jsonify({'success': False, 'message': 'No se encontrÃ³ novedad para esta solicitud'}), 404

        novedad = novedades[0]
        usuario_gestion = session.get('usuario_nombre')
        
        # Obtener info de la solicitud
        solicitud_info = _obtener_info_solicitud_completa(int(solicitud_id))

        if accion == 'aceptar':
            nuevo_estado_novedad = 'aceptada'
            nuevo_estado_solicitud = 8
            log_action = 'aceptada'
            estado_nombre = 'Novedad Aceptada'
        else:
            nuevo_estado_novedad = 'rechazada'
            nuevo_estado_solicitud = 9
            log_action = 'rechazada'
            estado_nombre = 'Novedad Rechazada'

        novedad_id = novedad.get('novedad_id') or novedad.get('id')
        success_novedad = NovedadModel.actualizar_estado(
            novedad_id=novedad_id,
            nuevo_estado=nuevo_estado_novedad,
            usuario_resuelve=usuario_gestion,
            comentario=observaciones
        )

        success_solicitud = SolicitudModel.actualizar_estado_solicitud(int(solicitud_id), nuevo_estado_solicitud)

        if success_novedad and success_solicitud:
            # ====== NOTIFICACIÃ“N: Novedad gestionada ======
            if NOTIFICACIONES_ACTIVAS and solicitud_info and solicitud_info.get('email_solicitante'):
                try:
                    NotificationService.notificar_cambio_estado_solicitud(
                        solicitud_info, 
                        'Novedad Registrada', 
                        estado_nombre,
                        usuario_gestion,
                        observaciones
                    )
                    logger.info(f"ðŸ“§ NotificaciÃ³n enviada: Novedad {log_action} para solicitud #{solicitud_id}")
                except Exception as e:
                    logger.error(f"Error enviando notificaciÃ³n de gestiÃ³n novedad: {e}")
            # =============================================
            
            logger.info(f'Novedad {log_action}. Solicitud ID: {solicitud_id}, Usuario: {usuario_gestion}')
            return jsonify({
                'success': True, 
                'message': f'Novedad {nuevo_estado_novedad} exitosamente'
            })
        else:
            logger.error(f'Error al procesar novedad. Solicitud ID: {solicitud_id}')
            return jsonify({'success': False, 'message': 'Error al procesar la novedad'}), 500

    except Exception as e:
        logger.error(f'Error en gestiÃ³n de novedad: {e}', exc_info=True)
        return jsonify({'success': False, 'message': 'Error interno del servidor'}), 500


@solicitudes_bp.route('/novedades')
@login_required
@novedad_view_required
def listar_novedades():
    """Lista todas las novedades del sistema"""
    try:
        novedades = NovedadModel.obtener_todas()
        estadisticas = NovedadModel.obtener_estadisticas()
        
        filtro_estado = request.args.get('estado', '')
        if filtro_estado:
            novedades = [n for n in novedades if n.get('estado') == filtro_estado]
        
        tipos_novedad = NovedadModel.obtener_tipos_disponibles()
        
        logger.info(f"Usuario {session.get('usuario_id')} visualizando {len(novedades)} novedades")
        
        return render_template(
            'solicitudes/listar.html',
            novedades=novedades,
            estadisticas_novedades=estadisticas,
            filtro_estado=filtro_estado,
            tipos_novedad=tipos_novedad,
            mostrar_todas_novedades=True
        )
        
    except Exception as e:
        logger.error(f"Error al listar novedades: {str(e)}", exc_info=True)
        flash('Error al cargar novedades', 'danger')
        return redirect('/solicitudes')


# ============================================================================
# APIs
# ============================================================================

@solicitudes_bp.route('/api/novedades/pendientes')
@login_required
@novedad_view_required
def obtener_novedades_pendientes():
    """Obtiene todas las novedades en estado pendiente"""
    try:
        novedades = NovedadModel.obtener_novedades_pendientes()
        logger.info(f'Consulta de novedades pendientes. Usuario: {session.get("usuario_id")}')
        return jsonify({'success': True, 'novedades': novedades})
    except Exception as e:
        logger.error(f'Error al obtener novedades pendientes: {e}', exc_info=True)
        return jsonify({'success': False, 'message': 'Error interno del servidor'}), 500


@solicitudes_bp.route('/api/<int:solicitud_id>/novedad')
@login_required
def obtener_novedad_por_solicitud(solicitud_id):
    """Obtiene la novedad asociada a una solicitud"""
    try:
        novedades = NovedadModel.obtener_por_solicitud(solicitud_id)
        
        if novedades:
            return jsonify({
                'success': True,
                'novedad': novedades[0]
            })
        else:
            return jsonify({
                'success': False,
                'error': 'No se encontrÃ³ novedad para esta solicitud'
            })
            
    except Exception as e:
        logger.error(f"Error obteniendo novedad para solicitud {solicitud_id}: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@solicitudes_bp.route('/api/<int:solicitud_id>/info-devolucion')
@login_required
def info_devolucion(solicitud_id):
    """Obtiene informaciÃ³n para devoluciÃ³n"""
    try:
        info = SolicitudModel.obtener_info_devolucion(solicitud_id)
        
        if not info:
            return jsonify({'success': False, 'error': 'Solicitud no encontrada'}), 404
        
        return jsonify({
            'success': True,
            'cantidad_entregada': info.get('cantidad_entregada', 0),
            'cantidad_ya_devuelta': info.get('cantidad_ya_devuelta', 0),
            'material_nombre': info.get('material_nombre', ''),
            'solicitante_nombre': info.get('solicitante_nombre', ''),
            'material_imagen': info.get('material_imagen', '')
        })
        
    except Exception as e:
        logger.error(f"Error obteniendo info devoluciÃ³n {solicitud_id}: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@solicitudes_bp.route('/api/<int:solicitud_id>/detalles')
@login_required
def detalle_solicitud_api(solicitud_id):
    """Obtiene el detalle completo de una solicitud para el modal"""
    try:
        solicitud_raw = SolicitudModel.obtener_por_id(solicitud_id)
        
        if not solicitud_raw:
            return jsonify({'success': False, 'error': 'Solicitud no encontrada'}), 404
        
        solicitud = mapear_solicitud(solicitud_raw)
        novedades = NovedadModel.obtener_por_solicitud(solicitud_id)
        
        return jsonify({
            'success': True,
            'solicitud': solicitud,
            'novedades': novedades
        })
        
    except Exception as e:
        logger.error(f"Error obteniendo detalle de solicitud {solicitud_id}: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@solicitudes_bp.route('/api/novedades/estadisticas')
@login_required
@novedad_view_required
def obtener_estadisticas_novedades():
    """API para obtener estadÃ­sticas de novedades"""
    try:
        estadisticas = NovedadModel.obtener_estadisticas()
        
        return jsonify({
            'success': True,
            'estadisticas': estadisticas
        })
    except Exception as e:
        logger.error(f"Error obteniendo estadÃ­sticas: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@solicitudes_bp.route('/api/novedades/actualizar/<int:novedad_id>', methods=['POST'])
@login_required
@novedad_manage_required
def actualizar_novedad(novedad_id):
    """Actualizar estado de una novedad"""
    try:
        data = request.get_json()
        nuevo_estado = data.get('estado')
        observaciones = data.get('observaciones', '')
        
        if not nuevo_estado:
            return jsonify({'success': False, 'message': 'Estado requerido'}), 400
        
        usuario_resuelve = session.get('usuario_nombre', 'Sistema')
        
        success = NovedadModel.actualizar_estado(
            novedad_id=novedad_id,
            estado=nuevo_estado,
            usuario_resuelve=usuario_resuelve,
            observaciones_resolucion=observaciones
        )
        
        if success:
            logger.info(f"Novedad {novedad_id} actualizada a {nuevo_estado} por {usuario_resuelve}")
            return jsonify({'success': True, 'message': 'Novedad actualizada'})
        else:
            return jsonify({'success': False, 'message': 'Error al actualizar'}), 500
            
    except Exception as e:
        logger.error(f"Error actualizando novedad: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500