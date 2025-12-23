# blueprints/auth.py
from flask import Blueprint, render_template, request, redirect, session, flash, jsonify
from models.usuarios_model import UsuarioModel
import logging
from functools import wraps
import bcrypt
from database import get_database_connection

logger = logging.getLogger(__name__)
# CORRECCIÓN: Cambia 'auth_bp' por 'auth' y añade url_prefix
auth_bp = Blueprint('auth', __name__, url_prefix='/auth')  # <-- CAMBIADO

# ======================
# DECORADORES DE AYUDA
# ======================

def login_required(f):
    """Decorador para requerir autenticación"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'usuario_id' not in session:
            flash('Por favor inicie sesión para acceder a esta página', 'warning')
            return redirect('/auth/login')  # <-- Actualizado
        return f(*args, **kwargs)
    return decorated_function

def logout_required(f):
    """Decorador para requerir que el usuario NO esté autenticado"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'usuario_id' in session:
            return redirect('/dashboard')
        return f(*args, **kwargs)
    return decorated_function

# ======================
# FUNCIONES AUXILIARES
# ======================

def _setup_session(usuario_info):
    """Configura la sesión del usuario"""
    session['usuario_id'] = usuario_info['id']
    session['usuario_nombre'] = usuario_info['nombre']
    session['usuario'] = usuario_info['usuario']
    session['rol'] = usuario_info['rol']
    session['oficina_id'] = usuario_info.get('oficina_id', 1)
    session['oficina_nombre'] = usuario_info.get('oficina_nombre', '')

def _load_dashboard_data(oficina_id=None):
    """Carga todos los datos necesarios para el dashboard"""
    from models.materiales_model import MaterialModel
    from models.oficinas_model import OficinaModel
    from models.solicitudes_model import SolicitudModel
    
    materiales = MaterialModel.obtener_todos(oficina_id) or []
    oficinas = OficinaModel.obtener_todas() or []
    solicitudes = SolicitudModel.obtener_todas(oficina_id) or []
    aprobadores = UsuarioModel.obtener_aprobadores() or []
    
    return {
        'materiales': materiales,
        'oficinas': oficinas,
        'solicitudes': solicitudes,
        'aprobadores': aprobadores
    }

# ======================
# RUTAS DE AUTENTICACIÓN
# ======================

@auth_bp.route('/')
def index():
    """Redirige a dashboard si está autenticado, sino a login"""
    if 'usuario_id' in session:
        return redirect('/dashboard')
    return redirect('/auth/login')  # <-- Actualizado

@auth_bp.route('/login', methods=['GET', 'POST'])
@logout_required
def login():
    """Maneja el inicio de sesión de usuarios"""
    if request.method == 'POST':
        return _handle_login_post()
    return render_template('auth/login.html')

def _handle_login_post():
    """Maneja la lógica de POST para login"""
    usuario = request.form['usuario'].strip()
    contraseña = request.form['contraseña']
    
    logger.info(f"🔐 Login solicitado para: {usuario}")
    
    # Validación básica
    if not usuario or not contraseña:
        flash('Usuario y contraseña son requeridos', 'danger')
        return render_template('auth/login.html')
    
    try:
        usuario_info = UsuarioModel.verificar_credenciales(usuario, contraseña)
        
        if usuario_info:
            _setup_session(usuario_info)
            logger.info(f"✅ Login exitoso: {usuario} - Rol: {usuario_info['rol']}")
            flash(f'¡Bienvenido {usuario_info["nombre"]}!', 'success')
            return redirect('/dashboard')
        else:
            logger.warning(f"❌ Login fallido para: {usuario}")
            flash('Usuario o contraseña incorrectos', 'danger')
            
    except Exception as e:
        logger.error(f"❌ Error en login: {e}", exc_info=True)
        flash('Error del sistema durante el login. Contacte al administrador.', 'danger')
    
    return render_template('auth/login.html')

@auth_bp.route('/debug-login', methods=['POST'])
@logout_required
def debug_login():
    """Endpoint de debug para login"""
    usuario = request.form['usuario'].strip()
    contraseña = request.form['contraseña']
    
    print(f"\n🔍 DEBUG LOGIN ===================================")
    print(f"Usuario: {usuario}")
    print(f"Contraseña proporcionada: {contraseña}")
    
    # Llamar directamente al modelo
    from models.usuarios_model import UsuarioModel
    
    # 1. Verificar hash directamente
    conn = get_database_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT ContraseñaHash FROM Usuarios WHERE NombreUsuario = ?", (usuario,))
    row = cursor.fetchone()
    
    if row:
        stored_hash = row[0]
        print(f"Hash en BD: {stored_hash}")
        print(f"Longitud hash: {len(stored_hash)}")
        
        # Intentar verificar
        try:
            if bcrypt.checkpw(contraseña.encode('utf-8'), stored_hash.encode('utf-8')):
                print("✅ bcrypt.checkpw: TRUE")
            else:
                print("❌ bcrypt.checkpw: FALSE")
        except Exception as e:
            print(f"❌ Error bcrypt: {e}")
    else:
        print("❌ Usuario no encontrado en BD")
    
    conn.close()
    
    # 2. Llamar al modelo normal
    print(f"\n🔍 LLAMANDO A UsuarioModel.verificar_credenciales...")
    usuario_info = UsuarioModel.verificar_credenciales(usuario, contraseña)
    print(f"Resultado: {usuario_info}")
    
    if usuario_info:
        return jsonify({"success": True, "message": "Login exitoso (debug)"})
    else:
        return jsonify({"success": False, "message": "Login fallido (debug)"})

@auth_bp.route('/logout')
def logout():
    """Cierra la sesión del usuario"""
    usuario = session.get('usuario', 'Desconocido')
    session.clear()
    logger.info(f"🔒 Logout exitoso para: {usuario}")
    flash('Sesión cerrada correctamente', 'info')
    return redirect('/auth/login')  # <-- Actualizado

@auth_bp.route('/dashboard')
@login_required
def dashboard():
    """Dashboard principal de la aplicación"""
    try:
        logger.info("📊 Cargando dashboard...")
        
        # Determinar filtro de oficina según permisos
        from utils.permissions import user_can_view_all
        oficina_id = None if user_can_view_all() else session.get('oficina_id')
        
        # Cargar datos del dashboard
        dashboard_data = _load_dashboard_data(oficina_id)
        
        logger.info(
            f"✅ Dashboard cargado: "
            f"{len(dashboard_data['materiales'])} materiales, "
            f"{len(dashboard_data['oficinas'])} oficinas, "
            f"{len(dashboard_data['solicitudes'])} solicitudes, "
            f"{len(dashboard_data['aprobadores'])} aprobadores"
        )
        
        return render_template('dashboard.html', **dashboard_data)
        
    except Exception as e:
        logger.error(f"❌ Error crítico en dashboard: {e}", exc_info=True)
        flash('Error al cargar el dashboard', 'danger')
        
        # Retornar dashboard vacío en caso de error
        empty_data = {
            'materiales': [],
            'oficinas': [],
            'solicitudes': [],
            'aprobadores': []
        }
        return render_template('dashboard.html', **empty_data)

@auth_bp.route('/test-ldap', methods=['GET', 'POST'])
def test_ldap():
    """Endpoint público para probar LDAP (sin login requerido)"""
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        
        from utils.ldap_auth import ad_auth
        from config.config import Config
        
        result = {
            'test_type': 'LDAP Authentication',
            'username': username,
            'ldap_enabled': Config.LDAP_ENABLED,
            'ldap_server': Config.LDAP_SERVER,
            'ldap_domain': Config.LDAP_DOMAIN,
            'success': False
        }
        
        if Config.LDAP_ENABLED and username and password:
            try:
                # Probar autenticación LDAP
                ad_user = ad_auth.authenticate_user(username, password)
                
                if ad_user:
                    result['success'] = True
                    result['message'] = '✅ Autenticación LDAP exitosa'
                    result['user_info'] = {
                        'username': ad_user.get('username'),
                        'full_name': ad_user.get('full_name'),
                        'email': ad_user.get('email'),
                        'department': ad_user.get('department'),
                        'role_from_ad': ad_user.get('role'),
                        'groups_count': len(ad_user.get('groups', []))
                    }
                    
                    # Intentar sincronizar
                    try:
                        from models.usuarios_model import UsuarioModel
                        usuario_sync = UsuarioModel.sync_user_from_ad(ad_user)
                        if usuario_sync:
                            result['sync_success'] = True
                            result['sync_info'] = {
                                'user_id': usuario_sync.get('id'),
                                'system_role': usuario_sync.get('rol'),
                                'office_id': usuario_sync.get('oficina_id')
                            }
                            result['message'] += ' - ✅ Usuario sincronizado'
                        else:
                            result['sync_success'] = False
                            result['message'] += ' - ⚠️ Error en sincronización'
                    except Exception as sync_error:
                        result['sync_success'] = False
                        result['sync_error'] = str(sync_error)
                        result['message'] += f' - ⚠️ Error sincronización: {sync_error}'
                else:
                    result['success'] = False
                    result['message'] = '❌ Autenticación LDAP fallida'
                    
            except Exception as e:
                result['success'] = False
                result['message'] = f'❌ Error: {str(e)}'
                import traceback
                result['traceback'] = traceback.format_exc()
        else:
            result['message'] = '❌ LDAP deshabilitado o credenciales vacías'
        
        return render_template('auth/test_ldap_simple.html', result=result)
    
    return render_template('auth/test_ldap_simple.html', result=None)