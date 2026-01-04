# blueprints/auth.py
from flask import Blueprint, render_template, request, redirect, session, flash, current_app
from models.usuarios_model import UsuarioModel
from datetime import datetime, timedelta
from functools import wraps

# =====================================================
# CONFIGURACIÓN DEL BLUEPRINT
# =====================================================
auth_bp = Blueprint('auth', __name__, url_prefix='')

# =====================================================
# CONFIGURACIÓN DE SESIÓN MODIFICADA
# =====================================================
SESSION_TIMEOUT_MINUTES = 5  # REDUCIDO: 30 → 5 minutos de inactividad
SESSION_ABSOLUTE_TIMEOUT_HOURS = 3  # REDUCIDO: 8 → 3 horas máximo

# =====================================================
# FUNCIONES DE MANEJO DE SESIÓN
# =====================================================
def init_session_config(app):
    """Inicializa la configuración de sesión en la aplicación"""
    app.config['SESSION_COOKIE_SECURE'] = True  # Solo HTTPS en producción
    app.config['SESSION_COOKIE_HTTPONLY'] = True  # No accesible por JavaScript
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'  # Protección CSRF
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=SESSION_ABSOLUTE_TIMEOUT_HOURS)
    
    print(f"⚠️ Configuración de sesión: {SESSION_TIMEOUT_MINUTES} min inactividad, {SESSION_ABSOLUTE_TIMEOUT_HOURS}h máximo")

def check_session_timeout():
    """Verifica si la sesión ha expirado por inactividad"""
    if 'usuario_id' not in session:
        return False
    
    last_activity = session.get('last_activity')
    if last_activity:
        try:
            if isinstance(last_activity, str):
                last_activity = datetime.fromisoformat(last_activity)
            
            inactive_time = datetime.now() - last_activity
            if inactive_time > timedelta(minutes=SESSION_TIMEOUT_MINUTES):
                print(f"⏰ Sesión expirada por inactividad (5 min): {inactive_time}")
                return True
        except Exception as e:
            print(f"⚠️ Error verificando timeout: {e}")
    
    return False

def update_session_activity():
    """Actualiza el timestamp de última actividad"""
    if 'usuario_id' in session:
        session['last_activity'] = datetime.now().isoformat()
        session.modified = True

def clear_session_safely():
    """Limpia la sesión de forma segura"""
    try:
        session.clear()
    except Exception as e:
        print(f"⚠️ Error limpiando sesión: {e}")

def require_login(f):
    """Decorador para requerir login con verificación de timeout"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'usuario_id' not in session:
            flash('Por favor, inicie sesión para continuar', 'warning')
            return redirect('/login')
        
        if check_session_timeout():
            clear_session_safely()
            flash('Su sesión ha expirado por inactividad (5 minutos). Por favor, inicie sesión nuevamente.', 'warning')
            return redirect('/login')
        
        update_session_activity()
        return f(*args, **kwargs)
    return decorated_function

# =====================================================
# FUNCIONES AUXILIARES
# =====================================================
def assign_role_by_office(office_name):
    """Devuelve el rol asignado según el nombre de la oficina."""
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
    """Obtiene información del cliente para logs de seguridad"""
    return {
        'ip': request.remote_addr,
        'user_agent': request.headers.get('User-Agent', 'Unknown'),
        'timestamp': datetime.now().isoformat()
    }

# =====================================================
# RUTAS DE AUTENTICACIÓN
# =====================================================
@auth_bp.route('/')
def index():
    if 'usuario_id' in session:
        if check_session_timeout():
            clear_session_safely()
            return redirect('/login')
        return redirect('/dashboard')
    return redirect('/login')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    # Si ya está logueado, redirigir al dashboard
    if 'usuario_id' in session:
        if not check_session_timeout():
            return redirect('/dashboard')
        clear_session_safely()
    
    if request.method == 'POST':
        usuario = request.form.get('usuario', '').strip()
        contraseña = request.form.get('contraseña', '')
        
        # Validación básica
        if not usuario or not contraseña:
            flash('Por favor, ingrese usuario y contraseña', 'warning')
            return render_template('auth/login.html')
        
        client_info = get_client_info()
        print(f"🔐 Intento de login: {usuario} desde {client_info['ip']}")
        
        try:
            usuario_info = UsuarioModel.verificar_credenciales(usuario, contraseña)
            
            if usuario_info:
                # Regenerar ID de sesión para prevenir session fixation
                session.clear()
                
                # Establecer datos de sesión
                session['usuario_id'] = usuario_info['id']
                session['usuario_nombre'] = usuario_info['nombre']
                session['usuario'] = usuario_info['usuario']
                session['rol'] = usuario_info['rol']
                session['oficina_id'] = usuario_info.get('oficina_id', 1)
                session['oficina_nombre'] = usuario_info.get('oficina_nombre', '')
                
                # Timestamps de sesión
                session['login_time'] = datetime.now().isoformat()
                session['last_activity'] = datetime.now().isoformat()
                session['client_ip'] = client_info['ip']
                
                # Hacer la sesión permanente
                session.permanent = True
                
                print(f"✅ Login exitoso: {usuario} - Rol: {usuario_info['rol']} - IP: {client_info['ip']}")
                flash(f'¡Bienvenido {usuario_info["nombre"]}!', 'success')
                return redirect('/dashboard')
            else:
                print(f"❌ Login fallido: {usuario} desde {client_info['ip']}")
                flash('Usuario o contraseña incorrectos', 'danger')
                return render_template('auth/login.html')
                
        except Exception as e:
            print(f"❌ Error durante login: {e}")
            import traceback
            print(f"❌ Traceback: {traceback.format_exc()}")
            flash('Error del sistema durante el login', 'danger')
            return render_template('auth/login.html')
    
    return render_template('auth/login.html')

@auth_bp.route('/logout')
def logout():
    usuario = session.get('usuario', 'Desconocido')
    client_info = get_client_info()
    print(f"🚪 Logout: {usuario} desde {client_info['ip']}")
    
    clear_session_safely()
    flash('Sesión cerrada correctamente', 'info')
    return redirect('/login')

 
@auth_bp.route('/test-ldap', methods=['GET', 'POST'])
def test_ldap():
    """
    Ruta para probar conexión LDAP REAL.
    Accesible desde: /test-ldap
    
    ✅ CORREGIDO: Ahora usa ADAuth real en lugar de datos simulados
    """
    try:
        result = None
        
        if request.method == 'POST':
            username = request.form.get('username', '').strip()
            password = request.form.get('password', '')
            
            if not username or not password:
                flash('Debe ingresar usuario y contraseña', 'danger')
                return render_template('auth/test_ldap.html')
            
            try:
                # Importar la clase REAL de autenticación LDAP
                from utils.ldap_auth import ADAuth
                from config.config import Config
                
                # Obtener configuración
                ldap_enabled = Config.LDAP_ENABLED
                ldap_server = Config.LDAP_SERVER
                ldap_domain = Config.LDAP_DOMAIN
                
                print(f"🔍 TEST LDAP: Probando autenticación para '{username}'")
                print(f"📡 Servidor: {ldap_server}")
                print(f"🌐 Dominio: {ldap_domain}")
                
                # Crear instancia de ADAuth y autenticar
                ad_auth = ADAuth()
                
                # 1. Probar conexión al servidor
                connection_ok = ad_auth.test_connection()
                print(f"🔌 Conexión al servidor: {'✅ OK' if connection_ok else '❌ FALLO'}")
                
                # 2. Autenticar usuario
                user_data = ad_auth.authenticate_user(username, password)
                
                if user_data:
                    # ✅ AUTENTICACIÓN EXITOSA - Datos REALES del LDAP
                    print(f"✅ TEST LDAP: Autenticación exitosa para '{username}'")
                    print(f"📋 Datos del usuario: {user_data}")
                    
                    # Intentar sincronizar con la base de datos
                    sync_info = None
                    sync_error = None
                    
                    try:
                        # Buscar o crear usuario en la base de datos
                        from models.usuarios_model import UsuarioModel
                        
                        db_user = UsuarioModel.get_by_username(username)
                        
                        if db_user:
                            print(f"👤 Usuario encontrado en BD: ID {db_user.get('id')}")
                            sync_info = {
                                'user_id': db_user.get('id'),
                                'system_role': db_user.get('rol'),
                                'office_id': db_user.get('oficina_id'),
                                'sync_status': 'Usuario existente actualizado'
                            }
                        else:
                            print(f"⚠️ Usuario NO encontrado en BD, debería crearse automáticamente en login")
                            sync_info = {
                                'user_id': None,
                                'system_role': user_data.get('role', 'usuario'),
                                'office_id': 1,
                                'sync_status': 'Usuario nuevo - se creará en el primer login'
                            }
                    
                    except Exception as sync_ex:
                        print(f"⚠️ Error en sincronización BD: {sync_ex}")
                        sync_error = f"Error sincronizando con BD: {str(sync_ex)}"
                    
                    result = {
                        'success': True,
                        'message': '✅ Autenticación LDAP exitosa con datos REALES',
                        'ldap_enabled': ldap_enabled,
                        'ldap_server': ldap_server,
                        'ldap_domain': ldap_domain,
                        'username': username,
                        'user_info': {
                            'username': user_data.get('username'),
                            'full_name': user_data.get('full_name'),
                            'email': user_data.get('email'),
                            'department': user_data.get('department'),
                            'role_from_ad': user_data.get('role'),
                            'groups_count': len(user_data.get('groups', []))
                        },
                        'sync_info': sync_info,
                        'sync_error': sync_error,
                        'traceback': None
                    }
                    
                else:
                    # ❌ AUTENTICACIÓN FALLIDA
                    print(f"❌ TEST LDAP: Autenticación fallida para '{username}'")
                    result = {
                        'success': False,
                        'message': '❌ Autenticación LDAP fallida - Credenciales inválidas o usuario no encontrado',
                        'ldap_enabled': ldap_enabled,
                        'ldap_server': ldap_server,
                        'ldap_domain': ldap_domain,
                        'username': username,
                        'user_info': None,
                        'sync_info': None,
                        'sync_error': 'Credenciales inválidas o servidor LDAP no disponible',
                        'traceback': None
                    }
                        
            except ImportError as ie:
                # Módulo LDAP no disponible
                import traceback
                print(f"⚠️ TEST LDAP: Módulo ldap3 no disponible: {ie}")
                result = {
                    'success': False,
                    'message': '⚠️ Módulo LDAP no instalado - Instale python-ldap3',
                    'ldap_enabled': False,
                    'ldap_server': 'No disponible',
                    'ldap_domain': 'No disponible',
                    'username': username,
                    'user_info': None,
                    'sync_info': None,
                    'sync_error': f'ImportError: {str(ie)}',
                    'traceback': traceback.format_exc()
                }
                
            except Exception as e:
                # Error general
                import traceback
                print(f"❌ TEST LDAP: Error general: {e}")
                print(traceback.format_exc())
                result = {
                    'success': False,
                    'message': f'❌ Error en autenticación LDAP: {str(e)}',
                    'ldap_enabled': False,
                    'ldap_server': 'Error',
                    'ldap_domain': 'Error',
                    'username': username,
                    'user_info': None,
                    'sync_info': None,
                    'sync_error': str(e),
                    'traceback': traceback.format_exc()
                }
        
        else:  # GET request
            # Mostrar configuración actual
            try:
                from config.config import Config
                result = {
                    'success': None,
                    'message': 'Ingrese sus credenciales de dominio para probar la conexión LDAP',
                    'ldap_enabled': Config.LDAP_ENABLED,
                    'ldap_server': Config.LDAP_SERVER,
                    'ldap_domain': Config.LDAP_DOMAIN,
                    'username': None,
                    'user_info': None,
                    'sync_info': None,
                    'sync_error': None
                }
            except Exception as e:
                result = {
                    'success': None,
                    'message': f'Error cargando configuración LDAP: {str(e)}',
                    'ldap_enabled': False,
                    'ldap_server': 'No configurado',
                    'ldap_domain': 'No configurado',
                    'username': None,
                    'user_info': None,
                    'sync_info': None,
                    'sync_error': None
                }
        
        return render_template('auth/test_ldap.html', result=result)
        
    except Exception as e:
        import traceback
        print(f"❌ Error crítico en test_ldap: {e}")
        print(traceback.format_exc())
        result = {
            'success': False,
            'message': f'❌ Error crítico en la página: {str(e)}',
            'ldap_enabled': False,
            'ldap_server': 'Error',
            'ldap_domain': 'Error',
            'username': None,
            'user_info': None,
            'sync_info': None,
            'sync_error': str(e),
            'traceback': traceback.format_exc()
        }
        return render_template('auth/test_ldap.html', result=result)

@auth_bp.route('/dashboard')
@require_login
def dashboard():
    try:
        print("📊 Cargando dashboard...")
        
        # ✅ NUEVO: Obtener filtro de oficina según permisos
        from utils.permissions import user_can_view_all
        oficina_id = None if user_can_view_all() else session.get('oficina_id')
        
        materiales = []
        oficinas = []
        solicitudes = []
        aprobadores = []
        
        try:
            from models.materiales_model import MaterialModel
            materiales = MaterialModel.obtener_todos(oficina_id) or []
            print(f"✅ Materiales cargados: {len(materiales)}")
        except Exception as e:
            print(f"⚠️ Error cargando materiales: {e}")
            materiales = []
        
        try:
            from models.oficinas_model import OficinaModel
            oficinas = OficinaModel.obtener_todas() or []
            print(f"✅ Oficinas cargadas: {len(oficinas)}")
        except Exception as e:
            print(f"⚠️ Error cargando oficinas: {e}")
            oficinas = []
        
        try:
            from models.solicitudes_model import SolicitudModel
            solicitudes = SolicitudModel.obtener_todas(oficina_id) or []
            print(f"✅ Solicitudes cargadas: {len(solicitudes)}")
        except Exception as e:
            print(f"⚠️ Error cargando solicitudes: {e}")
            solicitudes = []
        
        try:
            from models.usuarios_model import UsuarioModel
            aprobadores = UsuarioModel.obtener_aprobadores() or []
            print(f"✅ Aprobadores cargados: {len(aprobadores)}")
        except Exception as e:
            print(f"⚠️ Error cargando aprobadores: {e}")
            aprobadores = []

        return render_template('dashboard.html',
                            materiales=materiales,
                            oficinas=oficinas,
                            solicitudes=solicitudes,
                            aprobadores=aprobadores)
    except Exception as e:
        print(f"❌ Error crítico en dashboard: {e}")
        flash('Error al cargar el dashboard', 'danger')
        return render_template('dashboard.html', 
                            materiales=[], 
                            oficinas=[], 
                            solicitudes=[],
                            aprobadores=[])

# =====================================================
# API DE ESTADO DE SESIÓN
# =====================================================
@auth_bp.route('/api/session-status')
def session_status():
    """API para verificar estado de sesión (útil para JavaScript)"""
    from flask import jsonify
    
    if 'usuario_id' not in session:
        return jsonify({'authenticated': False, 'reason': 'no_session'})
    
    if check_session_timeout():
        return jsonify({'authenticated': False, 'reason': 'timeout'})
    
    # Calcular tiempo restante
    last_activity = session.get('last_activity')
    if last_activity:
        try:
            if isinstance(last_activity, str):
                last_activity = datetime.fromisoformat(last_activity)
            
            inactive_time = datetime.now() - last_activity
            remaining_seconds = (timedelta(minutes=SESSION_TIMEOUT_MINUTES) - inactive_time).total_seconds()
            
            return jsonify({
                'authenticated': True,
                'user': session.get('usuario_nombre'),
                'remaining_seconds': max(0, int(remaining_seconds)),
                'timeout_minutes': SESSION_TIMEOUT_MINUTES
            })
        except Exception:
            pass
    
    return jsonify({'authenticated': True, 'user': session.get('usuario_nombre')})

@auth_bp.route('/api/extend-session', methods=['POST'])
def extend_session():
    """API para extender la sesión activa"""
    from flask import jsonify
    
    if 'usuario_id' not in session:
        return jsonify({'success': False, 'message': 'No hay sesión activa'}), 401
    
    if check_session_timeout():
        clear_session_safely()
        return jsonify({'success': False, 'message': 'Sesión expirada'}), 401
    
    update_session_activity()
    return jsonify({
        'success': True, 
        'message': 'Sesión extendida',
        'new_timeout_seconds': SESSION_TIMEOUT_MINUTES * 60
    })
