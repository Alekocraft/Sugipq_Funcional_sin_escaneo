# blueprints/auth.py
from flask import Blueprint, render_template, request, redirect, session, flash, current_app
from models.usuarios_model import UsuarioModel
from datetime import datetime, timedelta
from functools import wraps
import os

 
auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

SESSION_TIMEOUT_MINUTES = 30  # ✅ Cambiado de 5 a 30 minutos
SESSION_ABSOLUTE_TIMEOUT_HOURS = 8  # ✅ Aumentado de 3 a 8 horas

def init_session_config(app):
    """
    Configura sesiones de forma segura según el entorno
    
    ✅ DÍA 5 - CORRECCIÓN CRÍTICA:
    - Desarrollo (HTTP): SESSION_COOKIE_SECURE = False
    - Producción (HTTPS): SESSION_COOKIE_SECURE = True
    """
    # Detectar si estamos en producción basado en el dominio
    is_production = os.getenv('FLASK_ENV') == 'production' or \
                    'sugipq.qualitascolombia.com.co' in os.getenv('SERVER_NAME', '')
    
    # ✅ CORRECCIÓN CRÍTICA: False en desarrollo, True solo en producción con HTTPS
    app.config['SESSION_COOKIE_SECURE'] = is_production
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=SESSION_ABSOLUTE_TIMEOUT_HOURS)
    
    # Configurar dominio de cookies para producción
    if is_production:
        app.config['SESSION_COOKIE_DOMAIN'] = '.qualitascolombia.com.co'
    
    print(f"[SESIÓN] Configuración: SECURE={app.config['SESSION_COOKIE_SECURE']}, HTTPONLY=True, SAMESITE=Lax")
    print(f"[SESIÓN] Entorno: {'PRODUCCIÓN (HTTPS)' if is_production else 'DESARROLLO (HTTP)'}")

def check_session_timeout():
    if 'usuario_id' not in session:
        return False
    
    last_activity = session.get('last_activity')
    if last_activity:
        try:
            if isinstance(last_activity, str):
                last_activity = datetime.fromisoformat(last_activity)
            
            inactive_time = datetime.now() - last_activity
            if inactive_time > timedelta(minutes=SESSION_TIMEOUT_MINUTES):
                return True
        except Exception as e:
            print(f"Error verificando timeout: {e}")
    
    return False

def update_session_activity():
    if 'usuario_id' in session:
        session['last_activity'] = datetime.now().isoformat()
        session.modified = True

def clear_session_safely():
    try:
        session.clear()
    except Exception as e:
        print(f"Error limpiando sesión: {e}")

def require_login(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'usuario_id' not in session:
            flash('Por favor, inicie sesión para continuar', 'warning')
            return redirect('/auth/login')
        
        if check_session_timeout():
            clear_session_safely()
            flash(f'Su sesión ha expirado por inactividad ({SESSION_TIMEOUT_MINUTES} minutos). Por favor, inicie sesión nuevamente.', 'warning')
            return redirect('/auth/login')
        
        update_session_activity()
        return f(*args, **kwargs)
    return decorated_function

def assign_role_by_office(office_name):
    office_name = office_name.lower().strip() if office_name else ''
    
    if 'gerencia' in office_name:
        return 'admin'
    elif 'almacén' in office_name or 'logística' in office_name:
        return 'almacen'
    elif 'finanzas' in office_name or 'contabilidad' in office_name:
        return 'finanzas'
    elif 'rrhh' in office_name or 'recursos humanos' in office_name:
        return 'rrhh'
    else:
        return 'usuario'

def get_client_info():
    return {
        'ip': request.remote_addr,
        'user_agent': request.headers.get('User-Agent', 'Unknown'),
        'timestamp': datetime.now().isoformat()
    }

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if 'usuario_id' in session:
        if check_session_timeout():
            clear_session_safely()
            return redirect('/auth/login')
        return redirect('/dashboard')
    
    if request.method == 'POST':
        usuario = request.form.get('usuario', '').strip()
        contraseña = request.form.get('contraseña', '')
        
        if not usuario or not contraseña:
            flash('Por favor, ingrese usuario y contraseña', 'warning')
            return render_template('auth/login.html')
        
        client_info = get_client_info()
        
        try:
            usuario_info = UsuarioModel.verificar_credenciales(usuario, contraseña)
            
            if usuario_info:
                # ✅ CORRECCIÓN CRÍTICA: Limpiar sesión ANTES de crear nueva
                session.clear()
                
                # ✅ CORRECCIÓN CRÍTICA: Marcar sesión como permanente PRIMERO
                session.permanent = True
                
                # ✅ Asignar datos de sesión
                session['usuario_id'] = usuario_info['id']
                session['usuario_nombre'] = usuario_info['nombre']
                session['usuario'] = usuario_info['usuario']
                session['rol'] = usuario_info['rol']
                session['oficina_id'] = usuario_info.get('oficina_id', 1)
                session['oficina_nombre'] = usuario_info.get('oficina_nombre', '')
                
                session['login_time'] = datetime.now().isoformat()
                session['last_activity'] = datetime.now().isoformat()
                session['client_ip'] = client_info['ip']
                
                # ✅ CORRECCIÓN CRÍTICA: Forzar que Flask guarde la sesión
                session.modified = True
                
                print(f"[SESIÓN] Creada para usuario: {usuario_info['usuario']}")
                print(f"[SESIÓN] Permanent: {session.permanent}")
                
                flash(f'¡Bienvenido {usuario_info["nombre"]}!', 'success')
                
                # ✅ IMPORTANTE: return redirect
                return redirect('/dashboard')
            else:
                flash('Usuario o contraseña incorrectos', 'danger')
                return render_template('auth/login.html')
                
        except Exception as e:
            print(f"[ERROR] Exception en login: {e}")
            import traceback
            traceback.print_exc()
            flash('Error del sistema durante el login', 'danger')
            return render_template('auth/login.html')
    
    return render_template('auth/login.html')

@auth_bp.route('/logout')
def logout():
    usuario = session.get('usuario', 'Desconocido')
    client_info = get_client_info()
    
    print(f"[SESIÓN] Logout de usuario: {usuario}")
    
    clear_session_safely()
    flash('Sesión cerrada correctamente', 'info')
    return redirect('/auth/login')

@auth_bp.route('/test-ldap', methods=['GET', 'POST'])
def test_ldap():
    try:
        result = None
        
        if request.method == 'POST':
            username = request.form.get('username', '').strip()
            password = request.form.get('password', '')
            
            if not username or not password:
                flash('Debe ingresar usuario y contraseña', 'danger')
                return render_template('auth/test_ldap.html')
            
            try:
                from utils.ldap_auth import ADAuth
                from config.config import Config
                
                ldap_enabled = Config.LDAP_ENABLED
                ldap_server = Config.LDAP_SERVER
                ldap_domain = Config.LDAP_DOMAIN
                
                ad_auth = ADAuth()
                
                connection_ok = ad_auth.test_connection()
                
                user_data = ad_auth.authenticate_user(username, password)
                
                if user_data:
                    sync_info = None
                    sync_error = None
                    
                    try:
                        from models.usuarios_model import UsuarioModel
                        
                        db_user = UsuarioModel.get_by_username(username)
                        
                        if db_user:
                            sync_info = {
                                'user_id': db_user.get('id'),
                                'system_role': db_user.get('rol'),
                                'office_id': db_user.get('oficina_id'),
                                'sync_status': 'Usuario existente actualizado'
                            }
                        else:
                            sync_info = {
                                'user_id': None,
                                'system_role': user_data.get('role', 'usuario'),
                                'office_id': 1,
                                'sync_status': 'Usuario nuevo - se creará en el primer login'
                            }
                    
                    except Exception as sync_err:
                        sync_error = str(sync_err)
                    
                    result = {
                        'success': True,
                        'message': 'Autenticación exitosa',
                        'ldap_config': {
                            'enabled': ldap_enabled,
                            'server': ldap_server,
                            'domain': ldap_domain
                        },
                        'connection': {
                            'status': 'OK' if connection_ok else 'Error',
                            'message': 'Conexión al servidor LDAP exitosa' if connection_ok else 'Error de conexión'
                        },
                        'user_data': {
                            'username': user_data.get('username'),
                            'full_name': user_data.get('full_name'),
                            'email': user_data.get('email'),
                            'department': user_data.get('department'),
                            'role': user_data.get('role')
                        },
                        'sync_info': sync_info,
                        'sync_error': sync_error
                    }
                    flash('Autenticación LDAP exitosa', 'success')
                else:
                    result = {
                        'success': False,
                        'message': 'Autenticación fallida',
                        'ldap_config': {
                            'enabled': ldap_enabled,
                            'server': ldap_server,
                            'domain': ldap_domain
                        },
                        'connection': {
                            'status': 'OK' if connection_ok else 'Error',
                            'message': 'Conexión al servidor LDAP exitosa' if connection_ok else 'Error de conexión'
                        }
                    }
                    flash('Usuario o contraseña incorrectos', 'danger')
            
            except Exception as e:
                result = {
                    'success': False,
                    'message': f'Error: {str(e)}',
                    'error_details': str(e)
                }
                flash(f'Error en prueba LDAP: {str(e)}', 'danger')
        
        return render_template('auth/test_ldap.html', result=result)
    
    except Exception as e:
        flash(f'Error: {str(e)}', 'danger')
        return render_template('auth/test_ldap.html', result=None)