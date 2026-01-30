# blueprints/auth.py
import logging
logger = logging.getLogger(__name__)
from flask import Blueprint, render_template, request, redirect, session, flash, current_app
from models.usuarios_model import UsuarioModel
from datetime import datetime, timedelta
from functools import wraps
import os

 
auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

SESSION_TIMEOUT_MINUTES = 10
SESSION_ABSOLUTE_TIMEOUT_HOURS = 2
def init_session_config(app):
    """
    Configura sesiones de forma segura según el entorno
    
    ✅ DÍA 5 - CORRECCIÓN CRÍTICA:
    - Desarrollo (HTTP): SESSION_COOKIE_SECURE = False
    - Producción (HTTPS): SESSION_COOKIE_SECURE = True
    """
    
    is_production = os.getenv('FLASK_ENV') == 'production' or \
                    'sugipq.qualitascolombia.com.co' in os.getenv('SERVER_NAME', '')
    
    
    app.config['SESSION_COOKIE_SECURE'] = is_production
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=SESSION_ABSOLUTE_TIMEOUT_HOURS)
    
    
    if is_production:
        app.config['SESSION_COOKIE_DOMAIN'] = '.qualitascolombia.com.co'
    
    logger.info(f"[SESIÓN] Configuración: SECURE={app.config['SESSION_COOKIE_SECURE']}, HTTPONLY=True, SAMESITE=Lax")
    logger.info(f"[SESIÓN] Entorno: {'PRODUCCIÓN (HTTPS)' if is_production else 'DESARROLLO (HTTP)'}")
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
            logger.info("Error verificando timeout: [error](%s)", type(e).__name__)
    return False

def update_session_activity():
    if 'usuario_id' in session:
        session['last_activity'] = datetime.now().isoformat()
        session.modified = True

def clear_session_safely():
    try:
        session.clear()
    except Exception as e:
        logger.info("Error limpiando sesión: [error](%s)", type(e).__name__)
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
                 
                session.clear()
                session.permanent = True
                session['usuario_id'] = usuario_info['id']
                session['usuario_nombre'] = usuario_info['nombre']
                session['usuario'] = usuario_info['usuario']
                session['rol'] = usuario_info['rol']
                session['oficina_id'] = usuario_info.get('oficina_id', 1)
                session['oficina_nombre'] = usuario_info.get('oficina_nombre', '')
                session['login_time'] = datetime.now().isoformat()
                session['last_activity'] = datetime.now().isoformat()
                session['client_ip'] = client_info['ip']
                session.modified = True
                
                logger.info(f"[SESIÓN] Creada para usuario: {usuario_info['usuario']}")
                logger.info(f"[SESIÓN] Permanent: {session.permanent}")
                flash(f'¡Bienvenido {usuario_info["nombre"]}!', 'success')
                
                 
                return redirect('/dashboard')
            else:
                flash('Usuario o contraseña incorrectos', 'danger')
                return render_template('auth/login.html')
                
        except Exception as e:
            logger.info("[ERROR] Exception en login: [error](%s)", type(e).__name__)
            logger.exception("[ERROR] Exception en login")
            flash('Error inesperado, contacte a soporte', 'danger')
            return render_template('auth/login.html')
    
    return render_template('auth/login.html')

@auth_bp.route('/logout')
def logout():
    usuario = session.get('usuario', 'Desconocido')
    client_info = get_client_info()
    
    logger.info(f"[SESIÓN] Logout de usuario: {usuario}")
    clear_session_safely()
    flash('Sesión cerrada correctamente', 'info')
    return redirect('/auth/login')

@auth_bp.route('/test-ldap', methods=['GET', 'POST'])
def test_ldap():
    """Prueba de autenticación LDAP/AD y verificación de sincronización.

    - Autentica credenciales contra AD.
    - Verifica si el usuario existe en la base de datos local.
    - NO crea/actualiza usuarios aquí (solo reporta estado).
    """
    result = None

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        if not username or not password:
            flash('Debe ingresar usuario y contraseña', 'danger')
            return render_template('auth/test_ldap.html', result=None)

        try:
            from utils.ldap_auth import ADAuth
            from config.config import Config

            ldap_enabled = getattr(Config, 'LDAP_ENABLED', False)
            ldap_server = getattr(Config, 'LDAP_SERVER', '') or ''
            ldap_domain = getattr(Config, 'LDAP_DOMAIN', '') or ''

            ad_auth = ADAuth()

            # test_connection en utils.ldap_auth devuelve dict {"success": bool, "message": ...}
            conn_res = ad_auth.test_connection()
            if isinstance(conn_res, dict):
                connection_ok = bool(conn_res.get('success'))
                connection_message = (conn_res.get('message') or '').strip()
                conn_meta = {
                    'server': conn_res.get('server'),
                    'port': conn_res.get('port'),
                    'use_ssl': conn_res.get('use_ssl'),
                }
            else:
                connection_ok = bool(conn_res)
                connection_message = 'Conexión al servidor LDAP exitosa' if connection_ok else 'Error de conexión'
                conn_meta = {}

            ad_user = ad_auth.authenticate_user(username, password)

            if ad_user:
                # Normalización de llaves (compatibilidad entre implementaciones)
                full_name = ad_user.get('full_name') or ad_user.get('nombre') or ad_user.get('name') or ''
                department = ad_user.get('department') or ad_user.get('departamento') or ''
                role_from_ad = ad_user.get('role') or ad_user.get('rol') or ''

                user_info = {
                    'username': ad_user.get('username') or username,
                    'full_name': full_name,
                    'email': ad_user.get('email') or '',
                    'department': department,
                    'role_from_ad': role_from_ad,
                    'groups_count': ad_user.get('groups_count') or '',
                }

                sync_info = None
                sync_error = None

                try:
                    db_user = UsuarioModel.get_by_username(username)

                    if db_user:
                        sync_info = {
                            'user_id': db_user.get('id'),
                            'system_role': db_user.get('rol'),
                            'office_id': db_user.get('oficina_id'),
                            'sync_status': 'Usuario existe en BD',
                        }
                    else:
                        sync_info = {
                            'user_id': None,
                            'system_role': role_from_ad or 'usuario',
                            'office_id': 1,
                            'sync_status': 'Usuario NO existe en BD (se creará en primer login)',
                        }

                except Exception as sync_err:
                    sync_error = str(sync_err)

                result = {
                    'success': True,
                    'message': 'Autenticación exitosa',

                    # ✅ estructura actual (anidada)
                    'ldap_config': {
                        'enabled': ldap_enabled,
                        'server': ldap_server,
                        'domain': ldap_domain
                    },
                    'connection': {
                        'status': 'OK' if connection_ok else 'Error',
                        'message': connection_message,
                        **{k: v for k, v in conn_meta.items() if v is not None}
                    },
                    'user_data': {
                        'username': user_info['username'],
                        'full_name': user_info['full_name'],
                        'email': user_info['email'],
                        'department': user_info['department'],
                        'role': user_info['role_from_ad']
                    },

                    # ✅ compatibilidad con el template (llaves planas)
                    'ldap_enabled': ldap_enabled,
                    'ldap_server': ldap_server,
                    'ldap_domain': ldap_domain,
                    'username': username,
                    'user_info': user_info,

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
                        'message': connection_message,
                        **{k: v for k, v in conn_meta.items() if v is not None}
                    },

                    # compatibilidad template
                    'ldap_enabled': ldap_enabled,
                    'ldap_server': ldap_server,
                    'ldap_domain': ldap_domain,
                    'username': username,
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
