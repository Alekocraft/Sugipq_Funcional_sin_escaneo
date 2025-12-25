# app/app.py - Archivo principal unificado

import os
import logging
from datetime import datetime, timedelta
from flask import (
    Flask, render_template, request, redirect, session, flash,
    jsonify, url_for, send_file, g, make_response
)
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
import uuid
import json
import traceback

# ============================================================================
# CONFIGURACIÓN DE LOGGING
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuración de logging para LDAP
ldap_logger = logging.getLogger('ldap3')
ldap_logger.setLevel(logging.WARNING)

# Configurar formato para LDAP
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Crear directorio de logs si no existe
log_dir = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'logs')
os.makedirs(log_dir, exist_ok=True)

# Configurar handler para archivo de LDAP
ldap_log_file = os.path.join(log_dir, 'ldap.log')
file_handler = logging.FileHandler(ldap_log_file)
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(formatter)
ldap_logger.addHandler(file_handler)

# También configurar un handler para consola (opcional)
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.WARNING)
console_handler.setFormatter(formatter)
ldap_logger.addHandler(console_handler)

logger.info(f"Logging de LDAP configurado. Archivo: {ldap_log_file}")

# ============================================================================
# CONFIGURACIÓN DE LA APLICACIÓN FLASK
# ============================================================================

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, 'templates'),
    static_folder=os.path.join(BASE_DIR, 'static')
)

# Configuración de seguridad y aplicación
app.secret_key = os.environ.get('SECRET_KEY', os.urandom(32))
app.config['JSON_AS_ASCII'] = False
app.config['TEMPLATES_AUTO_RELOAD'] = True

# Configuración de archivos subidos
UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
logger.info(f"Directorio de uploads configurado en: {os.path.abspath(UPLOAD_FOLDER)}")

# Configuración de sesión segura
app.config['SESSION_COOKIE_SECURE'] = os.environ.get('FLASK_ENV') == 'production'
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=8)

# Tiempo de inactividad (minutos)
SESSION_TIMEOUT_MINUTES = 30

# ============================================================================
# CONEXIÓN A BASE DE DATOS Y MODELOS
# ============================================================================

# Importación de modelos
try:
    from models.materiales_model import MaterialModel
    from models.oficinas_model import OficinaModel
    from models.solicitudes_model import SolicitudModel
    from models.usuarios_model import UsuarioModel
    from models.inventario_corporativo_model import InventarioCorporativoModel
    logger.info("Modelos cargados correctamente")
except ImportError as e:
    logger.error(f"Error cargando modelos: {e}")
    # Definir clases dummy para evitar errores
    class MaterialModel: pass
    class OficinaModel: pass
    class SolicitudModel: pass
    class UsuarioModel: pass
    class InventarioCorporativoModel: pass

# Importación de utilidades
try:
    from utils.filters import filtrar_por_oficina_usuario, verificar_acceso_oficina
    from utils.initialization import inicializar_oficina_principal
    from utils.permissions import (
        can_access, can_view_actions,
        get_accessible_modules,
        can_create_novedad, can_manage_novedad,
        can_approve_solicitud, can_approve_partial_solicitud,
        can_reject_solicitud, can_return_solicitud,
        can_view_novedades, user_can_view_all
    )
    logger.info("Utilidades cargadas correctamente")
except ImportError as e:
    logger.error(f"Error cargando utilidades: {e}")
    # Definir funciones dummy
    def filtrar_por_oficina_usuario(*args, **kwargs): return []
    def verificar_acceso_oficina(*args, **kwargs): return True
    def inicializar_oficina_principal(): pass
    def can_access(*args, **kwargs): return True
    def can_view_actions(*args, **kwargs): return True
    def get_accessible_modules(*args, **kwargs): return []
    def can_create_novedad(*args, **kwargs): return True
    def can_manage_novedad(*args, **kwargs): return True
    def can_approve_solicitud(*args, **kwargs): return True
    def can_approve_partial_solicitud(*args, **kwargs): return True
    def can_reject_solicitud(*args, **kwargs): return True
    def can_return_solicitud(*args, **kwargs): return True
    def can_view_novedades(*args, **kwargs): return True
    def user_can_view_all(*args, **kwargs): return True

# Importar funciones de permisos para templates
try:
    from utils.permissions_functions import PERMISSION_FUNCTIONS
    logger.info("Funciones de permisos para templates cargadas correctamente")
except ImportError as e:
    logger.warning(f"No se encontró permissions_functions.py, usando funciones por defecto: {e}")
    PERMISSION_FUNCTIONS = {}

# ============================================================================
# IMPORTACIÓN CONDICIONAL DE BLUEPRINTS
# ============================================================================

# Importación de blueprints principales (siempre disponibles)
try:
    from blueprints.auth import auth_bp
    from blueprints.materiales import materiales_bp
    from blueprints.solicitudes import solicitudes_bp
    from blueprints.oficinas import oficinas_bp
    from blueprints.aprobadores import aprobadores_bp
    from blueprints.reportes import reportes_bp
    from blueprints.api import api_bp
    from blueprints.usuarios import usuarios_bp
    logger.info("Blueprints principales cargados correctamente")
except ImportError as e:
    logger.error(f"Error cargando blueprints principales: {e}")
    # Crear blueprints dummy
    from flask import Blueprint
    auth_bp = Blueprint('auth', __name__)
    materiales_bp = Blueprint('materiales', __name__)
    solicitudes_bp = Blueprint('solicitudes', __name__)
    oficinas_bp = Blueprint('oficinas', __name__)
    aprobadores_bp = Blueprint('aprobadores', __name__)
    reportes_bp = Blueprint('reportes', __name__)
    api_bp = Blueprint('api', __name__)
    usuarios_bp = Blueprint('usuarios', __name__)

# Importación condicional de blueprint de préstamos
try:
    from blueprints.prestamos import prestamos_bp
    logger.info("Blueprint de préstamos cargado exitosamente")
except ImportError as e:
    logger.warning(f"Blueprint de préstamos no disponible: {e}")
    from flask import Blueprint
    prestamos_bp = Blueprint('prestamos', __name__)
    
    @prestamos_bp.route('/')
    def prestamos_vacio():
        flash('Módulo de préstamos no disponible', 'warning')
        return redirect('/dashboard')

# Importación condicional de blueprint de inventario corporativo
try:
    from blueprints.inventario_corporativo import inventario_corporativo_bp
    logger.info("Blueprint de inventario corporativo cargado desde blueprints")
except ImportError as e:
    logger.warning(f"Blueprint de inventario corporativo no encontrado en blueprints: {e}")
    try:
        from routes_inventario_corporativo import bp_inv as inventario_corporativo_bp
        logger.info("Blueprint de inventario corporativo cargado desde routes_inventario_corporativo")
    except ImportError as e2:
        logger.warning(f"Blueprint de inventario corporativo no disponible: {e2}")
        from flask import Blueprint
        inventario_corporativo_bp = Blueprint('inventario_corporativo', __name__)
        
        @inventario_corporativo_bp.route('/')
        def inventario_vacio():
            flash('Módulo de inventario corporativo no disponible', 'warning')
            return redirect('/dashboard')

# ============================================================================
# MIDDLEWARE DE SESIÓN
# ============================================================================

@app.before_request
def check_session_timeout():
    """Verifica timeout de sesión antes de cada request"""
    # Rutas públicas que no requieren verificación
    public_routes = ['/login', '/logout', '/static', '/api/session-check', 
                     '/auth/login', '/auth/logout', '/auth/test-ldap']
    
    if any(request.path.startswith(route) for route in public_routes):
        return
    
    if 'usuario_id' in session:
        last_activity = session.get('last_activity')
        if last_activity:
            try:
                if isinstance(last_activity, str):
                    last_activity = datetime.fromisoformat(last_activity)
                
                inactive_time = datetime.now() - last_activity
                if inactive_time > timedelta(minutes=SESSION_TIMEOUT_MINUTES):
                    logger.info(f"Sesión expirada por inactividad: {session.get('usuario')}")
                    session.clear()
                    flash('Su sesión ha expirado por inactividad. Por favor, inicie sesión nuevamente.', 'warning')
                    return redirect('/auth/login')
            except Exception as e:
                logger.warning(f"Error verificando timeout de sesión: {e}")

@app.after_request
def update_session_activity(response):
    """Actualiza timestamp de actividad después de cada request"""
    if 'usuario_id' in session and response.status_code < 400:
        session['last_activity'] = datetime.now().isoformat()
        session.modified = True
    return response

# ============================================================================
# FUNCIONES DE PERMISOS PARA TEMPLATES (DEFINIDAS LOCALMENTE)
# ============================================================================

# Roles con permisos completos
ROLES_GESTION_COMPLETA = ['administrador', 'lider_inventario', 'aprobador']

# Roles de oficina
ROLES_OFICINA = [
    'oficina_coq', 'oficina_cali', 'oficina_pereira', 'oficina_neiva',
    'oficina_kennedy', 'oficina_bucaramanga', 'oficina_polo_club',
    'oficina_nogal', 'oficina_tunja', 'oficina_cartagena', 'oficina_morato',
    'oficina_medellin', 'oficina_cedritos', 'oficina_lourdes', 'oficina_regular'
]

def get_user_role():
    """Obtiene el rol del usuario actual"""
    return session.get('rol', '').lower()

def has_gestion_completa():
    """Verifica si el usuario tiene permisos de gestión completa"""
    return get_user_role() in ROLES_GESTION_COMPLETA

def is_oficina_role():
    """Verifica si el usuario tiene rol de oficina"""
    return get_user_role() in ROLES_OFICINA

def can_create_or_view():
    """Verifica si puede crear novedades o ver detalles"""
    rol = get_user_role()
    return rol in ROLES_GESTION_COMPLETA or rol in ROLES_OFICINA

def should_show_devolucion_button(solicitud):
    """Determina si mostrar botón de devolución"""
    if not solicitud:
        return False
    if not can_create_or_view():
        return False
    
    estado_id = solicitud.get('estado_id') or 1
    estados_permitidos = [2, 4, 5]  # Aprobada, Entregada Parcial, Completada
    
    if estado_id not in estados_permitidos:
        return False
    
    cantidad_entregada = solicitud.get('cantidad_entregada', 0) or 0
    cantidad_devuelta = solicitud.get('cantidad_devuelta', 0) or 0
    
    return cantidad_entregada > cantidad_devuelta

def should_show_novedad_button(solicitud):
    """Determina si mostrar botón de crear novedad"""
    if not solicitud:
        return False
    if not can_create_or_view():
        return False
    
    estado_id = solicitud.get('estado_id') or 1
    estados_permitidos = [2, 4, 5]  # Aprobada, Entregada Parcial, Completada
    estados_con_novedad = [7, 8, 9]
    
    if estado_id in estados_con_novedad:
        return False
    
    return estado_id in estados_permitidos

def should_show_gestion_novedad_button(solicitud):
    """Determina si mostrar botón de gestionar novedad (aprobar/rechazar)"""
    if not solicitud:
        return False
    if not has_gestion_completa():
        return False
    
    estado_id = solicitud.get('estado_id') or 1
    return estado_id == 7  # Novedad Registrada

def should_show_aprobacion_buttons(solicitud):
    """Determina si mostrar botones de aprobación/rechazo de solicitudes"""
    if not solicitud:
        return False
    if not has_gestion_completa():
        return False
    
    estado_id = solicitud.get('estado_id') or 1
    return estado_id == 1  # Pendiente

def should_show_detalle_button(solicitud):
    """Determina si mostrar botón de ver detalles"""
    return solicitud is not None and can_create_or_view()

# ============================================================================
# CONTEXT PROCESSOR
# ============================================================================

@app.context_processor
def utility_processor():
    """Inyecta funciones de permisos en todos los templates"""
    all_functions = {}
    
    # Agregar funciones principales de utils.permissions
    try:
        all_functions.update({
            'can_access': can_access,
            'can_create_novedad': can_create_novedad,
            'can_manage_novedad': can_manage_novedad,
            'can_view_novedades': can_view_novedades,
            'can_approve_solicitud': can_approve_solicitud,
            'can_reject_solicitud': can_reject_solicitud,
            'can_return_solicitud': can_return_solicitud,
            'can_approve_partial_solicitud': can_approve_partial_solicitud,
            'can_view_actions': can_view_actions,
            'get_accessible_modules': get_accessible_modules,
            'user_can_view_all': user_can_view_all
        })
    except Exception as e:
        logger.error(f"No se pudieron importar funciones de permisos: {e}")
    
    # Agregar funciones de PERMISSION_FUNCTIONS si existen
    if PERMISSION_FUNCTIONS:
        all_functions.update(PERMISSION_FUNCTIONS)
    
    # AGREGAR FUNCIONES should_show_* LOCALES (SIEMPRE)
    all_functions.update({
        'should_show_devolucion_button': should_show_devolucion_button,
        'should_show_novedad_button': should_show_novedad_button,
        'should_show_gestion_novedad_button': should_show_gestion_novedad_button,
        'should_show_aprobacion_buttons': should_show_aprobacion_buttons,
        'should_show_detalle_button': should_show_detalle_button,
        'has_gestion_completa': has_gestion_completa,
        'is_oficina_role': is_oficina_role,
        'can_create_or_view': can_create_or_view,
        'get_user_role': get_user_role,
        'filtrar_por_oficina_usuario': filtrar_por_oficina_usuario,
        'verificar_acceso_oficina': verificar_acceso_oficina,
    })
    
    # Funciones adicionales
    def can_view_solicitud_detalle():
        """Todos los roles pueden ver detalles de solicitudes"""
        return True
    
    def get_estados_novedad():
        """Obtiene los estados de novedad"""
        return {
            'registrada': 'registrada',
            'aceptada': 'aceptada', 
            'rechazada': 'rechazada'
        }
    
    all_functions.update({
        'can_view_solicitud_detalle': can_view_solicitud_detalle,
        'get_estados_novedad': get_estados_novedad,
        'session_timeout_minutes': SESSION_TIMEOUT_MINUTES
    })
    
    return all_functions

# ============================================================================
# REGISTRO DE BLUEPRINTS
# ============================================================================

 
app.register_blueprint(auth_bp, name='auth_bp')
app.register_blueprint(materiales_bp)
app.register_blueprint(solicitudes_bp, url_prefix='/solicitudes')
app.register_blueprint(oficinas_bp)
app.register_blueprint(aprobadores_bp)
app.register_blueprint(reportes_bp)
app.register_blueprint(api_bp)
app.register_blueprint(usuarios_bp)

# Registrar blueprints opcionales
app.register_blueprint(prestamos_bp, url_prefix='/prestamos')
logger.info("Blueprint de préstamos registrado")

app.register_blueprint(inventario_corporativo_bp, url_prefix='/inventario-corporativo')
logger.info("Blueprint de inventario corporativo registrado")

# ============================================================================
# RUTAS PRINCIPALES (UNIFICADAS)
# ============================================================================

@app.route('/')
def index():
    """Redirige usuarios autenticados al dashboard, otros al login"""
    if 'usuario_id' in session:
        return redirect('/dashboard')
    return redirect('/auth/login')

@app.route('/dashboard')
def dashboard():
    """Página principal del dashboard de la aplicación"""
    if 'usuario_id' not in session:
        logger.warning("Intento de acceso al dashboard sin autenticación")
        return redirect('/auth/login')
    
    try:
        oficina_id = None if user_can_view_all() else session.get('oficina_id')
        
        materiales = MaterialModel.obtener_todos(oficina_id) or []
        oficinas = OficinaModel.obtener_todas() or []
        solicitudes = SolicitudModel.obtener_todas(oficina_id) or []
        aprobadores = UsuarioModel.obtener_aprobadores() or []
        
        return render_template('dashboard.html',
            materiales=materiales,
            oficinas=oficinas,
            solicitudes=solicitudes,
            aprobadores=aprobadores
        )
    except Exception as e:
        logger.error(f"Error cargando dashboard: {e}")
        return render_template('dashboard.html',
            materiales=[],
            oficinas=[],
            solicitudes=[],
            aprobadores=[]
        )

@app.route('/logout', methods=['GET', 'POST'])
def logout():
    """Redirige logout al blueprint de auth"""
    return redirect('/auth/logout')

@app.route('/test-ldap', methods=['GET', 'POST'])
def test_ldap():
    """Redirige a la ruta de test-ldap en auth"""
    return redirect('/auth/test-ldap')

# ============================================================================
# RUTAS DE AUTENTICACIÓN (BACKUP PARA CASO DE ERROR)
# ============================================================================

@app.route('/login', methods=['GET', 'POST'])
def login_backup():
    """Ruta de login de respaldo en caso de error en blueprint"""
    try:
        # Si el blueprint de auth funciona, redirigir a él
        return redirect('/auth/login')
    except:
        # Si hay error, mostrar formulario básico
        if request.method == 'POST':
            username = request.form.get('username')
            password = request.form.get('password')
            
            # Aquí iría la lógica de autenticación de respaldo
            flash('Autenticación no disponible temporalmente. Contacte al administrador.', 'danger')
        
        return render_template('auth/login_backup.html')

# ============================================================================
# API DE ESTADO DE SESIÓN
# ============================================================================

@app.route('/api/session-check')
def api_session_check():
    """API para verificar estado de sesión (útil para JavaScript)"""
    if 'usuario_id' not in session:
        return jsonify({'authenticated': False, 'reason': 'no_session'})
    
    last_activity = session.get('last_activity')
    if last_activity:
        try:
            if isinstance(last_activity, str):
                last_activity = datetime.fromisoformat(last_activity)
            
            inactive_time = datetime.now() - last_activity
            remaining_seconds = (timedelta(minutes=SESSION_TIMEOUT_MINUTES) - inactive_time).total_seconds()
            
            if remaining_seconds <= 0:
                return jsonify({'authenticated': False, 'reason': 'timeout'})
            
            return jsonify({
                'authenticated': True,
                'user': session.get('usuario_nombre'),
                'remaining_seconds': max(0, int(remaining_seconds)),
                'timeout_minutes': SESSION_TIMEOUT_MINUTES
            })
        except Exception:
            pass
    
    return jsonify({'authenticated': True, 'user': session.get('usuario_nombre')})

# ============================================================================
# RUTAS DE MATERIALES (BACKUP)
# ============================================================================

@app.route('/materiales')
def materiales_backup():
    """Ruta de respaldo para materiales"""
    if 'usuario_id' not in session:
        return redirect('/auth/login')
    
    try:
        # Usar el filtrado por oficina si no es administrador
        oficina_id = None if user_can_view_all() else session.get('oficina_id')
        materiales = MaterialModel.obtener_todos(oficina_id) or []
        
        return render_template('materiales/index.html', 
            materiales=materiales,
            can_edit=has_gestion_completa()
        )
    except Exception as e:
        logger.error(f"Error en ruta de materiales: {e}")
        flash('Error cargando materiales', 'danger')
        return redirect('/dashboard')

@app.route('/materiales/crear', methods=['GET', 'POST'])
def crear_material_backup():
    """Ruta de respaldo para crear material"""
    if 'usuario_id' not in session:
        return redirect('/auth/login')
    
    if not has_gestion_completa():
        flash('No tiene permisos para crear materiales', 'danger')
        return redirect('/materiales')
    
    if request.method == 'POST':
        try:
            nombre = request.form.get('nombre')
            descripcion = request.form.get('descripcion')
            stock = int(request.form.get('stock', 0))
            stock_minimo = int(request.form.get('stock_minimo', 0))
            categoria = request.form.get('categoria')
            
            if not nombre:
                flash('El nombre es requerido', 'danger')
                return render_template('materiales/crear.html')
            
            nuevo_material = {
                'nombre': nombre,
                'descripcion': descripcion,
                'stock': stock,
                'stock_minimo': stock_minimo,
                'categoria': categoria
            }
            
            MaterialModel.crear(nuevo_material)
            flash('Material creado exitosamente', 'success')
            return redirect('/materiales')
            
        except Exception as e:
            logger.error(f"Error creando material: {e}")
            flash('Error creando material', 'danger')
    
    return render_template('materiales/crear.html')

# ============================================================================
# RUTAS DE SOLICITUDES (BACKUP)
# ============================================================================

@app.route('/solicitudes/listar')
def listar_solicitudes_backup():
    """Ruta de respaldo para listar solicitudes"""
    if 'usuario_id' not in session:
        return redirect('/auth/login')
    
    try:
        oficina_id = None if user_can_view_all() else session.get('oficina_id')
        solicitudes = SolicitudModel.obtener_todas(oficina_id) or []
        
        return render_template('solicitudes/listar.html',
            solicitudes=solicitudes
        )
    except Exception as e:
        logger.error(f"Error listando solicitudes: {e}")
        flash('Error cargando solicitudes', 'danger')
        return redirect('/dashboard')

@app.route('/solicitudes/crear', methods=['GET', 'POST'])
def crear_solicitud_backup():
    """Ruta de respaldo para crear solicitud"""
    if 'usuario_id' not in session:
        return redirect('/auth/login')
    
    if request.method == 'POST':
        try:
            material_id = request.form.get('material_id')
            cantidad = int(request.form.get('cantidad', 1))
            comentario = request.form.get('comentario', '')
            
            if not material_id or cantidad <= 0:
                flash('Datos inválidos', 'danger')
                return redirect('/solicitudes/crear')
            
            nueva_solicitud = {
                'material_id': material_id,
                'usuario_id': session.get('usuario_id'),
                'cantidad': cantidad,
                'comentario': comentario,
                'estado': 'pendiente'
            }
            
            SolicitudModel.crear(nueva_solicitud)
            flash('Solicitud creada exitosamente', 'success')
            return redirect('/solicitudes')
            
        except Exception as e:
            logger.error(f"Error creando solicitud: {e}")
            flash('Error creando solicitud', 'danger')
    
    # Obtener materiales disponibles
    try:
        oficina_id = None if user_can_view_all() else session.get('oficina_id')
        materiales = MaterialModel.obtener_todos(oficina_id) or []
    except:
        materiales = []
    
    return render_template('solicitudes/crear.html',
        materiales=materiales
    )

# ============================================================================
# RUTAS DE OFICINAS (BACKUP)
# ============================================================================

@app.route('/oficinas')
def listar_oficinas_backup():
    """Ruta de respaldo para listar oficinas"""
    if 'usuario_id' not in session:
        return redirect('/auth/login')
    
    if not has_gestion_completa():
        flash('No tiene permisos para ver oficinas', 'danger')
        return redirect('/dashboard')
    
    try:
        oficinas = OficinaModel.obtener_todas() or []
        return render_template('oficinas/index.html', oficinas=oficinas)
    except Exception as e:
        logger.error(f"Error listando oficinas: {e}")
        flash('Error cargando oficinas', 'danger')
        return redirect('/dashboard')

# ============================================================================
# RUTAS DE USUARIOS (BACKUP)
# ============================================================================

@app.route('/usuarios')
def listar_usuarios_backup():
    """Ruta de respaldo para listar usuarios"""
    if 'usuario_id' not in session:
        return redirect('/auth/login')
    
    if not has_gestion_completa():
        flash('No tiene permisos para ver usuarios', 'danger')
        return redirect('/dashboard')
    
    try:
        usuarios = UsuarioModel.obtener_todos() or []
        return render_template('usuarios/index.html', usuarios=usuarios)
    except Exception as e:
        logger.error(f"Error listando usuarios: {e}")
        flash('Error cargando usuarios', 'danger')
        return redirect('/dashboard')

# ============================================================================
# RUTAS DE REPORTES (BACKUP)
# ============================================================================

@app.route('/reportes')
def reportes_backup():
    """Ruta de respaldo para reportes"""
    if 'usuario_id' not in session:
        return redirect('/auth/login')
    
    if not has_gestion_completa():
        flash('No tiene permisos para ver reportes', 'danger')
        return redirect('/dashboard')
    
    return render_template('reportes/index.html')

# ============================================================================
# MANEJADORES DE ERRORES
# ============================================================================

@app.errorhandler(404)
def pagina_no_encontrada(error):
    """Maneja errores 404 - Página no encontrada"""
    logger.warning(f"Página no encontrada: {request.path}")
    return render_template('error/404.html'), 404

@app.errorhandler(500)
def error_interno(error):
    """Maneja errores 500 - Error interno del servidor"""
    logger.error(f"Error interno del servidor: {error}", exc_info=True)
    return render_template('error/500.html'), 500

@app.errorhandler(413)
def archivo_demasiado_grande(error):
    """Maneja errores 413 - Archivo demasiado grande"""
    logger.warning(f"Intento de subir archivo demasiado grande: {request.url}")
    flash('El archivo es demasiado grande. Tamaño máximo: 16MB', 'danger')
    return redirect(request.referrer or '/')

@app.errorhandler(401)
def no_autorizado(error):
    """Maneja errores 401 - No autorizado"""
    logger.warning(f"Acceso no autorizado: {request.path}")
    flash('No está autorizado para acceder a esta página', 'danger')
    return redirect('/auth/login')

# ============================================================================
# RUTAS DE SISTEMA
# ============================================================================

@app.route('/system/health')
def system_health():
    """Endpoint de salud del sistema"""
    try:
        # Verificar conexión a base de datos
        from database import get_database_connection
        conn = get_database_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT 1')
        cursor.close()
        conn.close()
        
        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'database': 'connected',
            'session': 'active' if 'usuario_id' in session else 'inactive',
            'blueprints': {
                'auth': 'registered',
                'materiales': 'registered',
                'solicitudes': 'registered',
                'oficinas': 'registered',
                'usuarios': 'registered'
            }
        })
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'timestamp': datetime.now().isoformat(),
            'error': str(e)
        }), 500

@app.route('/system/info')
def system_info():
    """Información del sistema"""
    info = {
        'app_name': 'Sistema de Gestión de Inventarios',
        'version': '1.0.0',
        'environment': os.environ.get('FLASK_ENV', 'development'),
        'python_version': os.sys.version,
        'debug': app.debug,
        'session_timeout_minutes': SESSION_TIMEOUT_MINUTES,
        'upload_folder': app.config['UPLOAD_FOLDER'],
        'registered_blueprints': list(app.blueprints.keys())
    }
    return jsonify(info)

# ============================================================================
# PUNTO DE ENTRADA
# ============================================================================

if __name__ == '__main__':
    logger.info("Iniciando servidor Flask de Sistema de Gestión de Inventarios")
    logger.info(f"Logging de LDAP activo en: {ldap_log_file}")
    
    try:
        # Inicialización del sistema
        inicializar_oficina_principal()
        logger.info("Sistema inicializado correctamente")
    except Exception as e:
        logger.error(f"Error en inicialización: {e}")
    
    # Configuración del puerto
    port = int(os.environ.get('PORT', 5010))
    logger.info(f"Servidor iniciado en puerto: {port}")
    
    # Verificar estructura de carpetas
    required_folders = ['templates', 'static', 'static/uploads', 'logs']
    for folder in required_folders:
        folder_path = os.path.join(BASE_DIR, folder)
        if not os.path.exists(folder_path):
            os.makedirs(folder_path, exist_ok=True)
            logger.info(f"Carpeta creada: {folder_path}")
    
    app.run(
        debug=True,
        host='0.0.0.0',
        port=port
    )