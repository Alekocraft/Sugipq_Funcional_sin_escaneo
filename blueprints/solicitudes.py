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

# Configuración de logging
logger = logging.getLogger(__name__)

# Crear blueprint
solicitudes_bp = Blueprint('solicitudes', __name__)

# Configuración para carga de imágenes de novedades
UPLOAD_FOLDER_NOVEDADES = 'static/images/novedades'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

def allowed_file(filename):
    """Valida si la extensión del archivo está permitida"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Crear directorio si no existe
os.makedirs(UPLOAD_FOLDER_NOVEDADES, exist_ok=True)


# ============================================================================
# DECORADORES
# ============================================================================

def login_required(f):
    """Decorador que verifica autenticación"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'usuario_id' not in session:
            logger.warning(f"Acceso no autorizado a {request.path}. Redirigiendo a login.")
            flash('Debe iniciar sesión para acceder a esta página', 'warning')
            return redirect('/auth/login')
        return f(*args, **kwargs)
    return decorated_function


def approval_required(f):
    """Decorador para verificar permisos de aprobación"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not can_approve_solicitud():
            flash('No tiene permisos para aprobar solicitudes', 'danger')
            return redirect('/solicitudes')
        return f(*args, **kwargs)
    return decorated_function


def return_required(f):
    """Decorador para verificar permisos de devolución"""
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
# FUNCIÓN AUXILIAR PARA MAPEAR CAMPOS
# ============================================================================

def mapear_solicitud(s):
    """
    Mapea los campos del modelo a los nombres esperados por el template.
    El modelo devuelve: solicitud_id, estado_nombre, etc.
    El template espera: id, estado, etc.
    """
    return {
        # Campos principales
        'id': s.get('solicitud_id') or s.get('id'),
        'solicitud_id': s.get('solicitud_id') or s.get('id'),
        
        # Estado
        'estado_id': s.get('estado_id') or 1,
        'estado': s.get('estado_nombre') or s.get('estado') or 'Pendiente',
        
        # Material
        'material_id': s.get('material_id'),
        'material_nombre': s.get('material_nombre'),
        
        # Cantidades
        'cantidad_solicitada': s.get('cantidad_solicitada') or 0,
        'cantidad_entregada': s.get('cantidad_entregada') or 0,
        'cantidad_devuelta': s.get('cantidad_devuelta') or 0,
        
        # Oficina - IMPORTANTE: el modelo devuelve oficina_solicitante_id
        'oficina_id': s.get('oficina_solicitante_id') or s.get('oficina_id'),
        'oficina_solicitante_id': s.get('oficina_solicitante_id') or s.get('oficina_id'),
        'oficina_nombre': s.get('oficina_nombre'),
        
        # Usuario
        'usuario_solicitante': s.get('usuario_solicitante'),
        
        # Fechas
        'fecha_solicitud': s.get('fecha_solicitud'),
        'fecha_aprobacion': s.get('fecha_aprobacion'),
        'fecha_ultima_entrega': s.get('fecha_ultima_entrega'),
        
        # Valores
        'porcentaje_oficina': s.get('porcentaje_oficina') or 0,
        'valor_total_solicitado': s.get('valor_total_solicitado') or 0,
        'valor_oficina': s.get('valor_oficina') or 0,
        'valor_sede_principal': s.get('valor_sede_principal') or 0,
        
        # Aprobador
        'aprobador_id': s.get('aprobador_id'),
        'aprobador_nombre': s.get('aprobador_nombre'),
        
        # Observaciones
        'observacion': s.get('observacion') or '',
        
        # Novedades
        'tiene_novedad': s.get('tiene_novedad') or False,
        'estado_novedad': s.get('estado_novedad'),
        'tipo_novedad': s.get('tipo_novedad'),
        'novedad_descripcion': s.get('novedad_descripcion'),
        'cantidad_afectada': s.get('cantidad_afectada') or 0,
    }


# ============================================================================
# RUTAS PRINCIPALES
# ============================================================================

@solicitudes_bp.route('/')
@login_required
def listar():
    """Lista todas las solicitudes con filtros opcionales"""
    try:
        # Obtener parámetros de filtro
        filtro_estado = request.args.get('estado', 'todos')
        filtro_oficina = request.args.get('oficina', 'todas')
        filtro_material = request.args.get('material', '')
        filtro_solicitante = request.args.get('solicitante', '')
        
        # Obtener todas las solicitudes del modelo
        solicitudes_raw = SolicitudModel.obtener_todas()
        
        # *** IMPORTANTE: Mapear campos del modelo a los nombres esperados por el template ***
        solicitudes = [mapear_solicitud(s) for s in solicitudes_raw]
        
        # Filtrar por estado (usando el nombre del estado)
        if filtro_estado != 'todos':
            solicitudes = [s for s in solicitudes if s.get('estado', '').lower() == filtro_estado.lower()]
        
        # Filtrar por oficina
        oficinas_unique = list(set([s.get('oficina_nombre', '') for s in solicitudes if s.get('oficina_nombre')]))
        if filtro_oficina != 'todas':
            solicitudes = [s for s in solicitudes if s.get('oficina_nombre', '') == filtro_oficina]
        
        # Filtrar por material
        if filtro_material:
            solicitudes = [s for s in solicitudes if filtro_material.lower() in s.get('material_nombre', '').lower()]
        
        # Filtrar por solicitante
        if filtro_solicitante:
            solicitudes = [s for s in solicitudes if filtro_solicitante.lower() in s.get('usuario_solicitante', '').lower()]
        
        # Aplicar filtro de oficina según permisos del usuario
        solicitudes = filtrar_por_oficina_usuario(solicitudes)
        
        # Obtener materiales para mostrar información adicional
        materiales = MaterialModel.obtener_todos()
        materiales_dict = {m['id']: m for m in materiales}
        
        # Calcular estadísticas
        total_solicitudes = len(solicitudes)
        solicitudes_pendientes = len([s for s in solicitudes if s.get('estado', '').lower() == 'pendiente'])
        solicitudes_aprobadas = len([s for s in solicitudes if s.get('estado', '').lower() == 'aprobada'])
        solicitudes_rechazadas = len([s for s in solicitudes if s.get('estado', '').lower() == 'rechazada'])
        solicitudes_devueltas = len([s for s in solicitudes if s.get('estado', '').lower() == 'devuelta'])
        solicitudes_novedad = len([s for s in solicitudes if 'novedad' in s.get('estado', '').lower()])
        
        # Verificar si mostrar sección de novedades
        mostrar_novedades = can_view_novedades()
        
        # DEBUG: Log para verificar que los datos están correctos
        if solicitudes:
            logger.info(f"Primera solicitud mapeada: id={solicitudes[0].get('id')}, estado_id={solicitudes[0].get('estado_id')}, estado={solicitudes[0].get('estado')}")
        
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
            cantidad = request.form.get('cantidad')
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
                observacion=observacion
            )
            
            if solicitud_id:
                flash('Solicitud creada exitosamente', 'success')
                return redirect('/solicitudes')
            else:
                flash('Error al crear la solicitud', 'danger')
                return redirect('/solicitudes/crear')
        
        # GET: Mostrar formulario
        materiales = MaterialModel.obtener_todos()
        return render_template('solicitudes/crear.html', materiales=materiales)
        
    except Exception as e:
        logger.error(f"Error al crear solicitud: {str(e)}", exc_info=True)
        flash('Error al crear la solicitud', 'danger')
        return redirect('/solicitudes/crear')


# ============================================================================
# RUTAS DE APROBACIÓN
# ============================================================================

@solicitudes_bp.route('/aprobar/<int:solicitud_id>', methods=['POST'])
@login_required
@approval_required
def aprobar_solicitud(solicitud_id):
    """Aprobar una solicitud completamente"""
    try:
        usuario_aprobador = session.get('usuario_id')
        success, mensaje = SolicitudModel.aprobar(solicitud_id, usuario_aprobador)
        
        if success:
            flash('Solicitud aprobada exitosamente', 'success')
            return jsonify({'success': True, 'message': mensaje})
        else:
            flash(mensaje, 'danger')
            return jsonify({'success': False, 'message': mensaje})
        
    except Exception as e:
        logger.error(f"Error al aprobar solicitud {solicitud_id}: {str(e)}")
        return jsonify({'success': False, 'message': 'Error al procesar la aprobación'})


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
        success, mensaje = SolicitudModel.aprobar_parcial(solicitud_id, int(cantidad_aprobada), usuario_aprobador)
        
        if success:
            return jsonify({'success': True, 'message': f'Solicitud aprobada parcialmente ({cantidad_aprobada} unidades)'})
        else:
            return jsonify({'success': False, 'message': mensaje})
        
    except Exception as e:
        logger.error(f"Error al aprobar parcial solicitud {solicitud_id}: {str(e)}")
        return jsonify({'success': False, 'message': 'Error al procesar la aprobación parcial'})


@solicitudes_bp.route('/rechazar/<int:solicitud_id>', methods=['POST'])
@login_required
@approval_required
def rechazar_solicitud(solicitud_id):
    """Rechazar una solicitud"""
    try:
        if not can_reject_solicitud():
            return jsonify({'success': False, 'message': 'No tiene permisos para rechazar solicitudes'})
        
        data = request.get_json() if request.is_json else request.form
        observacion = data.get('observacion', 'Sin observación')
        
        usuario_rechaza = session.get('usuario_id')
        success, mensaje = SolicitudModel.rechazar(solicitud_id, usuario_rechaza, observacion)
        
        if success:
            return jsonify({'success': True, 'message': 'Solicitud rechazada exitosamente'})
        else:
            return jsonify({'success': False, 'message': mensaje})
        
    except Exception as e:
        logger.error(f"Error al rechazar solicitud {solicitud_id}: {str(e)}")
        return jsonify({'success': False, 'message': 'Error al procesar el rechazo'})


# ============================================================================
# RUTAS DE DEVOLUCIÓN
# ============================================================================

@solicitudes_bp.route('/devolucion/<int:solicitud_id>', methods=['POST'])
@login_required
def registrar_devolucion(solicitud_id):
    """Registrar devolución de material"""
    try:
        data = request.get_json() if request.is_json else request.form
        cantidad_devuelta = data.get('cantidad_devuelta')
        
        if not cantidad_devuelta:
            return jsonify({'success': False, 'message': 'Debe especificar la cantidad devuelta'})
        
        usuario_devolucion = session.get('usuario_nombre', 'Sistema')
        observacion = data.get('observacion', '')
        
        success, mensaje = SolicitudModel.registrar_devolucion(
            solicitud_id, 
            int(cantidad_devuelta), 
            usuario_devolucion,
            observacion
        )
        
        if success:
            return jsonify({'success': True, 'message': mensaje})
        else:
            return jsonify({'success': False, 'message': mensaje})
        
    except Exception as e:
        logger.error(f"Error al registrar devolución {solicitud_id}: {str(e)}")
        return jsonify({'success': False, 'message': 'Error al procesar la devolución'})


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
        
        # Validación de campos obligatorios
        if not all([solicitud_id, tipo_novedad, descripcion, cantidad_afectada, usuario_id]):
            logger.warning(f'Intento de registro de novedad con datos incompletos. Usuario: {usuario_id}')
            return jsonify({'success': False, 'error': 'Faltan datos requeridos'}), 400
        
        # Procesamiento de imagen adjunta
        imagen = request.files.get('imagen_novedad')
        ruta_imagen = None
        
        if imagen and imagen.filename:
            if allowed_file(imagen.filename):
                filename = secure_filename(imagen.filename)
                name, ext = os.path.splitext(filename)
                filename = f"{name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}{ext}"
                filepath = os.path.join(UPLOAD_FOLDER_NOVEDADES, filename)
                imagen.save(filepath)
                ruta_imagen = f"images/novedades/{filename}"
                logger.info(f'Imagen guardada para novedad: {filename}')
        
        # Crear novedad con imagen
        success = NovedadModel.crear(
            solicitud_id=int(solicitud_id),
            tipo_novedad=tipo_novedad,
            descripcion=descripcion,
            usuario_reporta=usuario_id,
            cantidad_afectada=int(cantidad_afectada),
            ruta_imagen=ruta_imagen
        )
        
        if success:
            # Actualizar estado de la solicitud a "novedad_registrada" (estado 7)
            SolicitudModel.actualizar_estado_solicitud(int(solicitud_id), 7)
            
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
        # Obtener datos del form o JSON
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
            logger.warning(f'Intento de gestión de novedad con datos incompletos')
            return jsonify({'success': False, 'message': 'Datos incompletos'}), 400

        # Obtener la novedad más reciente de la solicitud
        novedades = NovedadModel.obtener_por_solicitud(int(solicitud_id))
        
        if not novedades:
            logger.warning(f'No se encontraron novedades para la solicitud ID: {solicitud_id}')
            return jsonify({'success': False, 'message': 'No se encontró novedad para esta solicitud'}), 404

        novedad = novedades[0]
        usuario_gestion = session.get('usuario_nombre')

        # Determinar estados según la acción
        if accion == 'aceptar':
            nuevo_estado_novedad = 'aceptada'
            nuevo_estado_solicitud = 8  # Novedad Aceptada
            log_action = 'aceptada'
        else:
            nuevo_estado_novedad = 'rechazada'
            nuevo_estado_solicitud = 9  # Novedad Rechazada
            log_action = 'rechazada'

        # Actualizar estado de la novedad
        novedad_id = novedad.get('novedad_id') or novedad.get('id')
        success_novedad = NovedadModel.actualizar_estado(
            novedad_id=novedad_id,
            nuevo_estado=nuevo_estado_novedad,
            usuario_resuelve=usuario_gestion,
            comentario=observaciones
        )

        # Actualizar estado de la solicitud
        success_solicitud = SolicitudModel.actualizar_estado_solicitud(int(solicitud_id), nuevo_estado_solicitud)

        if success_novedad and success_solicitud:
            logger.info(f'Novedad {log_action}. Solicitud ID: {solicitud_id}, Usuario: {usuario_gestion}')
            return jsonify({
                'success': True, 
                'message': f'Novedad {nuevo_estado_novedad} exitosamente'
            })
        else:
            logger.error(f'Error al procesar novedad. Solicitud ID: {solicitud_id}')
            return jsonify({'success': False, 'message': 'Error al procesar la novedad'}), 500

    except Exception as e:
        logger.error(f'Error en gestión de novedad: {e}', exc_info=True)
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
                'error': 'No se encontró novedad para esta solicitud'
            })
            
    except Exception as e:
        logger.error(f"Error obteniendo novedad para solicitud {solicitud_id}: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@solicitudes_bp.route('/api/<int:solicitud_id>/info-devolucion')
@login_required
def info_devolucion(solicitud_id):
    """Obtiene información para devolución"""
    try:
        info = SolicitudModel.obtener_info_devolucion(solicitud_id)
        
        if not info:
            return jsonify({'success': False, 'error': 'Solicitud no encontrada'}), 404
        
        return jsonify({
            'success': True,
            'cantidad_entregada': info.get('cantidad_entregada', 0),
            'cantidad_ya_devuelta': info.get('cantidad_ya_devuelta', 0),
            'material_nombre': info.get('material_nombre', ''),
            'solicitante_nombre': info.get('solicitante_nombre', '')
        })
        
    except Exception as e:
        logger.error(f"Error obteniendo info devolución {solicitud_id}: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@solicitudes_bp.route('/api/<int:solicitud_id>/detalles')
@login_required
def detalle_solicitud_api(solicitud_id):
    """Obtiene el detalle completo de una solicitud para el modal"""
    try:
        # Obtener solicitud del modelo
        solicitud_raw = SolicitudModel.obtener_por_id(solicitud_id)
        
        if not solicitud_raw:
            return jsonify({'success': False, 'error': 'Solicitud no encontrada'}), 404
        
        # Mapear campos
        solicitud = mapear_solicitud(solicitud_raw)
        
        # Obtener novedades asociadas
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
    """API para obtener estadísticas de novedades"""
    try:
        estadisticas = NovedadModel.obtener_estadisticas()
        
        return jsonify({
            'success': True,
            'estadisticas': estadisticas
        })
    except Exception as e:
        logger.error(f"Error obteniendo estadísticas: {str(e)}")
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
