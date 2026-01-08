# blueprints/confirmacion_asignaciones.py
 
"""
Blueprint para gestionar confirmaciones de asignaciones mediante tokens temporales.
VERSION CORREGIDA: Usa helpers desde utils.helpers
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from models.confirmacion_asignaciones_model import ConfirmacionAsignacionesModel
from utils.helpers import sanitizar_email, sanitizar_username, sanitizar_ip  # CORRECCIÓN: usa utils.helpers
from utils.auth import login_required
from datetime import datetime
import logging
import re

logger = logging.getLogger(__name__)

# Crear blueprint
confirmacion_bp = Blueprint(
    'confirmacion',
    __name__,
    url_prefix='/confirmacion'
)


def validar_ldap(username, password):
    """
    Valida credenciales contra Active Directory usando ADAuth.
    Retorna: (exito: bool, email: str, nombre: str, mensaje_error: str)
    """
    try:
        # Importar la instancia global de ADAuth
        from utils.ldap_auth import ad_auth
        
        # Autenticar usuario
        resultado = ad_auth.authenticate_user(username, password)
        
        if resultado:
            # Exito - extraer datos del resultado
            email = resultado.get('email', f"{username}@qualitascolombia.com.co")
            nombre = resultado.get('full_name', username)
            
            logger.info(f"✅ LDAP: Autenticacion exitosa para {username} ({email})")
            return (True, email, nombre, None)
        else:
            # Fallo de autenticacion
            logger.warning(f"❌ LDAP: Credenciales invalidas para {username}")
            return (False, None, None, "Usuario o contrasena incorrectos")
            
    except ImportError as e:
        logger.error(f"❌ Modulo LDAP no disponible: {e}")
        return (False, None, None, "Sistema de autenticacion no disponible")
    except Exception as e:
        logger.error(f"❌ Error en validacion LDAP: {e}", exc_info=True)
        return (False, None, None, f"Error de autenticacion: {str(e)}")


def validar_numero_identificacion(numero_identificacion):
    """
    Valida el formato del número de identificación (cédula).
    
    Args:
        numero_identificacion: Número de identificación a validar
        
    Returns:
        tuple: (es_valido: bool, numero_limpio: str, mensaje_error: str)
    """
    # Verificar que no esté vacío
    if not numero_identificacion or not numero_identificacion.strip():
        return (False, None, "El número de identificación es obligatorio")
    
    # Limpiar el número (eliminar espacios)
    numero_limpio = numero_identificacion.strip()
    
    # Validar que solo contenga dígitos
    if not numero_limpio.isdigit():
        return (False, None, "El número de identificación debe contener solo números")
    
    # Validar longitud (entre 6 y 20 dígitos)
    if len(numero_limpio) < 6:
        return (False, None, "El número de identificación debe tener al menos 6 dígitos")
    
    if len(numero_limpio) > 20:
        return (False, None, "El número de identificación no puede tener más de 20 dígitos")
    
    return (True, numero_limpio, None)


@confirmacion_bp.route('/confirmar-asignacion/<token>', methods=['GET', 'POST'])
def confirmar_asignacion(token):
    """
    Procesa la confirmacion de una asignacion mediante token.
    GET: Muestra el formulario de confirmacion con login LDAP
    POST: Valida LDAP, número de identificación y procesa la confirmacion
    """
    try:
        # Validar el token
        validacion = ConfirmacionAsignacionesModel.validar_token(token)
        
        if not validacion:
            logger.warning(f"Token invalido o no encontrado: {token[:20]}...")
            return render_template(
                'confirmacion/error.html',
                mensaje='Token invalido o no encontrado',
                titulo='Error de Validacion'
            ), 404
        
        if not validacion.get('es_valido'):
            # Token no valido (expirado o ya usado)
            if validacion.get('ya_confirmado'):
                return render_template(
                    'confirmacion/ya_confirmado.html',
                    mensaje=validacion.get('mensaje_error'),
                    titulo='Asignacion Ya Confirmada',
                    asignacion=validacion
                )
            elif validacion.get('expirado'):
                return render_template(
                    'confirmacion/token_expirado.html',
                    mensaje=validacion.get('mensaje_error'),
                    titulo='Token Expirado'
                )
            else:
                return render_template(
                    'confirmacion/error.html',
                    mensaje=validacion.get('mensaje_error', 'Error desconocido'),
                    titulo='Error de Validacion'
                )
        
        # Si es GET, mostrar formulario de confirmacion
        if request.method == 'GET':
            # Verificar si LDAP esta disponible
            ldap_disponible = True
            try:
                from utils.ldap_auth import ad_auth
                # Probar que ADAuth este instanciado correctamente
                if ad_auth is None or not hasattr(ad_auth, 'authenticate_user'):
                    ldap_disponible = False
                    logger.warning("ADAuth no esta disponible o mal configurado")
            except ImportError:
                ldap_disponible = False
                logger.warning("Modulo ldap_auth no disponible")
            
            return render_template(
                'confirmacion/confirmar.html',
                token=token,
                asignacion=validacion,
                ldap_disponible=ldap_disponible
            )
        
        # Si es POST, procesar la confirmacion
        if request.method == 'POST':
            # ============================================================
            # NUEVA VALIDACIÓN: Número de Identificación (obligatorio)
            # ============================================================
            numero_identificacion = request.form.get('numero_identificacion', '').strip()
            es_valido, numero_limpio, error_cedula = validar_numero_identificacion(numero_identificacion)
            
            if not es_valido:
                logger.warning(f"❌ Número de identificación inválido: {error_cedula}")
                flash(error_cedula, 'error')
                return render_template(
                    'confirmacion/confirmar.html',
                    token=token,
                    asignacion=validacion,
                    ldap_disponible=True,
                    error=error_cedula
                )
            
            logger.info(f"✅ Número de identificación validado: {numero_limpio}")
            
            # Verificar si se usa autenticacion LDAP
            sin_autenticar = request.form.get('sin_autenticar') == 'true'
            
            if not sin_autenticar:
                # VALIDAR CREDENCIALES LDAP
                username = request.form.get('username', '').strip()
                password = request.form.get('password', '')
                
                if not username or not password:
                    flash('Debe ingresar usuario y contrasena', 'error')
                    return render_template(
                        'confirmacion/confirmar.html',
                        token=token,
                        asignacion=validacion,
                        ldap_disponible=True,
                        error='Debe ingresar usuario y contrasena'
                    )
                
                logger.info(f"🔐 Intentando validar LDAP para usuario: {sanitizar_username(username)}")
                
                # Validar contra LDAP
                exito, email_ldap, nombre_ldap, mensaje_error = validar_ldap(username, password)
                
                if not exito:
                    logger.warning(f"❌ Fallo autenticacion LDAP para usuario: {sanitizar_username(username)}")
                    flash(f'Error de autenticacion: {mensaje_error}', 'error')
                    return render_template(
                        'confirmacion/confirmar.html',
                        token=token,
                        asignacion=validacion,
                        ldap_disponible=True,
                        error=mensaje_error,
                        username_anterior=username  # Mantener el usuario ingresado
                    )
                
                logger.info(f"✅ LDAP validado: {sanitizar_username(username)} -> {sanitizar_email(email_ldap)}")
                
                # Verificar que el usuario LDAP coincida con el asignado
                email_asignado = validacion.get('usuario_email', '').lower()
                email_ldap_lower = (email_ldap or '').lower()
                
                logger.info(f"📧 Comparando emails: LDAP={email_ldap_lower} vs Asignado={email_asignado}")
                
                if email_ldap_lower != email_asignado:
                    logger.warning(f"❌ Usuario LDAP ({email_ldap}) no coincide con asignado ({email_asignado})")
                    flash('El usuario autenticado no coincide con el destinatario de la asignacion', 'error')
                    return render_template(
                        'confirmacion/confirmar.html',
                        token=token,
                        asignacion=validacion,
                        ldap_disponible=True,
                        error=f'El usuario autenticado ({email_ldap}) no coincide con el destinatario ({email_asignado})',
                        username_anterior=username
                    )
                
                usuario_confirmacion = email_ldap
                nombre_confirmacion = nombre_ldap
                logger.info(f"✅ Usuario validado y coincidente: {sanitizar_username(username)} ({sanitizar_email(email_ldap)})")
            else:
                # Sin autenticacion LDAP (fallback)
                usuario_confirmacion = validacion.get('usuario_email', 'Usuario')
                nombre_confirmacion = validacion.get('usuario_nombre', 'Usuario')
                logger.warning(f"⚠️ Confirmacion sin autenticacion LDAP para: {usuario_confirmacion}")
            
            # Obtener datos adicionales
            direccion_ip = request.remote_addr
            user_agent = request.headers.get('User-Agent', '')
            
            logger.info(f"📝 Confirmando asignacion - Usuario: {sanitizar_email(usuario_confirmacion)}, CC: [PROTEGIDO], IP: {sanitizar_ip(direccion_ip)}")
            
            # Confirmar la asignacion (INCLUYENDO NÚMERO DE IDENTIFICACIÓN)
            resultado = ConfirmacionAsignacionesModel.confirmar_asignacion(
                token=token,
                usuario_ad_username=usuario_confirmacion,
                numero_identificacion=numero_limpio,  # NUEVO PARÁMETRO
                direccion_ip=direccion_ip,
                user_agent=user_agent
            )
            
            if resultado.get('success'):
                logger.info(f"✅ Asignacion confirmada exitosamente: {resultado.get('asignacion_id')} - CC: {numero_limpio}")
                return render_template(
                    'confirmacion/confirmado_exitoso.html',
                    resultado=resultado,
                    titulo='Confirmacion Exitosa',
                    mensaje='Su asignacion ha sido confirmada correctamente.',
                    producto=resultado.get('producto_nombre'),
                    oficina=resultado.get('oficina_nombre'),
                    usuario=nombre_confirmacion,
                    fecha_confirmacion=datetime.now()
                )
            else:
                logger.error(f"❌ Error al confirmar asignacion: {resultado.get('message')}")
                return render_template(
                    'confirmacion/error.html',
                    mensaje=resultado.get('message', 'Error al confirmar la asignacion'),
                    titulo='Error al Confirmar'
                )
    
    except Exception as e:
        logger.error(f"❌ Error procesando confirmacion: {e}", exc_info=True)
        return render_template(
            'confirmacion/error.html',
            mensaje=f'Error inesperado al procesar la confirmacion: {str(e)}',
            titulo='Error del Sistema'
        ), 500


@confirmacion_bp.route('/mis-pendientes')
@login_required
def mis_pendientes():
    """
    Muestra las confirmaciones pendientes del usuario autenticado.
    Requiere login.
    """
    try:
        # Obtener email del usuario de la sesion
        usuario_email = session.get('email')
        if not usuario_email:
            flash('No se pudo obtener tu informacion de usuario', 'error')
            return redirect(url_for('auth.login'))
        
        # Obtener confirmaciones pendientes
        pendientes = ConfirmacionAsignacionesModel.obtener_confirmaciones_pendientes(
            usuario_email=usuario_email
        )
        
        return render_template(
            'confirmacion/mis_pendientes.html',
            confirmaciones=pendientes,
            pendientes=pendientes,
            total_pendientes=len(pendientes),
            titulo='Mis Confirmaciones Pendientes'
        )
    
    except Exception as e:
        logger.error(f"Error obteniendo confirmaciones pendientes: {e}", exc_info=True)
        flash('Error al cargar las confirmaciones pendientes', 'error')
        return redirect(url_for('dashboard'))


@confirmacion_bp.route('/estadisticas')
@login_required
def estadisticas():
    """
    Muestra estadisticas generales de confirmaciones.
    Solo para administradores.
    """
    try:
        # Verificar si el usuario es administrador
        if not session.get('is_admin', False):
            flash('No tienes permisos para ver esta pagina', 'error')
            return redirect(url_for('dashboard'))
        
        # Obtener estadisticas
        stats = ConfirmacionAsignacionesModel.obtener_estadisticas_confirmaciones()
        
        return render_template(
            'confirmacion/estadisticas.html',
            estadisticas=stats,
            titulo='Estadisticas de Confirmaciones'
        )
    
    except Exception as e:
        logger.error(f"Error obteniendo estadisticas: {e}", exc_info=True)
        flash('Error al cargar las estadisticas', 'error')
        return redirect(url_for('dashboard'))


@confirmacion_bp.route('/limpiar-tokens', methods=['POST'])
@login_required
def limpiar_tokens():
    """
    Limpia tokens expirados de la base de datos.
    Solo para administradores.
    """
    try:
        # Verificar si el usuario es administrador
        if not session.get('is_admin', False):
            flash('No tienes permisos para realizar esta accion', 'error')
            return redirect(url_for('dashboard'))
        
        # Limpiar tokens
        eliminados = ConfirmacionAsignacionesModel.limpiar_tokens_expirados()
        
        flash(f'Se eliminaron {eliminados} tokens expirados', 'success')
        logger.info(f"Tokens expirados limpiados: {eliminados}")
        
        return redirect(url_for('confirmacion.estadisticas'))
    
    except Exception as e:
        logger.error(f"Error limpiando tokens: {e}", exc_info=True)
        flash('Error al limpiar tokens expirados', 'error')
        return redirect(url_for('confirmacion.estadisticas'))


# Manejador de errores especifico para este blueprint
@confirmacion_bp.errorhandler(404)
def not_found_error(error):
    """Maneja errores 404 especificos del blueprint de confirmaciones."""
    logger.warning(f"Pagina no encontrada en confirmacion: {request.url}")
    return render_template(
        'confirmacion/error.html',
        mensaje='La pagina solicitada no existe',
        titulo='Pagina No Encontrada'
    ), 404


@confirmacion_bp.errorhandler(500)
def internal_error(error):
    """Maneja errores 500 especificos del blueprint de confirmaciones."""
    logger.error(f"Error interno en confirmacion: {error}", exc_info=True)
    return render_template(
        'confirmacion/error.html',
        mensaje='Ocurrio un error interno en el servidor',
        titulo='Error del Servidor'
    ), 500