# app/solicitudes.py

import os
import logging
from datetime import datetime
from werkzeug.utils import secure_filename
from flask import Blueprint, render_template, request, jsonify, session, flash, redirect, url_for
from functools import wraps

# Importar modelos
from models.novedades_model import NovedadModel
from models.solicitudes_model import SolicitudModel
from database import get_database_connection

# Configurar blueprint
solicitudes_bp = Blueprint('solicitudes', __name__)

# Configuración de logging
logger = logging.getLogger(__name__)

# Configuración para carga de imágenes
UPLOAD_FOLDER_NOVEDADES = 'static/images/novedades'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

def allowed_file(filename):
    """Valida si la extensión del archivo está permitida"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Crear directorio si no existe
os.makedirs(UPLOAD_FOLDER_NOVEDADES, exist_ok=True)

# Decorador para verificar login
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'usuario_id' not in session:
            flash('Debe iniciar sesión para acceder a esta página', 'warning')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

# Decorador para verificar permisos específicos
def permission_required(module, action=None):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            from utils.permissions import can_access
            if not can_access(module, action):
                flash('No tiene permisos para realizar esta acción', 'danger')
                return redirect(url_for('solicitudes.ver_solicitudes'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

@solicitudes_bp.route('/')
@login_required
def ver_solicitudes():
    """Muestra la página principal de solicitudes"""
    try:
        # Obtener parámetros de filtro
        filtro_estado = request.args.get('estado', 'todos')
        filtro_oficina = request.args.get('oficina', 'todas')
        filtro_material = request.args.get('material', '')
        filtro_solicitante = request.args.get('solicitante', '')
        
        # Obtener solicitudes con filtros
        solicitudes = SolicitudModel.obtener_todas(
            estado=filtro_estado if filtro_estado != 'todos' else None,
            oficina=filtro_oficina if filtro_oficina != 'todas' else None,
            material=filtro_material if filtro_material else None,
            solicitante=filtro_solicitante if filtro_solicitante else None
        )
        
        # Obtener estadísticas usando los IDs correctos
        total_solicitudes = len(solicitudes)
        
        # Mapear nombres de estado a IDs
        estado_ids = {
            'pendiente': 1,
            'aprobada': 2,
            'rechazada': 3,
            'entregada_parcial': 4,
            'completada': 5,
            'devuelta': 6,
            'novedad_registrada': 7,
            'novedad_aceptada': 8,
            'novedad_rechazada': 9
        }
        
        # Contar por estado usando los IDs
        solicitudes_pendientes = len([s for s in solicitudes if s.get('estado_id') == estado_ids['pendiente']])
        solicitudes_aprobadas = len([s for s in solicitudes if s.get('estado_id') == estado_ids['aprobada']])
        solicitudes_rechazadas = len([s for s in solicitudes if s.get('estado_id') == estado_ids['rechazada']])
        solicitudes_completadas = len([s for s in solicitudes if s.get('estado_id') == estado_ids['completada']])
        solicitudes_devueltas = len([s for s in solicitudes if s.get('estado_id') == estado_ids['devuelta']])
        
        # Novedades (estados 7, 8, 9)
        solicitudes_novedad = len([s for s in solicitudes if s.get('estado_id') in [7, 8, 9]])
        
        # Obtener lista de oficinas únicas para el filtro
        from models.oficinas_model import OficinaModel
        oficinas = OficinaModel.obtener_todas()
        oficinas_unique = [o['nombre'] for o in oficinas if o['nombre']]
        
        return render_template('solicitudes.html',
            solicitudes=solicitudes,
            total_solicitudes=total_solicitudes,
            solicitudes_pendientes=solicitudes_pendientes,
            solicitudes_aprobadas=solicitudes_aprobadas,
            solicitudes_rechazadas=solicitudes_rechazadas,
            solicitudes_completadas=solicitudes_completadas,
            solicitudes_devueltas=solicitudes_devueltas,
            solicitudes_novedad=solicitudes_novedad,
            oficinas_unique=oficinas_unique,
            filtro_estado=filtro_estado,
            filtro_oficina=filtro_oficina
        )
    except Exception as e:
        logger.error(f"Error al cargar solicitudes: {e}", exc_info=True)
        flash('Error al cargar las solicitudes', 'danger')
        return render_template('solicitudes.html', solicitudes=[], total_solicitudes=0)

@solicitudes_bp.route('/api/<int:solicitud_id>/info-devolucion')
@login_required
def obtener_info_devolucion(solicitud_id):
    """Obtiene información para la devolución de una solicitud"""
    try:
        conn = get_database_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                sm.SolicitudId,
                sm.CantidadEntregada,
                m.NombreElemento as material_nombre,
                u.NombreUsuario as solicitante_nombre
            FROM SolicitudesMaterial sm
            INNER JOIN Materiales m ON sm.MaterialId = m.MaterialId
            INNER JOIN Usuarios u ON sm.UsuarioSolicitante = u.NombreUsuario
            WHERE sm.SolicitudId = ?
        """, (solicitud_id,))
        
        row = cursor.fetchone()
        
        if row:
            # Calcular cantidad ya devuelta
            cursor.execute("""
                SELECT SUM(CantidadDevuelta) as total_devuelto
                FROM Devoluciones
                WHERE SolicitudId = ?
            """, (solicitud_id,))
            
            devolucion_row = cursor.fetchone()
            cantidad_ya_devuelta = devolucion_row[0] if devolucion_row and devolucion_row[0] else 0
            
            return jsonify({
                'success': True,
                'solicitud_id': row[0],
                'cantidad_entregada': row[1] or 0,
                'cantidad_ya_devuelta': cantidad_ya_devuelta,
                'material_nombre': row[2] or 'No especificado',
                'solicitante_nombre': row[3] or 'No especificado'
            })
        else:
            return jsonify({'success': False, 'error': 'Solicitud no encontrada'}), 404
            
    except Exception as e:
        logger.error(f"Error obteniendo info de devolución: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

@solicitudes_bp.route('/api/<int:solicitud_id>/novedad')
@login_required
def obtener_novedad_solicitud(solicitud_id):
    """Obtiene la novedad asociada a una solicitud"""
    try:
        conn = get_database_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                ns.NovedadId as novedad_id,
                ns.SolicitudId,
                ns.TipoNovedad,
                ns.Descripcion,
                ns.EstadoNovedad as estado,
                ns.UsuarioRegistra,
                ns.FechaRegistro,
                ns.CantidadAfectada,
                ns.RutaImagen as imagen_url
            FROM NovedadesSolicitudes ns
            WHERE ns.SolicitudId = ?
            ORDER BY ns.FechaRegistro DESC
        """, (solicitud_id,))
        
        row = cursor.fetchone()
        
        if row:
            novedad = {
                'novedad_id': row[0],
                'solicitud_id': row[1],
                'tipo_novedad': row[2],
                'descripcion': row[3],
                'estado_novedad': row[4],
                'usuario_registra': row[5],
                'fecha_registro': row[6].strftime('%Y-%m-%d %H:%M:%S') if row[6] else '',
                'cantidad_afectada': row[7],
                'imagen_url': row[8]
            }
            return jsonify({'success': True, 'novedad': novedad})
        else:
            return jsonify({'success': False, 'error': 'No se encontró novedad'}), 404
            
    except Exception as e:
        logger.error(f"Error obteniendo novedad: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

@solicitudes_bp.route('/registrar-novedad', methods=['POST'])
@login_required
@permission_required('novedades', 'create')
def registrar_novedad():
    """
    Registra una nueva novedad asociada a una solicitud
    Permite adjuntar una imagen como evidencia
    """
    try:
        solicitud_id = request.form.get('solicitud_id')
        tipo_novedad = request.form.get('tipo_novedad')
        descripcion = request.form.get('descripcion')
        cantidad_afectada = request.form.get('cantidad_afectada')
        usuario_reporta = session.get('usuario_nombre') or session.get('nombre_usuario')
        
        # Validación de campos obligatorios
        if not all([solicitud_id, tipo_novedad, descripcion, cantidad_afectada]):
            logger.warning(f'Intento de registro de novedad con datos incompletos')
            return jsonify({'success': False, 'error': 'Faltan datos requeridos'}), 400
        
        # Validar que la cantidad afectada sea un número positivo
        try:
            cantidad_afectada = int(cantidad_afectada)
            if cantidad_afectada <= 0:
                return jsonify({'success': False, 'error': 'La cantidad afectada debe ser mayor que 0'}), 400
        except ValueError:
            return jsonify({'success': False, 'error': 'Cantidad afectada inválida'}), 400
        
        # Verificar que la solicitud esté en estado aprobada (2) o entregada parcial (4)
        conn = get_database_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT EstadoId, CantidadEntregada 
            FROM SolicitudesMaterial 
            WHERE SolicitudId = ?
        """, (solicitud_id,))
        
        row = cursor.fetchone()
        if not row:
            return jsonify({'success': False, 'error': 'Solicitud no encontrada'}), 404
        
        estado_actual = row[0]
        cantidad_entregada = row[1] or 0
        
        # Solo se pueden registrar novedades en solicitudes aprobadas o entregadas parcialmente
        if estado_actual not in [2, 4]:  # 2 = Aprobada, 4 = Entregada Parcial
            return jsonify({'success': False, 'error': 'Solo se pueden registrar novedades en solicitudes aprobadas o entregadas parcialmente'}), 400
        
        # Validar que la cantidad afectada no supere la cantidad entregada
        if cantidad_afectada > cantidad_entregada:
            return jsonify({'success': False, 'error': f'La cantidad afectada ({cantidad_afectada}) no puede superar la cantidad entregada ({cantidad_entregada})'}), 400
        
        cursor.close()
        conn.close()
        
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
            else:
                return jsonify({'success': False, 'error': 'Formato de imagen no permitido'}), 400
        
        # Inserción en base de datos usando el modelo actualizado
        success = NovedadModel.crear_con_imagen(
            solicitud_id=int(solicitud_id),
            tipo_novedad=tipo_novedad,
            descripcion=descripcion,
            cantidad_afectada=cantidad_afectada,
            usuario_reporta=usuario_reporta,
            ruta_imagen=ruta_imagen
        )
        
        if success:
            # Actualizar estado de la solicitud a "Novedad Registrada" (EstadoId = 7)
            conn = get_database_connection()
            cursor = conn.cursor()
            try:
                cursor.execute("""
                    UPDATE SolicitudesMaterial 
                    SET EstadoId = 7, TieneNovedad = 1
                    WHERE SolicitudId = ?
                """, (solicitud_id,))
                conn.commit()
            finally:
                cursor.close()
                conn.close()
            
            logger.info(f'Novedad registrada exitosamente. Solicitud ID: {solicitud_id}, Usuario: {usuario_reporta}')
            return jsonify({
                'success': True, 
                'message': 'Novedad registrada correctamente'
            })
        else:
            return jsonify({'success': False, 'error': 'Error al registrar la novedad en la base de datos'}), 500
        
    except Exception as e:
        logger.error(f'Error al registrar novedad: {str(e)}', exc_info=True)
        return jsonify({'success': False, 'error': 'Error interno del servidor'}), 500

@solicitudes_bp.route('/gestionar-novedad', methods=['POST'])
@login_required
@permission_required('novedades', 'manage')
def gestionar_novedad():
    """
    Gestiona una novedad existente (aceptar/rechazar)
    Solo para roles: administrador, lider_inventario, aprobador
    """
    try:
        solicitud_id = request.form.get('solicitud_id')
        accion = request.form.get('accion')
        observaciones = request.form.get('observaciones', '')
        usuario_gestion = session.get('usuario_nombre') or session.get('nombre_usuario')
        
        if not all([solicitud_id, accion, usuario_gestion]):
            logger.warning(f'Intento de gestión de novedad con datos incompletos')
            return jsonify({'success': False, 'message': 'Datos incompletos'}), 400

        # Obtener la novedad más reciente de la solicitud
        novedades = NovedadModel.obtener_por_solicitud(int(solicitud_id))
        if not novedades:
            logger.warning(f'No se encontraron novedades para la solicitud ID: {solicitud_id}')
            return jsonify({'success': False, 'message': 'No se encontró novedad para esta solicitud'}), 404

        novedad = novedades[0]
        novedad_id = novedad.get('id') or novedad.get('novedad_id')

        # Determinar estados según la acción
        if accion == 'aceptar':
            nuevo_estado_novedad = 'aceptada'
            nuevo_estado_solicitud_id = 8  # EstadoId para "Novedad Aceptada"
            log_action = 'aceptada'
        else:
            nuevo_estado_novedad = 'rechazada'
            nuevo_estado_solicitud_id = 9  # EstadoId para "Novedad Rechazada"
            log_action = 'rechazada'

        # Actualizar estado de la novedad
        success_novedad = NovedadModel.actualizar_estado(
            novedad_id=novedad_id,
            nuevo_estado=nuevo_estado_novedad,
            usuario_resuelve=usuario_gestion,
            comentario=observaciones
        )

        if success_novedad:
            # Actualizar estado de la solicitud
            conn = get_database_connection()
            cursor = conn.cursor()
            try:
                cursor.execute("""
                    UPDATE SolicitudesMaterial 
                    SET EstadoId = ?
                    WHERE SolicitudId = ?
                """, (nuevo_estado_solicitud_id, solicitud_id))
                conn.commit()
                
                logger.info(f'Novedad {log_action}. Solicitud ID: {solicitud_id}, Usuario: {usuario_gestion}')
                return jsonify({
                    'success': True, 
                    'message': f'Novedad {nuevo_estado_novedad} exitosamente'
                })
            finally:
                cursor.close()
                conn.close()
        else:
            logger.error(f'Error al actualizar estado de novedad. Novedad ID: {novedad_id}')
            return jsonify({'success': False, 'message': 'Error al procesar la novedad'}), 500

    except Exception as e:
        logger.error(f'Error en gestión de novedad: {e}', exc_info=True)
        return jsonify({'success': False, 'message': 'Error interno del servidor'}), 500

@solicitudes_bp.route('/aprobar/<int:solicitud_id>', methods=['POST'])
@login_required
@permission_required('solicitudes', 'approve')
def aprobar_solicitud(solicitud_id):
    """Aprueba una solicitud completa"""
    try:
        # Obtener aprobador_id del usuario actual
        aprobador_id = session.get('aprobador_id')
        if not aprobador_id:
            # Si no tiene aprobador_id asignado, usar el aprobador por defecto (1)
            aprobador_id = 1
        
        # Llamar al stored procedure para aprobar la solicitud
        conn = get_database_connection()
        cursor = conn.cursor()
        
        cursor.execute("EXEC sp_AprobarSolicitud @SolicitudId = ?, @AprobadorId = ?", 
                      (solicitud_id, aprobador_id))
        
        conn.commit()
        
        flash('Solicitud aprobada correctamente', 'success')
        return redirect(url_for('solicitudes.ver_solicitudes'))
        
    except Exception as e:
        logger.error(f'Error al aprobar solicitud: {e}', exc_info=True)
        flash(f'Error al aprobar solicitud: {str(e)}', 'danger')
        return redirect(url_for('solicitudes.ver_solicitudes'))
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

@solicitudes_bp.route('/aprobar_parcial/<int:solicitud_id>', methods=['POST'])
@login_required
@permission_required('solicitudes', 'partial_approve')
def aprobar_parcial_solicitud(solicitud_id):
    """Aprueba parcialmente una solicitud"""
    try:
        cantidad_aprobada = request.form.get('cantidad_aprobada')
        if not cantidad_aprobada:
            flash('Debe especificar la cantidad a aprobar', 'danger')
            return redirect(url_for('solicitudes.ver_solicitudes'))
        
        cantidad_aprobada = int(cantidad_aprobada)
        if cantidad_aprobada <= 0:
            flash('La cantidad debe ser mayor que 0', 'danger')
            return redirect(url_for('solicitudes.ver_solicitudes'))
        
        # Obtener aprobador_id del usuario actual
        aprobador_id = session.get('aprobador_id', 1)
        
        # Llamar al stored procedure para aprobar parcialmente
        conn = get_database_connection()
        cursor = conn.cursor()
        
        cursor.execute("EXEC sp_AprobarParcialSolicitud @SolicitudId = ?, @AprobadorId = ?, @CantidadAprobada = ?", 
                      (solicitud_id, aprobador_id, cantidad_aprobada))
        
        conn.commit()
        
        flash('Solicitud aprobada parcialmente correctamente', 'success')
        return redirect(url_for('solicitudes.ver_solicitudes'))
        
    except Exception as e:
        logger.error(f'Error al aprobar parcialmente solicitud: {e}', exc_info=True)
        flash(f'Error al aprobar parcialmente: {str(e)}', 'danger')
        return redirect(url_for('solicitudes.ver_solicitudes'))
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

@solicitudes_bp.route('/rechazar/<int:solicitud_id>', methods=['POST'])
@login_required
@permission_required('solicitudes', 'reject')
def rechazar_solicitud(solicitud_id):
    """Rechaza una solicitud"""
    try:
        observacion = request.form.get('observacion', '')
        aprobador_id = session.get('aprobador_id', 1)
        
        conn = get_database_connection()
        cursor = conn.cursor()
        
        cursor.execute("EXEC sp_RechazarSolicitud @SolicitudId = ?, @AprobadorId = ?, @Observacion = ?", 
                      (solicitud_id, aprobador_id, observacion))
        
        conn.commit()
        
        flash('Solicitud rechazada correctamente', 'success')
        return redirect(url_for('solicitudes.ver_solicitudes'))
        
    except Exception as e:
        logger.error(f'Error al rechazar solicitud: {e}', exc_info=True)
        flash(f'Error al rechazar solicitud: {str(e)}', 'danger')
        return redirect(url_for('solicitudes.ver_solicitudes'))
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

@solicitudes_bp.route('/devolucion/<int:solicitud_id>', methods=['POST'])
@login_required
@permission_required('solicitudes', 'return')
def registrar_devolucion(solicitud_id):
    """Registra una devolución"""
    try:
        cantidad_devuelta = request.form.get('cantidad_devuelta')
        observacion = request.form.get('observacion', '')
        usuario_id = session.get('usuario_id')
        
        if not cantidad_devuelta or not usuario_id:
            flash('Datos incompletos', 'danger')
            return redirect(url_for('solicitudes.ver_solicitudes'))
        
        cantidad_devuelta = int(cantidad_devuelta)
        if cantidad_devuelta <= 0:
            flash('La cantidad debe ser mayor que 0', 'danger')
            return redirect(url_for('solicitudes.ver_solicitudes'))
        
        conn = get_database_connection()
        cursor = conn.cursor()
        
        cursor.execute("EXEC sp_RegistrarDevolucion @SolicitudId = ?, @UsuarioId = ?, @CantidadDevuelta = ?, @Observacion = ?", 
                      (solicitud_id, usuario_id, cantidad_devuelta, observacion))
        
        conn.commit()
        
        flash('Devolución registrada correctamente', 'success')
        return redirect(url_for('solicitudes.ver_solicitudes'))
        
    except Exception as e:
        logger.error(f'Error al registrar devolución: {e}', exc_info=True)
        flash(f'Error al registrar devolución: {str(e)}', 'danger')
        return redirect(url_for('solicitudes.ver_solicitudes'))
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

@solicitudes_bp.route('/api/novedades/pendientes')
@login_required
def obtener_novedades_pendientes():
    """
    Obtiene todas las novedades en estado pendiente
    Requiere permisos específicos de gestión
    """
    from utils.permissions import can_manage_novedad
    
    if not can_manage_novedad():
        logger.warning(f'Usuario sin permisos intentó acceder a novedades pendientes. Rol: {session.get("rol")}')
        return jsonify({'success': False, 'message': 'No tiene permisos'}), 403

    try:
        novedades = NovedadModel.obtener_todas(filtro_estado='registrada')
        logger.info(f'Consulta de novedades pendientes. Usuario: {session.get("usuario_id")}')
        return jsonify({'success': True, 'novedades': novedades})
    except Exception as e:
        logger.error(f'Error al obtener novedades pendientes: {e}', exc_info=True)
        return jsonify({'success': False, 'message': 'Error interno del servidor'}), 500