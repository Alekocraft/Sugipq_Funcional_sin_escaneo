# blueprints/inventario_corporativo.py
# ARCHIVO ACTUALIZADO CON SOPORTE PARA ASIGNACIÓN A USUARIOS AD

from flask import Blueprint, render_template, request, redirect, session, flash, jsonify, send_file
from werkzeug.utils import secure_filename
from models.inventario_corporativo_model import InventarioCorporativoModel
from utils.permissions import can_access, can_manage_inventario_corporativo, can_view_inventario_actions
import os
import pandas as pd
from io import BytesIO
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# =====================================================
# IMPORTACIONES PARA AD Y NOTIFICACIONES
# =====================================================
try:
    from utils.ldap_auth import ad_auth
    LDAP_AVAILABLE = True
except ImportError:
    LDAP_AVAILABLE = False
    logger.warning("LDAP no disponible - búsqueda de usuarios AD deshabilitada")

try:
    from services.notification_service import NotificationService
    NOTIFICATIONS_AVAILABLE = True
except ImportError:
    NOTIFICATIONS_AVAILABLE = False
    logger.warning("Servicio de notificaciones no disponible")

# =====================================================
# CONFIGURACIÓN DEL BLUEPRINT
# =====================================================
inventario_corporativo_bp = Blueprint(
    'inventario_corporativo',
    __name__,
    template_folder='templates'
)

# =====================================================
# FUNCIONES AUXILIARES
# =====================================================
def _require_login():
    """Verifica si el usuario está autenticado"""
    return 'usuario_id' in session

def _handle_unauthorized():
    """Maneja acceso no autorizado"""
    flash('No autorizado', 'danger')
    return redirect('/inventario-corporativo')

def _handle_not_found():
    """Maneja recursos no encontrados"""
    flash('Producto no encontrado', 'danger')
    return redirect('/inventario-corporativo')

def _calculate_inventory_stats(productos):
    """Calcula estadísticas del inventario"""
    if not productos:
        return {
            'valor_total': 0,
            'productos_bajo_stock': 0,
            'productos_asignables': 0,
            'total_productos': 0
        }
    
    valor_total = sum(float(p.get('valor_unitario', 0)) * int(p.get('cantidad', 0)) for p in productos)
    productos_bajo_stock = len([p for p in productos if int(p.get('cantidad', 0)) <= int(p.get('cantidad_minima', 5))])
    productos_asignables = len([p for p in productos if p.get('es_asignable')])
    
    return {
        'valor_total': valor_total,
        'productos_bajo_stock': productos_bajo_stock,
        'productos_asignables': productos_asignables,
        'total_productos': len(productos)
    }

def _handle_image_upload(archivo, producto_actual=None):
    """Maneja la subida de imágenes"""
    if not archivo or not archivo.filename:
        return producto_actual.get('ruta_imagen') if producto_actual else None
    
    filename = secure_filename(archivo.filename)
    upload_dir = os.path.join('static', 'uploads', 'productos')
    os.makedirs(upload_dir, exist_ok=True)
    filepath = os.path.join(upload_dir, filename)
    archivo.save(filepath)
    return '/' + filepath.replace('\\', '/')

def _validate_product_form(categorias, proveedores):
    """Valida los datos del formulario de producto"""
    nombre = request.form.get('nombre', '').strip()
    categoria_id = request.form.get('categoria_id')
    proveedor_id = request.form.get('proveedor_id')
    
    errors = []
    
    if not nombre:
        errors.append('El nombre del producto es requerido')
    if not categoria_id or categoria_id == '0':
        errors.append('Debe seleccionar una categoría')
    if not proveedor_id or proveedor_id == '0':
        errors.append('Debe seleccionar un proveedor')
    
    if not categorias or not proveedores:
        errors.append('Error: No hay categorías o proveedores disponibles. Contacte al administrador.')
    
    if errors:
        for error in errors:
            flash(error, 'danger')
        return None
    
    return {
        'nombre': nombre,
        'categoria_id': int(categoria_id),
        'proveedor_id': int(proveedor_id),
        'valor_unitario': float(request.form.get('valor_unitario') or 0),
        'cantidad': int(request.form.get('cantidad') or 0),
        'cantidad_minima': int(request.form.get('cantidad_minima') or 5),
        'ubicacion': request.form.get('ubicacion', 'COQ').strip(),
        'descripcion': request.form.get('descripcion', '').strip(),
        'es_asignable': 1 if request.form.get('es_asignable') == 'on' else 0
    }

# =====================================================
# RUTAS PRINCIPALES
# =====================================================

@inventario_corporativo_bp.route('/')
def listar_inventario_corporativo():
    """Lista todo el inventario corporativo con estadísticas"""
    if not _require_login():
        return redirect('/login')

    productos = InventarioCorporativoModel.obtener_todos() or []
    stats = _calculate_inventory_stats(productos)

    return render_template(
        'inventario_corporativo/listar.html',
        productos=productos,
        valor_total_inventario=stats['valor_total'],
        **stats,
        puede_gestionar_inventario=can_manage_inventario_corporativo(),
        puede_ver_acciones_inventario=can_view_inventario_actions()
    )

@inventario_corporativo_bp.route('/<int:producto_id>')
def ver_detalle_producto(producto_id):
    """Muestra el detalle de un producto específico"""
    if not _require_login():
        return redirect('/login')

    if not can_access('inventario_corporativo', 'view'):
        return _handle_unauthorized()

    producto = InventarioCorporativoModel.obtener_por_id(producto_id)
    if not producto:
        return _handle_not_found()

    historial = InventarioCorporativoModel.historial_asignaciones(producto_id) or []

    return render_template(
        'inventario_corporativo/detalle.html',
        producto=producto,
        historial=historial,
        puede_gestionar_inventario=can_manage_inventario_corporativo()
    )

# =====================================================
# OPERACIONES CRUD
# =====================================================

@inventario_corporativo_bp.route('/crear', methods=['GET', 'POST'])
def crear_inventario_corporativo():
    """Crea un nuevo producto en el inventario"""
    if not _require_login():
        return redirect('/login')

    if not can_access('inventario_corporativo', 'create'):
        return _handle_unauthorized()

    categorias = InventarioCorporativoModel.obtener_categorias() or []
    proveedores = InventarioCorporativoModel.obtener_proveedores() or []

    if request.method == 'POST':
        try:
            form_data = _validate_product_form(categorias, proveedores)
            if not form_data:
                return render_template('inventario_corporativo/crear.html',
                                       categorias=categorias,
                                       proveedores=proveedores)

            archivo = request.files.get('imagen')
            if not archivo or archivo.filename == '':
                flash('La imagen es obligatoria.', 'danger')
                return render_template('inventario_corporativo/crear.html',
                                       categorias=categorias,
                                       proveedores=proveedores)

            codigo_unico = InventarioCorporativoModel.generar_codigo_unico()
            ruta_imagen = _handle_image_upload(archivo)

            nuevo_id = InventarioCorporativoModel.crear(
                codigo_unico=codigo_unico,
                usuario_creador=session.get('usuario', 'Sistema'),
                ruta_imagen=ruta_imagen,
                **form_data
            )

            if nuevo_id:
                flash('Producto creado correctamente.', 'success')
                return redirect('/inventario-corporativo')
            else:
                flash('No fue posible crear el producto.', 'danger')

        except Exception as e:
            flash('Ocurrió un error al guardar el producto.', 'danger')
            logger.error(f"[ERROR CREAR] {e}")

    return render_template('inventario_corporativo/crear.html',
                           categorias=categorias,
                           proveedores=proveedores)


@inventario_corporativo_bp.route('/editar/<int:producto_id>', methods=['GET', 'POST'])
def editar_producto_corporativo(producto_id):
    """Edita un producto existente"""
    if not _require_login():
        return redirect('/login')

    if not can_access('inventario_corporativo', 'edit'):
        return _handle_unauthorized()

    producto = InventarioCorporativoModel.obtener_por_id(producto_id)
    if not producto:
        return _handle_not_found()

    categorias = InventarioCorporativoModel.obtener_categorias() or []
    proveedores = InventarioCorporativoModel.obtener_proveedores() or []

    if request.method == 'POST':
        try:
            form_data = _validate_product_form(categorias, proveedores)
            if not form_data:
                return render_template('inventario_corporativo/editar.html',
                                    producto=producto,
                                    categorias=categorias,
                                    proveedores=proveedores)

            ruta_imagen = _handle_image_upload(request.files.get('imagen'), producto)

            actualizado = InventarioCorporativoModel.actualizar(
                producto_id=producto_id,
                codigo_unico=request.form.get('codigo_unico', '').strip(),
                ruta_imagen=ruta_imagen,
                **form_data
            )

            if actualizado:
                flash('Producto actualizado correctamente.', 'success')
                return redirect(f'/inventario-corporativo/{producto_id}')
            else:
                flash('No fue posible actualizar el producto.', 'danger')

        except Exception as e:
            logger.error(f"[ERROR EDITAR] {e}")
            flash('Error al actualizar el producto.', 'danger')

    return render_template(
        'inventario_corporativo/editar.html',
        producto=producto,
        categorias=categorias,
        proveedores=proveedores
    )

@inventario_corporativo_bp.route('/eliminar/<int:producto_id>', methods=['POST'])
def eliminar_producto_corporativo(producto_id):
    """Elimina un producto del inventario"""
    if not _require_login():
        return redirect('/login')

    if not can_access('inventario_corporativo', 'delete'):
        return _handle_unauthorized()

    try:
        eliminado = InventarioCorporativoModel.eliminar(
            producto_id=producto_id,
            usuario_accion=session.get('usuario', 'Sistema')
        )

        if eliminado:
            flash('Producto eliminado correctamente.', 'success')
        else:
            flash('No fue posible eliminar el producto.', 'danger')

    except Exception as e:
        logger.error(f"[ERROR ELIMINAR] {e}")
        flash('Error al eliminar producto.', 'danger')

    return redirect('/inventario-corporativo')

# =====================================================
# VISTAS ESPECÍFICAS POR UBICACIÓN
# =====================================================

def _render_filtered_view(productos, titulo, subtitulo, tipo):
    """Renderiza vista filtrada con estadísticas"""
    stats = _calculate_inventory_stats(productos)
    
    if tipo == 'oficinas':
        oficinas_unicas = set(p.get('oficina') for p in productos if p.get('oficina'))
        total_oficinas = len(oficinas_unicas)
    else:
        total_oficinas = 1

    return render_template(
        'inventario_corporativo/listar_con_filtros.html',
        productos=productos,
        oficinas_filtradas=InventarioCorporativoModel.obtener_oficinas() or [],
        categorias=InventarioCorporativoModel.obtener_categorias() or [],
        filtro_oficina='',
        filtro_categoria='',
        filtro_stock='',
        titulo=titulo,
        subtitulo=subtitulo,
        total_oficinas=total_oficinas,
        tipo=tipo,
        **stats,
        puede_gestionar_inventario=can_manage_inventario_corporativo(),
        puede_ver_acciones_inventario=can_view_inventario_actions()
    )

@inventario_corporativo_bp.route('/sede-principal')
def listar_sede_principal():
    """Lista productos de la sede principal"""
    if not _require_login():
        return redirect('/login')

    productos = InventarioCorporativoModel.obtener_por_sede_principal() or []
    return _render_filtered_view(productos, 'Sede Principal', 'Productos de la sede principal', 'sede')

@inventario_corporativo_bp.route('/oficinas-servicio')
def listar_oficinas_servicio():
    """Lista productos de oficinas de servicio"""
    if not _require_login():
        return redirect('/login')

    productos = InventarioCorporativoModel.obtener_por_oficinas_servicio() or []
    return _render_filtered_view(productos, 'Oficinas de Servicio', 'Productos en oficinas de servicio', 'oficinas')

# =====================================================
# ASIGNACIÓN DE PRODUCTOS - ACTUALIZADO CON USUARIOS AD
# =====================================================

@inventario_corporativo_bp.route('/asignar/<int:producto_id>', methods=['GET', 'POST'])
def asignar_producto_corporativo(producto_id):
    """Asigna un producto a una oficina y usuario del AD"""
    if not _require_login():
        return redirect('/login')

    if not can_access('inventario_corporativo', 'assign'):
        return _handle_unauthorized()

    producto = InventarioCorporativoModel.obtener_por_id(producto_id)
    if not producto:
        return _handle_not_found()

    if not producto.get('es_asignable'):
        flash('Este producto no es asignable.', 'warning')
        return redirect(f'/inventario-corporativo/{producto_id}')

    oficinas = InventarioCorporativoModel.obtener_oficinas() or []
    historial = InventarioCorporativoModel.historial_asignaciones(producto_id) or []

    if request.method == 'POST':
        try:
            oficina_id = int(request.form.get('oficina_id') or 0)
            cantidad_asignar = int(request.form.get('cantidad') or 0)
            
            # Nuevos campos para usuario AD
            usuario_ad_username = request.form.get('usuario_ad_username', '').strip()
            usuario_ad_nombre = request.form.get('usuario_ad_nombre', '').strip()
            usuario_ad_email = request.form.get('usuario_ad_email', '').strip()
            enviar_notificacion = request.form.get('enviar_notificacion') == 'on'

            # Validaciones
            if cantidad_asignar > producto.get('cantidad', 0):
                flash('No hay suficiente stock.', 'danger')
                return redirect(request.url)
            
            if not oficina_id:
                flash('Debe seleccionar una oficina.', 'danger')
                return redirect(request.url)

            # Obtener nombre de oficina para la notificación
            oficina_nombre = next(
                (o['nombre'] for o in oficinas if o['id'] == oficina_id), 
                'Oficina'
            )

            # Preparar información del usuario AD si se proporcionó
            usuario_ad_info = None
            if usuario_ad_username:
                usuario_ad_info = {
                    'username': usuario_ad_username,
                    'full_name': usuario_ad_nombre or usuario_ad_username,
                    'email': usuario_ad_email,
                    'department': ''
                }

            # Realizar asignación
            if usuario_ad_info:
                # Usar el método extendido para asignación con usuario AD
                from models.inventario_corporativo_model_extended import InventarioCorporativoModelExtended
                
                resultado = InventarioCorporativoModelExtended.asignar_a_usuario_ad(
                    producto_id=producto_id,
                    oficina_id=oficina_id,
                    cantidad=cantidad_asignar,
                    usuario_ad_info=usuario_ad_info,
                    usuario_accion=session.get('usuario', 'Sistema')
                )
                
                if resultado.get('success'):
                    flash('Producto asignado correctamente.', 'success')
                    
                    # Enviar notificación si está habilitado y hay email
                    if enviar_notificacion and usuario_ad_email and NOTIFICATIONS_AVAILABLE:
                        try:
                            NotificationService.enviar_notificacion_asignacion(
                                destinatario_email=usuario_ad_email,
                                destinatario_nombre=usuario_ad_nombre or usuario_ad_username,
                                producto_info=producto,
                                cantidad=cantidad_asignar,
                                oficina_nombre=oficina_nombre,
                                asignador_nombre=session.get('usuario_nombre', session.get('usuario', 'Sistema'))
                            )
                            flash(f'Notificación enviada a {usuario_ad_email}', 'info')
                        except Exception as e:
                            logger.error(f"Error enviando notificación: {e}")
                            flash('Producto asignado pero no se pudo enviar la notificación.', 'warning')
                    
                    return redirect(f'/inventario-corporativo/{producto_id}')
                else:
                    flash(resultado.get('message', 'No se pudo asignar el producto.'), 'danger')
            else:
                # Usar el método tradicional sin usuario AD específico
                asignado = InventarioCorporativoModel.asignar_a_oficina(
                    producto_id=producto_id,
                    oficina_id=oficina_id,
                    cantidad=cantidad_asignar,
                    usuario_accion=session.get('usuario', 'Sistema')
                )

                if asignado:
                    flash('Producto asignado correctamente.', 'success')
                    return redirect(f'/inventario-corporativo/{producto_id}')
                else:
                    flash('No se pudo asignar el producto.', 'danger')

        except Exception as e:
            logger.error(f"[ERROR ASIGNAR] {e}")
            flash('Error al asignar producto.', 'danger')

    return render_template(
        'inventario_corporativo/asignar.html',
        producto=producto,
        oficinas=oficinas,
        historial=historial,
        ldap_disponible=LDAP_AVAILABLE
    )

# =====================================================
# API PARA BÚSQUEDA DE USUARIOS AD
# =====================================================

@inventario_corporativo_bp.route('/api/buscar-usuarios-ad')
def api_buscar_usuarios_ad():
    """
    API para buscar usuarios en Active Directory.
    Parámetros:
        q: Término de búsqueda (mínimo 3 caracteres)
    """
    if not _require_login():
        return jsonify({'error': 'No autorizado'}), 401
    
    if not LDAP_AVAILABLE:
        return jsonify({
            'error': 'Búsqueda de usuarios AD no disponible',
            'usuarios': []
        }), 503

    termino = request.args.get('q', '').strip()
    
    if len(termino) < 3:
        return jsonify({
            'error': 'Ingrese al menos 3 caracteres para buscar',
            'usuarios': []
        })
    
    try:
        usuarios = ad_auth.search_user_by_name(termino)
        
        return jsonify({
            'success': True,
            'usuarios': usuarios,
            'total': len(usuarios)
        })
        
    except Exception as e:
        logger.error(f"Error buscando usuarios AD: {e}")
        return jsonify({
            'error': 'Error al buscar usuarios',
            'usuarios': []
        }), 500

@inventario_corporativo_bp.route('/api/obtener-usuario-ad/<username>')
def api_obtener_usuario_ad(username):
    """
    API para obtener detalles de un usuario específico del AD.
    """
    if not _require_login():
        return jsonify({'error': 'No autorizado'}), 401
    
    if not LDAP_AVAILABLE:
        return jsonify({'error': 'LDAP no disponible'}), 503

    try:
        usuarios = ad_auth.search_user_by_name(username)
        
        # Buscar usuario exacto
        usuario = next(
            (u for u in usuarios if u.get('usuario', '').lower() == username.lower()),
            None
        )
        
        if usuario:
            return jsonify({
                'success': True,
                'usuario': usuario
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Usuario no encontrado'
            }), 404
            
    except Exception as e:
        logger.error(f"Error obteniendo usuario AD: {e}")
        return jsonify({'error': 'Error al obtener usuario'}), 500

# =====================================================
# APIS Y EXPORTACIÓN
# =====================================================

@inventario_corporativo_bp.route('/api/estadisticas-dashboard')
def api_estadisticas_dashboard():
    """API para estadísticas del dashboard (vista general)"""
    if not _require_login():
        return jsonify({'error': 'No autorizado'}), 401

    try:
        productos_todos = InventarioCorporativoModel.obtener_todos() or []
        productos_sede = InventarioCorporativoModel.obtener_por_sede_principal() or []
        productos_oficinas = InventarioCorporativoModel.obtener_por_oficinas_servicio() or []
        
        stats_todos = _calculate_inventory_stats(productos_todos)
        
        return jsonify({
            "total_productos": stats_todos['total_productos'],
            "valor_total": stats_todos['valor_total'],
            "stock_bajo": stats_todos['productos_bajo_stock'],
            "productos_sede": len(productos_sede),
            "productos_oficinas": len(productos_oficinas)
        })
        
    except Exception as e:
        logger.error(f"Error en API estadísticas dashboard: {e}")
        return jsonify({
            "total_productos": 0,
            "valor_total": 0,
            "stock_bajo": 0,
            "productos_sede": 0,
            "productos_oficinas": 0
        })

@inventario_corporativo_bp.route('/api/estadisticas')
def api_estadisticas_inventario():
    """API para estadísticas generales del inventario."""
    if not _require_login():
        return jsonify({'error': 'No autorizado'}), 401

    try:
        productos = InventarioCorporativoModel.obtener_todos_con_oficina() or []
        stats = _calculate_inventory_stats(productos)

        productos_sede = [p for p in productos if not p.get('oficina') or p.get('oficina') == 'Sede Principal']
        productos_oficinas = [p for p in productos if p.get('oficina') and p.get('oficina') != 'Sede Principal']
        
        return jsonify({
            "total_productos": stats['total_productos'],
            "valor_total": stats['valor_total'],
            "stock_bajo": stats['productos_bajo_stock'],
            "productos_sede": len(productos_sede),
            "productos_oficinas": len(productos_oficinas)
        })
        
    except Exception as e:
        logger.error(f"Error en API estadísticas: {e}")
        return jsonify({
            "total_productos": 0,
            "valor_total": 0,
            "stock_bajo": 0,
            "productos_sede": 0,
            "productos_oficinas": 0
        })

@inventario_corporativo_bp.route('/exportar/excel/<tipo>')
def exportar_inventario_corporativo_excel(tipo):
    """Exporta el inventario a Excel"""
    if not _require_login():
        return redirect('/login')

    if not can_access('inventario_corporativo', 'view'):
        return _handle_unauthorized()

    productos = InventarioCorporativoModel.obtener_todos_con_oficina() or []
    df = pd.DataFrame(productos)

    output = BytesIO()
    df.to_excel(output, index=False)
    output.seek(0)

    return send_file(output, download_name='inventario_corporativo.xlsx', as_attachment=True)
