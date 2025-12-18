# app/blueprints/solicitudes.py
import os
import json
import traceback
from datetime import datetime

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session,
    jsonify,
    Response
)
from werkzeug.utils import secure_filename

from models.solicitudes_model import SolicitudModel
from models.materiales_model import MaterialModel
from models.oficinas_model import OficinaModel
from models.novedades_model import NovedadModel

from utils.auth import login_required, role_required
from utils.permissions import can_create_novedad, can_manage_novedad
from utils.filters import verificar_acceso_oficina

solicitudes_bp = Blueprint('solicitudes', __name__)

UPLOAD_FOLDER_NOVEDADES = 'static/images/novedades'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
os.makedirs(UPLOAD_FOLDER_NOVEDADES, exist_ok=True)


def allowed_file(filename: str) -> bool:
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def _check_novedad_create_permissions() -> bool:
    return can_create_novedad()


def _check_novedad_manage_permissions() -> bool:
    return can_manage_novedad()


@solicitudes_bp.route('/')
@login_required
def listar_solicitudes():
    try:
        filtro_estado = request.args.get('estado', 'todos')
        filtro_oficina = request.args.get('oficina', 'todas')

        rol = (session.get('rol') or '').lower()
        oficina_id = session.get('oficina_id')

        if rol in ['administrador', 'aprobador', 'lider_inventario'
                   , 'oficina_coq']:
            if filtro_oficina != 'todas' and str(filtro_oficina).isdigit():
                solicitudes = SolicitudModel.obtener_todas_ordenadas(int(filtro_oficina))
            else:
                solicitudes = SolicitudModel.obtener_todas_ordenadas()
        else:
            solicitudes = SolicitudModel.obtener_todas_ordenadas(oficina_id)

        if filtro_estado != 'todos':
            estado_map = {
                'pendiente': 'Pendiente',
                'aprobada': 'Aprobada',
                'rechazada': 'Rechazada',
                'devuelta': 'Devuelta'
            }
            estado_filtro = estado_map.get(filtro_estado, '')
            if estado_filtro:
                solicitudes = [s for s in solicitudes if (s.get('estado') or '') == estado_filtro]

        materiales = MaterialModel.obtener_todos()
        materiales_dict = {}
        for m in materiales:
            mid = m.get('id') or m.get('material_id')
            if mid is None:
                continue
            materiales_dict[mid] = {
                'cantidad_disponible': m.get('stock_disponible') or m.get('cantidad_disponible', 0),
                'ruta_imagen': m.get('ruta_imagen', '')
            }

        oficinas_unique = list(set([s.get('oficina_nombre') for s in solicitudes if s.get('oficina_nombre')]))

        total_solicitudes = len(solicitudes)
        solicitudes_pendientes = len([s for s in solicitudes if (s.get('estado') or '') == 'Pendiente'])
        solicitudes_aprobadas = len([s for s in solicitudes if (s.get('estado') or '') == 'Aprobada'])
        solicitudes_rechazadas = len([s for s in solicitudes if (s.get('estado') or '') == 'Rechazada'])
        solicitudes_devueltas = len([s for s in solicitudes if (s.get('estado') or '') == 'Devuelta'])

        return render_template(
            'solicitudes/solicitudes.html',
            solicitudes=solicitudes,
            materiales_dict=materiales_dict,
            oficinas_unique=oficinas_unique,
            total_solicitudes=total_solicitudes,
            solicitudes_pendientes=solicitudes_pendientes,
            solicitudes_aprobadas=solicitudes_aprobadas,
            solicitudes_rechazadas=solicitudes_rechazadas,
            solicitudes_devueltas=solicitudes_devueltas,
            filtro_estado=filtro_estado,
            filtro_oficina=filtro_oficina
        )
    except Exception as e:
        flash(f'Error al cargar solicitudes: {str(e)}', 'error')
        return render_template(
            'solicitudes/solicitudes.html',
            solicitudes=[],
            materiales_dict={},
            oficinas_unique=[],
            total_solicitudes=0,
            solicitudes_pendientes=0,
            solicitudes_aprobadas=0,
            solicitudes_rechazadas=0,
            solicitudes_devueltas=0,
            filtro_estado='todos',
            filtro_oficina='todas'
        )


@solicitudes_bp.route('/crear', methods=['GET', 'POST'])
@login_required
def crear_solicitud():
    if request.method == 'GET':
        materiales = MaterialModel.obtener_todos()
        oficinas = OficinaModel.obtener_todas()
        return render_template(
            'solicitudes/crear.html',
            materiales=materiales,
            oficinas=oficinas
        )

    try:
        oficina_id = int(request.form['oficina_id'])
        material_id = int(request.form['material_id'])
        cantidad_solicitada = int(request.form['cantidad_solicitada'])
        porcentaje_oficina = float(request.form['porcentaje_oficina'])
        usuario_nombre = session.get('usuario_nombre') or session.get('user_name', 'Usuario')
        observacion = request.form.get('observacion', '')

        if cantidad_solicitada <= 0:
            flash('La cantidad debe ser mayor a 0', 'error')
            return redirect(url_for('solicitudes.crear_solicitud'))

        if porcentaje_oficina < 0 or porcentaje_oficina > 100:
            flash('El porcentaje debe estar entre 0 y 100', 'error')
            return redirect(url_for('solicitudes.crear_solicitud'))

        solicitud_id = SolicitudModel.crear(
            oficina_id,
            material_id,
            cantidad_solicitada,
            porcentaje_oficina,
            usuario_nombre,
            observacion
        )

        if solicitud_id:
            flash('✅ Solicitud creada exitosamente', 'success')
        else:
            flash('❌ Error al crear la solicitud', 'error')

    except Exception as e:
        flash(f'❌ Error: {str(e)}', 'error')

    return redirect(url_for('solicitudes.listar_solicitudes'))


# ============================
# FUNCIONES DE APROBACIÓN
# ============================

@solicitudes_bp.route('/aprobar/<int:solicitud_id>', methods=['POST'])
@login_required
@role_required('administrador', 'aprobador', 'lider_inventario')
def aprobar_solicitud(solicitud_id):
    """Ruta para aprobar completamente una solicitud - CORREGIDA"""
    try:
        solicitud = SolicitudModel.obtener_por_id(solicitud_id)
        if not solicitud or not verificar_acceso_oficina(solicitud.get('oficina_id')):
            flash('No tiene permisos para aprobar esta solicitud', 'danger')
            return redirect('/solicitudes')

        usuario_id = session.get('usuario_id') or session.get('user_id')
        
      
        success, message = SolicitudModel.aprobar(solicitud_id, usuario_id)
        
        if success:
            flash('✅ Solicitud aprobada y stock actualizado exitosamente', 'success')
        else:
            flash(f'❌ {message}', 'danger')
            
    except Exception as e:
        print(f"❌ Error aprobando solicitud: {e}")
        traceback.print_exc()
        flash(f'❌ Error al aprobar la solicitud: {str(e)}', 'danger')
    
    return redirect(url_for('solicitudes.listar_solicitudes'))


@solicitudes_bp.route('/aprobar_parcial/<int:solicitud_id>', methods=['POST'])
@login_required
@role_required('administrador', 'aprobador', 'lider_inventario')
def aprobar_parcial_solicitud(solicitud_id):
    try:
        solicitud = SolicitudModel.obtener_por_id(solicitud_id)
        if not solicitud or not verificar_acceso_oficina(solicitud.get('oficina_id')):
            flash('No tiene permisos para aprobar esta solicitud', 'danger')
            return redirect('/solicitudes')

        usuario_id = session.get('usuario_id') or session.get('user_id')
        cantidad_aprobada = int(request.form.get('cantidad_aprobada', 0))

        if cantidad_aprobada <= 0:
            flash('La cantidad aprobada debe ser mayor que 0', 'danger')
            return redirect('/solicitudes')

        success, message = SolicitudModel.aprobar_parcial(solicitud_id, usuario_id, cantidad_aprobada)
        
        if success:
            flash(message, 'success')
        else:
            flash(message, 'danger')
    except ValueError:
        flash('La cantidad aprobada debe ser un número válido', 'danger')
    except Exception as e:
        print(f"❌ Error aprobando parcialmente solicitud: {e}")
        flash('Error al aprobar parcialmente la solicitud', 'danger')
    
    return redirect(url_for('solicitudes.listar_solicitudes'))


@solicitudes_bp.route('/rechazar/<int:solicitud_id>', methods=['POST'])
@login_required
@role_required('administrador', 'aprobador', 'lider_inventario')
def rechazar_solicitud(solicitud_id):
    """Ruta CORREGIDA para rechazar solicitudes - FUNCIONA AHORA"""
    try:
        # Obtener la solicitud
        solicitud = SolicitudModel.obtener_por_id(solicitud_id)
        if not solicitud:
            flash('❌ Solicitud no encontrada', 'danger')
            return redirect(url_for('solicitudes.listar_solicitudes'))
        
        # Verificar permisos de acceso a la oficina
        if not verificar_acceso_oficina(solicitud.get('oficina_id')):
            flash('❌ No tiene permisos para rechazar esta solicitud', 'danger')
            return redirect(url_for('solicitudes.listar_solicitudes'))

        # Obtener datos del formulario
        usuario_id = session.get('usuario_id') or session.get('user_id')
        observacion = request.form.get('observacion', '').strip()
        
        if not observacion:
            flash('❌ Debe ingresar un motivo para rechazar la solicitud', 'danger')
            return redirect(url_for('solicitudes.listar_solicitudes'))
             
        success = SolicitudModel.rechazar(solicitud_id, usuario_id, observacion)
        
        if success:
            flash('✅ Solicitud rechazada exitosamente', 'success')
        else:
            flash('❌ Error al rechazar la solicitud', 'danger')
            
    except Exception as e:
        print(f"❌ Error rechazando solicitud: {e}")
        traceback.print_exc()
        flash(f'❌ Error al rechazar la solicitud: {str(e)}', 'danger')
    
    return redirect(url_for('solicitudes.listar_solicitudes'))


# ============================
# DEVOLUCIONES
# ============================

@solicitudes_bp.route('/devolucion/<int:solicitud_id>', methods=['POST'])
@login_required
@role_required('administrador', 'aprobador', 'lider_inventario')
def registrar_devolucion(solicitud_id):
    try:
        cantidad_devuelta = int(request.form.get('cantidad_devuelta') or 0)
        observacion = request.form.get('observacion_devolucion', '')
        usuario_nombre = session.get('usuario_nombre') or session.get('user_name', 'Usuario')

        if cantidad_devuelta <= 0:
            flash('❌ La cantidad a devolver debe ser mayor a 0', 'error')
            return redirect(url_for('solicitudes.listar_solicitudes'))

        success, message = SolicitudModel.registrar_devolucion(
            solicitud_id,
            cantidad_devuelta,
            usuario_nombre,
            observacion
        )

        flash(message, 'success' if success else 'error')
    except ValueError:
        flash('❌ Cantidad inválida', 'error')
    except Exception as e:
        flash(f'❌ Error al procesar la devolución: {str(e)}', 'error')

    return redirect(url_for('solicitudes.listar_solicitudes'))


@solicitudes_bp.route('/api/<int:solicitud_id>/info-devolucion')
@login_required
def api_info_devolucion(solicitud_id):
    try:
        print(f"🔍 DEBUG api_info_devolucion() - solicitud_id={solicitud_id}")
        info = SolicitudModel.obtener_info_devolucion(solicitud_id)
        print(f"🔍 DEBUG api_info_devolucion() - info devuelta por modelo: {info}")

        if not info:
            resp = {"error": "Solicitud no encontrada"}
            return Response(json.dumps(resp), status=404, mimetype="application/json")

        resp = {
            "solicitud_id": int(info.get("solicitud_id", 0)),
            "estado_id": int(info.get("estado_id", 0)),
            "estado": info.get("estado") or "",
            "cantidad_solicitada": int(info.get("cantidad_solicitada", 0)),
            "cantidad_entregada": int(info.get("cantidad_entregada", 0)),
            "cantidad_ya_devuelta": int(info.get("cantidad_ya_devuelta", 0)),
            "cantidad_puede_devolver": int(info.get("cantidad_puede_devolver", 0)),
            "material_nombre": info.get("material_nombre") or "",
            "oficina_nombre": info.get("oficina_nombre") or "",
            "solicitante_nombre": info.get("solicitante_nombre") or "",
        }

        print(f"✅ DEBUG api_info_devolucion() - respuesta JSON final: {resp}")
        return Response(json.dumps(resp, default=str), status=200, mimetype="application/json")

    except Exception as e:
        print("❌ ERROR api_info_devolucion:", str(e))
        traceback.print_exc()
        resp = {"error": "Error interno del servidor", "detalle": str(e)}
        return Response(json.dumps(resp, default=str), status=500, mimetype="application/json")


@solicitudes_bp.route('/api/pendientes')
@login_required
def api_solicitudes_pendientes():
    try:
        rol = (session.get('rol') or '').lower()
        oficina_id = session.get('oficina_id')
        if rol in ['administrador', 'aprobador', 'lider_inventario', 'oficina_coq']:
            solicitudes = SolicitudModel.obtener_para_aprobador()
        else:
            solicitudes = SolicitudModel.obtener_para_aprobador(oficina_id)
        return jsonify(solicitudes)
    except Exception:
        return jsonify({'error': 'Error interno del servidor'}), 500


# ==========
# NOVEDADES 
# ==========


@solicitudes_bp.route('/registrar-novedad', methods=['POST'])
@login_required
def registrar_novedad():
    if not _check_novedad_create_permissions():
        return jsonify({'success': False, 'message': 'No tiene permisos para crear novedades'}), 403

    try:
        print("🔍 DEBUG: Llegó a registrar_novedad")
        solicitud_id = request.form.get('solicitud_id')
        tipo_novedad = request.form.get('tipo_novedad')
        descripcion = request.form.get('descripcion')
        cantidad_afectada = request.form.get('cantidad_afectada')
        imagen = request.files.get('imagen_novedad')

        usuario_registra = session.get('usuario_nombre') or session.get('user_name', 'Usuario')
        print(f"🔍 DEBUG: Iniciando registro de novedad - Usuario: {usuario_registra}")
        print(f"🔍 DEBUG: Datos recibidos - solicitud_id: {solicitud_id}, tipo: {tipo_novedad}")

        if not all([solicitud_id, tipo_novedad, descripcion, cantidad_afectada]):
            return jsonify({'success': False, 'message': 'Todos los campos son obligatorios'}), 400

        if not imagen or imagen.filename == '':
            return jsonify({'success': False, 'message': 'La imagen es obligatoria'}), 400

        if not allowed_file(imagen.filename):
            return jsonify({'success': False, 'message': 'Tipo de archivo no permitido'}), 400

        filename = secure_filename(imagen.filename)
        name, ext = os.path.splitext(filename)
        filename = f"{name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}{ext}"

        filepath = os.path.join(UPLOAD_FOLDER_NOVEDADES, filename)
        os.makedirs(UPLOAD_FOLDER_NOVEDADES, exist_ok=True)
        print(f"🔍 DEBUG: Guardando imagen en: {filepath}")
        imagen.save(filepath)
        print("✅ DEBUG: Imagen guardada correctamente")

        ruta_imagen_db = f"images/novedades/{filename}"

        print("🔍 DEBUG: Creando novedad en BD...")
        success = NovedadModel.crear(
            solicitud_id=int(solicitud_id),
            tipo_novedad=tipo_novedad,
            descripcion=descripcion,
            cantidad_afectada=int(cantidad_afectada),
            usuario_registra=usuario_registra,
            ruta_imagen=ruta_imagen_db
        )

        if not success:
            print("❌ ERROR en registrar_novedad: fallo en NovedadModel.crear")
            return jsonify({'success': False, 'message': 'Error al registrar la novedad'}), 500

        SolicitudModel.actualizar_estado_solicitud(int(solicitud_id), 8)

        return jsonify({'success': True, 'message': 'Novedad registrada exitosamente'})
    except Exception as e:
        print("❌ ERROR en registrar_novedad:", str(e))
        traceback.print_exc()
        return jsonify({'success': False, 'message': 'Error interno del servidor'}), 500


@solicitudes_bp.route('/api/<int:solicitud_id>/novedad') 
@role_required('administrador', 'aprobador', 'lider_inventario')
def obtener_novedad_solicitud(solicitud_id):
    """Obtiene la última novedad de una solicitud - CORREGIDA CON CLAVES DE SESIÓN"""
    print(f"🔍 DEBUG obtener_novedad_solicitud: Llamando con solicitud_id={solicitud_id}")
    print(f"🔍 DEBUG Session data: usuario_id={session.get('usuario_id')}, usuario_nombre={session.get('usuario_nombre')}")
    
    try:
        # Obtener la última novedad
        novedad = NovedadModel.obtener_ultima_por_solicitud(solicitud_id)
        
        if not novedad:
            print(f"❌ DEBUG: No se encontró novedad para solicitud {solicitud_id}")
            return jsonify({
                'success': False,
                'error': 'No hay novedades registradas para esta solicitud'
            }), 404
        
        print(f"🔍 DEBUG: Novedad devuelta por modelo - Claves: {list(novedad.keys())}")
        
        # Obtener URL de imagen
        imagen_url = None
        ruta_imagen = novedad.get('RutaImagen') or novedad.get('ruta_imagen')
        print(f"🔍 DEBUG: Ruta imagen: {ruta_imagen}")
        
        if ruta_imagen:
            # Asegurar que la ruta sea correcta
            if not ruta_imagen.startswith('static/'):
                imagen_url = f"/static/{ruta_imagen}"
            else:
                imagen_url = f"/{ruta_imagen}"
            print(f"🔍 DEBUG: Imagen URL construida: {imagen_url}")
        
        # Formatear fecha_registro si es datetime
        fecha_registro = novedad.get('FechaRegistro') or novedad.get('fecha_reporte')
        
        if fecha_registro and hasattr(fecha_registro, 'strftime'):
            try:
                fecha_registro = fecha_registro.strftime('%d/%m/%Y %H:%M:%S')
            except Exception as e:
                fecha_registro = str(fecha_registro)
        
        # Preparar respuesta con todas las claves posibles para compatibilidad
        novedad_formateada = {
            'id': novedad.get('NovedadId') or novedad.get('id'),
            'novedad_id': novedad.get('NovedadId') or novedad.get('id'),
            'solicitud_id': novedad.get('SolicitudId') or novedad.get('solicitud_id'),
            'tipo_novedad': novedad.get('TipoNovedad') or novedad.get('tipo'),
            'descripcion': novedad.get('Descripcion') or novedad.get('descripcion'),
            'cantidad_afectada': novedad.get('CantidadAfectada') or novedad.get('cantidad_afectada'),
            'estado': novedad.get('EstadoNovedad') or novedad.get('estado'),
            'estado_novedad': novedad.get('EstadoNovedad') or novedad.get('estado'),
            'usuario_registra': novedad.get('UsuarioRegistra') or novedad.get('usuario_registra'),
            'fecha_registro': fecha_registro,
            'usuario_resuelve': novedad.get('UsuarioResuelve') or novedad.get('usuario_resuelve'),
            'fecha_resolucion': novedad.get('FechaResolucion'),
            'observaciones_resolucion': novedad.get('ObservacionesResolucion'),
            'ruta_imagen': ruta_imagen,
            'imagen_url': imagen_url
        }
        
        print(f"✅ DEBUG: Enviando respuesta exitosa")
        return jsonify({
            'success': True,
            'novedad': novedad_formateada
        })
        
    except Exception as e:
        print(f"❌ ERROR en obtener_novedad_solicitud: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': 'Error al obtener la novedad'
        }), 500


@solicitudes_bp.route('/gestionar-novedad', methods=['POST'])
@login_required
def gestionar_novedad():
    print(f"🔍 DEBUG gestionar_novedad: Llamado - Session: usuario_id={session.get('usuario_id')}")
    
    try:
        solicitud_id = request.form.get('solicitud_id')
        accion = request.form.get('accion')
        observaciones = request.form.get('observaciones', '')
        
        print(f"🔍 DEBUG: Datos recibidos - solicitud_id={solicitud_id}, accion={accion}")
        
        if not solicitud_id or not accion:
            return jsonify({'success': False, 'message': 'Faltan datos'}), 400
        
        # Obtener todas las novedades de la solicitud
        novedades = NovedadModel.obtener_por_solicitud(int(solicitud_id))
        
        if not novedades:
            return jsonify({'success': False, 'message': 'No se encontraron novedades para esta solicitud'}), 404
        
        # Encontrar la novedad pendiente (la más reciente o la que tenga estado 'pendiente')
        novedad_a_gestionar = None
        for novedad in novedades:
            estado_novedad = novedad.get('estado', '').lower()
            if estado_novedad == 'pendiente':
                novedad_a_gestionar = novedad
                break
        
        # Si no hay pendiente, usar la más reciente (primera de la lista ordenada)
        if not novedad_a_gestionar and novedades:
            novedad_a_gestionar = novedades[0]
        
        if not novedad_a_gestionar:
            return jsonify({'success': False, 'message': 'No se encontró novedad para gestionar'}), 404
        
        print(f"🔍 DEBUG: Novedad a gestionar encontrada: ID={novedad_a_gestionar.get('id')}")
        
        # Determinar el nuevo estado basado en la acción
        if accion == 'aceptar':
            nuevo_estado = 'resuelta'
            estado_solicitud_id = 9  # ID para 'novedad_aceptada'
        elif accion == 'rechazar':
            nuevo_estado = 'rechazada'
            estado_solicitud_id = 10  # ID para 'novedad_rechazada'
        else:
            return jsonify({'success': False, 'message': 'Acción no válida'}), 400
        
        # Actualizar estado de la novedad
        novedad_id = novedad_a_gestionar.get('id')
        if not novedad_id:
            novedad_id = novedad_a_gestionar.get('novedad_id') or novedad_a_gestionar.get('NovedadId')
        
        if not novedad_id:
            return jsonify({'success': False, 'message': 'No se pudo identificar la novedad'}), 500
        
        # Obtener el usuario actual para registrar quién resuelve
        usuario_resuelve = session.get('usuario_nombre') or session.get('usuario', 'sistema')
        
        print(f"🔍 DEBUG: Actualizando novedad {novedad_id} a estado {nuevo_estado}")
        
        # Actualizar la novedad
        actualizado = NovedadModel.actualizar_estado(
            novedad_id=novedad_id,
            estado=nuevo_estado,
            usuario_resuelve=usuario_resuelve,
            observaciones_resolucion=observaciones
        )
        
        if not actualizado:
            return jsonify({'success': False, 'message': 'Error al actualizar la novedad'}), 500
        
        # Actualizar el estado de la solicitud - CORRECCIÓN
        print(f"🔍 DEBUG: Actualizando estado de solicitud {solicitud_id} a ID {estado_solicitud_id}")
        success_solicitud = SolicitudModel.actualizar_estado_solicitud(
            int(solicitud_id), 
            estado_solicitud_id
        )
        
        if not success_solicitud:
            return jsonify({'success': False, 'message': 'Novedad actualizada pero error al actualizar la solicitud'}), 500
        
        return jsonify({
            'success': True,
            'message': f'Novedad {accion}ada exitosamente'
        })
        
    except Exception as e:
        print(f"❌ ERROR en gestionar_novedad: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': 'Error interno del servidor'}), 500


@solicitudes_bp.route('/api/novedades/pendientes')
@login_required
def obtener_novedades_pendientes():
    if not _check_novedad_manage_permissions():
        return jsonify({'success': False, 'message': 'No tiene permisos para gestionar novedades'}), 403

    try:
        novedades = NovedadModel.obtener_novedades_pendientes()
        return jsonify({'success': True, 'novedades': novedades})
    except Exception:
        return jsonify({'success': False, 'message': 'Error interno'}), 500