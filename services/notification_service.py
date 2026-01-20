"""
Servicio unificado de notificaciones por email para:
- Inventario Corporativo (asignaciones)
- Material POP (solicitudes y novedades)
- PrÃ©stamos

VersiÃ³n segura - Cumple con reporte de vulnerabilidades
"""
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from database import get_database_connection
import os
from utils.helpers import sanitizar_ip  # âœ… DÃA 5

logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURACIÃ“N DE EMAIL - Cargada desde variables de entorno
# ============================================================================
def _load_email_config():
    """Carga configuraciÃ³n de email desde variables de entorno"""
    try:
        smtp_server = os.getenv('SMTP_SERVER')
        smtp_port = os.getenv('SMTP_PORT', '25')
        use_tls = os.getenv('SMTP_USE_TLS', 'False').lower() == 'true'
        from_email = os.getenv('SMTP_FROM_EMAIL', 'noreply@qualitascolombia.com.co')
        
        # DEPURACIÃ“N: Mostrar lo que se estÃ¡ cargando
        print(f"\n=== CONFIGURACIÃ“N SMTP CARGADA ===")
        print(f"SMTP_SERVER: {sanitizar_ip(smtp_server) if smtp_server else 'No configurado'}")
        print(f"SMTP_PORT: {smtp_port}")
        print(f"SMTP_USE_TLS: {use_tls}")
        print(f"SMTP_FROM_EMAIL: {from_email}")
        print(f"TODAS LAS VARIABLES DE ENTORNO:")
        for key, value in os.environ.items():
            if 'SMTP' in key or 'EMAIL' in key:
                print(f"  {key}: {value}")
        print("================================\n")
        
        if not smtp_server:
            print("âš ï¸ CRÃTICO: SMTP_SERVER no configurado en variables de entorno")
            return None
            
        config = {
            'smtp_server': smtp_server,
            'smtp_port': int(smtp_port),
            'use_tls': use_tls,
            'smtp_user': os.getenv('SMTP_USER', ''),
            'smtp_password': os.getenv('SMTP_PASSWORD', ''),
            'from_email': from_email,
            'from_name': 'Sistema de GestiÃ³n de Inventarios'
        }
        
        print(f"âœ… ConfiguraciÃ³n SMTP cargada exitosamente")
        return config
        
    except Exception as e:
        print(f"âŒ Error cargando configuraciÃ³n de email: {e}")
        return None

EMAIL_CONFIG = _load_email_config()

# ============================================================================
# COLORES Y ESTILOS COMPARTIDOS
# ============================================================================
ESTILOS = {
    'colores': {
        'primario': '#0d6efd',
        'primario_oscuro': '#0a58ca',
        'exito': '#198754',
        'peligro': '#dc3545',
        'advertencia': '#ffc107',
        'info': '#0dcaf0',
        'secundario': '#6c757d',
        'claro': '#f8f9fa',
        'oscuro': '#212529'
    },
    'estados_solicitud': {
        'Pendiente': {'color': '#ffc107', 'icono': 'â³', 'bg': '#fff3cd'},
        'Aprobada': {'color': '#198754', 'icono': 'âœ…', 'bg': '#d1e7dd'},
        'Rechazada': {'color': '#dc3545', 'icono': 'âŒ', 'bg': '#f8d7da'},
        'Entregada Parcial': {'color': '#0dcaf0', 'icono': 'ðŸ“¦', 'bg': '#cff4fc'},
        'Completada': {'color': '#198754', 'icono': 'âœ”ï¸', 'bg': '#d1e7dd'},
        'Devuelta': {'color': '#6c757d', 'icono': 'â†©ï¸', 'bg': '#e9ecef'},
        'Novedad Registrada': {'color': '#fd7e14', 'icono': 'âš ï¸', 'bg': '#ffe5d0'},
        'Novedad Aceptada': {'color': '#198754', 'icono': 'âœ…', 'bg': '#d1e7dd'},
        'Novedad Rechazada': {'color': '#dc3545', 'icono': 'âŒ', 'bg': '#f8d7da'}
    },
    'estados_prestamo': {
        'PRESTADO': {'color': '#ffc107', 'icono': 'ðŸ“‹', 'bg': '#fff3cd'},
        'APROBADO': {'color': '#198754', 'icono': 'âœ…', 'bg': '#d1e7dd'},
        'APROBADO_PARCIAL': {'color': '#0dcaf0', 'icono': 'ðŸ“¦', 'bg': '#cff4fc'},
        'RECHAZADO': {'color': '#dc3545', 'icono': 'âŒ', 'bg': '#f8d7da'},
        'DEVUELTO': {'color': '#6c757d', 'icono': 'â†©ï¸', 'bg': '#e9ecef'}
    }
}

# ============================================================================
# CLASE PRINCIPAL DE NOTIFICACIONES
# ============================================================================
class NotificationService:
    """Servicio unificado para enviar notificaciones por email"""
    
    # ========================================================================
    # MÃ‰TODOS AUXILIARES SEGUROS
    # ========================================================================
    
    @staticmethod
    def _obtener_email_usuario(usuario_id):
        """Obtiene el email de un usuario por su ID de forma segura"""
        conn = get_database_connection()
        if not conn:
            return None
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT CorreoElectronico FROM Usuarios WHERE UsuarioId = ? AND Activo = 1",
                (usuario_id,)
            )
            row = cursor.fetchone()
            return row[0] if row else None
        except Exception:
            # Log genÃ©rico sin detalles sensibles
            logger.warning(f"No se pudo obtener email del usuario ID: {usuario_id}")
            return None
        finally:
            cursor.close()
            conn.close()
    
    @staticmethod
    def _obtener_emails_aprobadores():
        """Obtiene los emails de todos los aprobadores activos de forma segura"""
        conn = get_database_connection()
        if not conn:
            return []
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT DISTINCT u.CorreoElectronico 
                FROM Aprobadores a
                INNER JOIN Usuarios u ON a.UsuarioId = u.UsuarioId
                WHERE a.Activo = 1 AND u.Activo = 1 AND u.CorreoElectronico IS NOT NULL
            """)
            return [row[0] for row in cursor.fetchall() if row[0]]
        except Exception:
            logger.warning("Error obteniendo emails de aprobadores")
            return []
        finally:
            cursor.close()
            conn.close()
    
    @staticmethod
    def _obtener_emails_gestores():
        """Obtiene emails de administradores y lÃ­deres de inventario de forma segura"""
        conn = get_database_connection()
        if not conn:
            return []
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT CorreoElectronico 
                FROM Usuarios 
                WHERE Activo = 1 
                AND CorreoElectronico IS NOT NULL
                AND Rol IN ('administrador', 'lider_inventario', 'Administrador', 'Lider_inventario')
            """)
            return [row[0] for row in cursor.fetchall() if row[0]]
        except Exception:
            logger.warning("Error obteniendo emails de gestores")
            return []
        finally:
            cursor.close()
            conn.close()
    
    @staticmethod
    def _generar_estilos_base():
        """Genera los estilos CSS base para todos los emails"""
        return f'''
            body {{
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                line-height: 1.6;
                color: #333;
                max-width: 600px;
                margin: 0 auto;
                padding: 20px;
                background-color: #f5f5f5;
            }}
            .container {{
                background: white;
                border-radius: 10px;
                overflow: hidden;
                box-shadow: 0 4px 15px rgba(0,0,0,0.1);
            }}
            .header {{
                background: linear-gradient(135deg, {ESTILOS['colores']['primario']} 0%, {ESTILOS['colores']['primario_oscuro']} 100%);
                color: white;
                padding: 30px;
                text-align: center;
            }}
            .header h1 {{
                margin: 0;
                font-size: 24px;
            }}
            .content {{
                padding: 30px;
            }}
            .card {{
                background: {ESTILOS['colores']['claro']};
                border-radius: 10px;
                padding: 20px;
                margin: 20px 0;
                border-left: 4px solid {ESTILOS['colores']['primario']};
            }}
            .detail-row {{
                display: flex;
                justify-content: space-between;
                padding: 10px 0;
                border-bottom: 1px solid #eee;
            }}
            .detail-label {{
                color: #666;
                font-weight: 500;
            }}
            .detail-value {{
                font-weight: bold;
                color: #333;
            }}
            .badge {{
                display: inline-block;
                padding: 5px 15px;
                border-radius: 20px;
                font-weight: bold;
                font-size: 14px;
            }}
            .footer {{
                background: #e9ecef;
                padding: 20px;
                text-align: center;
                font-size: 12px;
                color: #666;
            }}
            .btn {{
                display: inline-block;
                background: {ESTILOS['colores']['primario']};
                color: white;
                padding: 12px 30px;
                text-decoration: none;
                border-radius: 5px;
                margin-top: 20px;
                font-weight: bold;
            }}
        '''
    
    @staticmethod
    def _enviar_email(destinatario_email, asunto, contenido_html, contenido_texto):
        """EnvÃ­a el email usando SMTP de forma segura"""
        if not EMAIL_CONFIG:
            logger.warning("âš ï¸ ConfiguraciÃ³n de email no disponible")
            return False
            
        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = asunto
            msg['From'] = f'{EMAIL_CONFIG["from_name"]} <{EMAIL_CONFIG["from_email"]}>'
            msg['To'] = destinatario_email
            
            part1 = MIMEText(contenido_texto, 'plain', 'utf-8')
            part2 = MIMEText(contenido_html, 'html', 'utf-8')
            msg.attach(part1)
            msg.attach(part2)
            
            # Usar TLS si estÃ¡ configurado
            if EMAIL_CONFIG['use_tls']:
                server = smtplib.SMTP_SSL(
                    EMAIL_CONFIG['smtp_server'], 
                    EMAIL_CONFIG['smtp_port'], 
                    timeout=30
                )
            else:
                server = smtplib.SMTP(
                    EMAIL_CONFIG['smtp_server'], 
                    EMAIL_CONFIG['smtp_port'], 
                    timeout=30
                )
            
            if EMAIL_CONFIG['use_tls'] and EMAIL_CONFIG['smtp_user'] and EMAIL_CONFIG['smtp_password']:
                server.login(EMAIL_CONFIG['smtp_user'], EMAIL_CONFIG['smtp_password'])
            
            server.sendmail(EMAIL_CONFIG['from_email'], destinatario_email, msg.as_string())
            server.quit()
            
            # Log seguro sin exponer informaciÃ³n sensible
            logger.info(f"âœ… Email enviado exitosamente")
            return True
            
        except Exception as e:
            # Log seguro - solo tipo de error sin detalles
            error_type = type(e).__name__
            logger.warning(f"âŒ Error enviando email ({error_type})")
            return False

    # ========================================================================
    # NOTIFICACIONES - INVENTARIO CORPORATIVO
    # ========================================================================
    
    @staticmethod
    def enviar_notificacion_asignacion(destinatario_email, destinatario_nombre, 
                                        producto_info, cantidad, oficina_nombre,
                                        asignador_nombre):
        """EnvÃ­a notificaciÃ³n de asignaciÃ³n de producto del inventario corporativo"""
        fecha_actual = datetime.now().strftime('%d/%m/%Y %H:%M')
        
        asunto = f'ðŸ“¦ AsignaciÃ³n de Inventario - {producto_info.get("nombre", "Producto")}'
        
        html = f'''
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>{NotificationService._generar_estilos_base()}</style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>ðŸ“¦ Nueva AsignaciÃ³n de Inventario</h1>
                </div>
                <div class="content">
                    <p>Hola <strong>{destinatario_nombre}</strong>,</p>
                    <p>Se te ha asignado el siguiente elemento del inventario corporativo:</p>
                    
                    <div class="card">
                        <h3 style="color: {ESTILOS['colores']['primario']}; margin-top: 0;">
                            {producto_info.get('nombre', 'Producto')}
                        </h3>
                        <div class="detail-row">
                            <span class="detail-label">CÃ³digo:</span>
                            <span class="detail-value">{producto_info.get('codigo_unico', 'N/A')}</span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-label">CategorÃ­a:</span>
                            <span class="detail-value">{producto_info.get('categoria', 'N/A')}</span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-label">Cantidad Asignada:</span>
                            <span class="badge" style="background: {ESTILOS['colores']['exito']}; color: white;">
                                {cantidad} unidad(es)
                            </span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-label">Oficina Destino:</span>
                            <span class="detail-value">{oficina_nombre}</span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-label">Asignado por:</span>
                            <span class="detail-value">{asignador_nombre}</span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-label">Fecha:</span>
                            <span class="detail-value">{fecha_actual}</span>
                        </div>
                    </div>
                    
                    <p style="color: #666;">
                        Por favor, confirma la recepciÃ³n de este elemento con el Ã¡rea de inventario.
                    </p>
                </div>
                <div class="footer">
                    <p>Este es un mensaje automÃ¡tico del Sistema de GestiÃ³n de Inventarios.</p>
                    <p>Qualitas Colombia - {datetime.now().year}</p>
                </div>
            </div>
        </body>
        </html>
        '''
        
        texto = f'''
NUEVA ASIGNACIÃ“N DE INVENTARIO CORPORATIVO
==========================================

Hola {destinatario_nombre},

Se te ha asignado: {producto_info.get('nombre', 'Producto')}
CÃ³digo: {producto_info.get('codigo_unico', 'N/A')}
Cantidad: {cantidad} unidad(es)
Oficina: {oficina_nombre}
Asignado por: {asignador_nombre}
Fecha: {fecha_actual}

---
Sistema de GestiÃ³n de Inventarios - Qualitas Colombia
        '''
        
        return NotificationService._enviar_email(destinatario_email, asunto, html, texto)
    
    @staticmethod
    def enviar_notificacion_asignacion_con_confirmacion(destinatario_email, destinatario_nombre, 
                                                        producto_info, cantidad, oficina_nombre,
                                                        asignador_nombre, token_confirmacion=None,
                                                        base_url='http://localhost:5000'):
        """
        EnvÃ­a notificaciÃ³n de asignaciÃ³n de producto con link de confirmaciÃ³n.
        """
        fecha_actual = datetime.now().strftime('%d/%m/%Y %H:%M')
        
        # Generar link de confirmaciÃ³n si hay token
        link_confirmacion = None
        if token_confirmacion:
            link_confirmacion = f"{base_url}/confirmacion/confirmar-asignacion/{token_confirmacion}"
        
        asunto = f'ðŸ“¦ AsignaciÃ³n de Inventario - {producto_info.get("nombre", "Producto")}'
        
        # Construir el bloque de confirmaciÃ³n por separado
        bloque_confirmacion = ''
        if token_confirmacion and link_confirmacion:
            bloque_confirmacion = f'''
                    <div class="card" style="background: #fff3cd; border-left-color: #ffc107;">
                        <h4 style="color: #856404; margin-top: 0;">âš ï¸ ACCIÃ“N REQUERIDA</h4>
                        <p style="color: #856404; margin-bottom: 15px;">
                            Debe confirmar la recepciÃ³n de este elemento dentro de los prÃ³ximos <strong>8 dÃ­as</strong>.
                        </p>
                        <center>
                            <a href="{link_confirmacion}" class="btn" style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);">
                                âœ… CONFIRMAR RECEPCIÃ“N
                            </a>
                        </center>
                        <p style="font-size: 12px; color: #666; margin-top: 15px; margin-bottom: 0;">
                            Si el botÃ³n no funciona, copie y pegue este enlace en su navegador:<br>
                            <a href="{link_confirmacion}" style="word-break: break-all;">{link_confirmacion}</a>
                        </p>
                    </div>
            '''
        else:
            bloque_confirmacion = '<p style="color: #666;">Por favor, confirma la recepciÃ³n de este elemento con el Ã¡rea de inventario.</p>'
        
        html = f'''
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>{NotificationService._generar_estilos_base()}</style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>ðŸ“¦ Nueva AsignaciÃ³n de Inventario</h1>
                </div>
                <div class="content">
                    <p>Hola <strong>{destinatario_nombre}</strong>,</p>
                    <p>Se te ha asignado el siguiente elemento del inventario corporativo:</p>
                    
                    <div class="card">
                        <h3 style="color: {ESTILOS['colores']['primario']}; margin-top: 0;">
                            {producto_info.get('nombre', 'Producto')}
                        </h3>
                        <div class="detail-row">
                            <span class="detail-label">CÃ³digo:</span>
                            <span class="detail-value">{producto_info.get('codigo_unico', 'N/A')}</span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-label">CategorÃ­a:</span>
                            <span class="detail-value">{producto_info.get('categoria', 'N/A')}</span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-label">Cantidad Asignada:</span>
                            <span class="badge" style="background: {ESTILOS['colores']['exito']}; color: white;">
                                {cantidad} unidad(es)
                            </span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-label">Oficina Destino:</span>
                            <span class="detail-value">{oficina_nombre}</span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-label">Asignado por:</span>
                            <span class="detail-value">{asignador_nombre}</span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-label">Fecha:</span>
                            <span class="detail-value">{fecha_actual}</span>
                        </div>
                    </div>
                    
                    {bloque_confirmacion}
                    
                    <p style="color: #666; font-size: 14px; margin-top: 20px;">
                        Si tiene alguna pregunta o problema con esta asignaciÃ³n, 
                        por favor contacte al departamento de inventario.
                    </p>
                </div>
                <div class="footer">
                    <p>Este es un mensaje automÃ¡tico del Sistema de GestiÃ³n de Inventarios.</p>
                    <p>Qualitas Colombia - {datetime.now().year}</p>
                </div>
            </div>
        </body>
        </html>
        '''
        
        texto_confirmacion = ''
        if token_confirmacion and link_confirmacion:
            texto_confirmacion = f'''
IMPORTANTE: Debe confirmar la recepciÃ³n dentro de los prÃ³ximos 8 dÃ­as.
Link de confirmaciÃ³n: {link_confirmacion}
'''
        
        texto = f'''
NUEVA ASIGNACIÃ“N DE INVENTARIO CORPORATIVO
==========================================

Hola {destinatario_nombre},

Se te ha asignado: {producto_info.get('nombre', 'Producto')}
CÃ³digo: {producto_info.get('codigo_unico', 'N/A')}
Cantidad: {cantidad} unidad(es)
Oficina: {oficina_nombre}
Asignado por: {asignador_nombre}
Fecha: {fecha_actual}

{texto_confirmacion}
---
Sistema de GestiÃ³n de Inventarios - Qualitas Colombia
        '''
        
        return NotificationService._enviar_email(destinatario_email, asunto, html, texto)
    
    @staticmethod
    def enviar_notificacion_confirmacion_asignacion(asignacion_id, producto_nombre, 
                                                     usuario_nombre, usuario_email):
        """
        EnvÃ­a notificaciÃ³n a los gestores cuando el usuario confirma la recepciÃ³n.
        """
        emails_gestores = NotificationService._obtener_emails_gestores()
        
        if not emails_gestores:
            logger.warning("No hay gestores configurados para notificar confirmaciÃ³n")
            return False
        
        fecha_actual = datetime.now().strftime('%d/%m/%Y %H:%M')
        
        asunto = f"âœ… ConfirmaciÃ³n de RecepciÃ³n: {producto_nombre}"
        
        html = f'''
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>{NotificationService._generar_estilos_base()}</style>
        </head>
        <body>
            <div class="container">
                <div class="header" style="background: linear-gradient(135deg, {ESTILOS['colores']['exito']} 0%, #146c43 100%);">
                    <h1>âœ… RecepciÃ³n Confirmada</h1>
                </div>
                <div class="content">
                    <p>Se ha confirmado la recepciÃ³n del siguiente producto:</p>
                    
                    <div class="card" style="border-left-color: {ESTILOS['colores']['exito']};">
                        <div class="detail-row">
                            <span class="detail-label">Producto:</span>
                            <span class="detail-value">{producto_nombre}</span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-label">Usuario:</span>
                            <span class="detail-value">{usuario_nombre}</span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-label">Email:</span>
                            <span class="detail-value">{usuario_email}</span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-label">ID AsignaciÃ³n:</span>
                            <span class="detail-value">#{asignacion_id}</span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-label">Fecha de confirmaciÃ³n:</span>
                            <span class="badge" style="background: {ESTILOS['colores']['exito']}; color: white;">
                                {fecha_actual}
                            </span>
                        </div>
                    </div>
                    
                    <p style="color: #666;">
                        El usuario ha confirmado exitosamente la recepciÃ³n del elemento asignado.
                    </p>
                </div>
                <div class="footer">
                    <p>Sistema de GestiÃ³n de Inventarios - Qualitas Colombia</p>
                </div>
            </div>
        </body>
        </html>
        '''
        
        texto = f'''
CONFIRMACIÃ“N DE RECEPCIÃ“N
=========================

Producto: {producto_nombre}
Usuario: {usuario_nombre}
Email: {usuario_email}
ID AsignaciÃ³n: #{asignacion_id}
Fecha de confirmaciÃ³n: {fecha_actual}

El usuario ha confirmado exitosamente la recepciÃ³n del elemento.

---
Sistema de GestiÃ³n de Inventarios - Qualitas Colombia
        '''
        
        exitos = 0
        for email in emails_gestores:
            if NotificationService._enviar_email(email, asunto, html, texto):
                exitos += 1
        
        return exitos > 0

    # ========================================================================
    # NOTIFICACIONES - MATERIAL POP (SOLICITUDES)
    # ========================================================================
    
    @staticmethod
    def notificar_solicitud_creada(solicitud_info):
        """Notifica a los aprobadores cuando se crea una nueva solicitud"""
        emails_aprobadores = NotificationService._obtener_emails_aprobadores()
        
        if not emails_aprobadores:
            logger.warning("No hay aprobadores configurados para notificar")
            return False
        
        fecha_actual = datetime.now().strftime('%d/%m/%Y %H:%M')
        estado_config = ESTILOS['estados_solicitud'].get('Pendiente', {})
        
        asunto = f'ðŸ“‹ Nueva Solicitud de Material - {solicitud_info.get("material_nombre", "Material")}'
        
        html = f'''
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>{NotificationService._generar_estilos_base()}</style>
        </head>
        <body>
            <div class="container">
                <div class="header" style="background: linear-gradient(135deg, {estado_config.get('color', '#ffc107')} 0%, #e0a800 100%);">
                    <h1>ðŸ“‹ Nueva Solicitud de Material</h1>
                </div>
                <div class="content">
                    <p>Se ha creado una nueva solicitud que requiere su aprobaciÃ³n:</p>
                    
                    <div class="card" style="border-left-color: {estado_config.get('color', '#ffc107')};">
                        <div class="detail-row">
                            <span class="detail-label">Material:</span>
                            <span class="detail-value">{solicitud_info.get('material_nombre', 'N/A')}</span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-label">Cantidad Solicitada:</span>
                            <span class="badge" style="background: {ESTILOS['colores']['primario']}; color: white;">
                                {solicitud_info.get('cantidad_solicitada', 0)} unidades
                            </span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-label">Oficina Solicitante:</span>
                            <span class="detail-value">{solicitud_info.get('oficina_nombre', 'N/A')}</span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-label">Solicitante:</span>
                            <span class="detail-value">{solicitud_info.get('usuario_solicitante', 'N/A')}</span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-label">Estado:</span>
                            <span class="badge" style="background: {estado_config.get('bg', '#fff3cd')}; color: {estado_config.get('color', '#856404')};">
                                â³ Pendiente de AprobaciÃ³n
                            </span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-label">Fecha:</span>
                            <span class="detail-value">{fecha_actual}</span>
                        </div>
                    </div>
                    
                    <p style="color: #666;">
                        Por favor, revise y procese esta solicitud a la brevedad.
                    </p>
                </div>
                <div class="footer">
                    <p>Sistema de GestiÃ³n de Inventarios - Qualitas Colombia</p>
                </div>
            </div>
        </body>
        </html>
        '''
        
        texto = f'''
NUEVA SOLICITUD DE MATERIAL
===========================

Material: {solicitud_info.get('material_nombre', 'N/A')}
Cantidad: {solicitud_info.get('cantidad_solicitada', 0)} unidades
Oficina: {solicitud_info.get('oficina_nombre', 'N/A')}
Solicitante: {solicitud_info.get('usuario_solicitante', 'N/A')}
Estado: Pendiente de AprobaciÃ³n
Fecha: {fecha_actual}

---
Sistema de GestiÃ³n de Inventarios - Qualitas Colombia
        '''
        
        exitos = 0
        for email in emails_aprobadores:
            if NotificationService._enviar_email(email, asunto, html, texto):
                exitos += 1
        
        return exitos > 0

    @staticmethod
    def notificar_cambio_estado_solicitud(solicitud_info, estado_anterior, estado_nuevo, 
                                           usuario_accion, observacion=''):
        """Notifica al solicitante cuando cambia el estado de su solicitud"""
        
        email_destino = solicitud_info.get('email_solicitante')
        
        if not email_destino:
            logger.warning(f"No se encontrÃ³ email para notificar solicitud {solicitud_info.get('id')}")
            return False
        
        fecha_actual = datetime.now().strftime('%d/%m/%Y %H:%M')
        estado_config = ESTILOS['estados_solicitud'].get(estado_nuevo, {})
        
        asunto = f'{estado_config.get("icono", "ðŸ“‹")} Solicitud {estado_nuevo} - {solicitud_info.get("material_nombre", "Material")}'
        
        observacion_html = f'<div class="detail-row"><span class="detail-label">ObservaciÃ³n:</span><span class="detail-value">{observacion}</span></div>' if observacion else ''
        
        html = f'''
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>{NotificationService._generar_estilos_base()}</style>
        </head>
        <body>
            <div class="container">
                <div class="header" style="background: linear-gradient(135deg, {estado_config.get('color', ESTILOS['colores']['primario'])} 0%, {ESTILOS['colores']['primario_oscuro']} 100%);">
                    <h1>{estado_config.get('icono', 'ðŸ“‹')} Solicitud {estado_nuevo}</h1>
                </div>
                <div class="content">
                    <p>Hola <strong>{solicitud_info.get('usuario_solicitante', '')}</strong>,</p>
                    <p>Tu solicitud de material ha cambiado de estado:</p>
                    
                    <div class="card" style="border-left-color: {estado_config.get('color', ESTILOS['colores']['primario'])};">
                        <div class="detail-row">
                            <span class="detail-label">Material:</span>
                            <span class="detail-value">{solicitud_info.get('material_nombre', 'N/A')}</span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-label">Cantidad:</span>
                            <span class="detail-value">{solicitud_info.get('cantidad_solicitada', 0)} unidades</span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-label">Estado Anterior:</span>
                            <span class="detail-value">{estado_anterior}</span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-label">Nuevo Estado:</span>
                            <span class="badge" style="background: {estado_config.get('bg', '#e9ecef')}; color: {estado_config.get('color', '#333')};">
                                {estado_config.get('icono', '')} {estado_nuevo}
                            </span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-label">Procesado por:</span>
                            <span class="detail-value">{usuario_accion}</span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-label">Fecha:</span>
                            <span class="detail-value">{fecha_actual}</span>
                        </div>
                        {observacion_html}
                    </div>
                </div>
                <div class="footer">
                    <p>Sistema de GestiÃ³n de Inventarios - Qualitas Colombia</p>
                </div>
            </div>
        </body>
        </html>
        '''
        
        texto_observacion = f'\nObservaciÃ³n: {observacion}' if observacion else ''
        
        texto = f'''
ACTUALIZACIÃ“N DE SOLICITUD
==========================

Material: {solicitud_info.get('material_nombre', 'N/A')}
Cantidad: {solicitud_info.get('cantidad_solicitada', 0)} unidades
Estado Anterior: {estado_anterior}
Nuevo Estado: {estado_nuevo}
Procesado por: {usuario_accion}
Fecha: {fecha_actual}{texto_observacion}

---
Sistema de GestiÃ³n de Inventarios - Qualitas Colombia
        '''
        
        return NotificationService._enviar_email(email_destino, asunto, html, texto)

    @staticmethod
    def notificar_novedad_registrada(solicitud_info, novedad_info):
        """Notifica a los gestores cuando se registra una novedad"""
        emails_gestores = NotificationService._obtener_emails_gestores()
        
        if not emails_gestores:
            return False
        
        fecha_actual = datetime.now().strftime('%d/%m/%Y %H:%M')
        
        asunto = f'âš ï¸ Nueva Novedad Registrada - Solicitud #{solicitud_info.get("id", "N/A")}'
        
        html = f'''
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>{NotificationService._generar_estilos_base()}</style>
        </head>
        <body>
            <div class="container">
                <div class="header" style="background: linear-gradient(135deg, #fd7e14 0%, #e65c00 100%);">
                    <h1>âš ï¸ Nueva Novedad Registrada</h1>
                </div>
                <div class="content">
                    <p>Se ha registrado una novedad que requiere su atenciÃ³n:</p>
                    
                    <div class="card" style="border-left-color: #fd7e14;">
                        <div class="detail-row">
                            <span class="detail-label">Solicitud #:</span>
                            <span class="detail-value">{solicitud_info.get('id', 'N/A')}</span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-label">Material:</span>
                            <span class="detail-value">{solicitud_info.get('material_nombre', 'N/A')}</span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-label">Tipo de Novedad:</span>
                            <span class="badge" style="background: #ffe5d0; color: #fd7e14;">
                                {novedad_info.get('tipo', 'N/A')}
                            </span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-label">DescripciÃ³n:</span>
                            <span class="detail-value">{novedad_info.get('descripcion', 'N/A')}</span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-label">Cantidad Afectada:</span>
                            <span class="detail-value">{novedad_info.get('cantidad_afectada', 0)}</span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-label">Registrado por:</span>
                            <span class="detail-value">{novedad_info.get('usuario_registra', 'N/A')}</span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-label">Fecha:</span>
                            <span class="detail-value">{fecha_actual}</span>
                        </div>
                    </div>
                    
                    <p style="color: #666;">
                        Por favor, revise y gestione esta novedad.
                    </p>
                </div>
                <div class="footer">
                    <p>Sistema de GestiÃ³n de Inventarios - Qualitas Colombia</p>
                </div>
            </div>
        </body>
        </html>
        '''
        
        texto = f'''
NUEVA NOVEDAD REGISTRADA
========================

Solicitud #: {solicitud_info.get('id', 'N/A')}
Material: {solicitud_info.get('material_nombre', 'N/A')}
Tipo: {novedad_info.get('tipo', 'N/A')}
DescripciÃ³n: {novedad_info.get('descripcion', 'N/A')}
Cantidad Afectada: {novedad_info.get('cantidad_afectada', 0)}
Registrado por: {novedad_info.get('usuario_registra', 'N/A')}

---
Sistema de GestiÃ³n de Inventarios - Qualitas Colombia
        '''
        
        exitos = 0
        for email in emails_gestores:
            if NotificationService._enviar_email(email, asunto, html, texto):
                exitos += 1
        
        return exitos > 0

    # ========================================================================
    # NOTIFICACIONES - PRÃ‰STAMOS
    # ========================================================================
    
    @staticmethod
    def notificar_prestamo_creado(prestamo_info):
        """Notifica a los gestores cuando se crea un nuevo prÃ©stamo"""
        emails_gestores = NotificationService._obtener_emails_gestores()
        
        if not emails_gestores:
            return False
        
        fecha_actual = datetime.now().strftime('%d/%m/%Y %H:%M')
        estado_config = ESTILOS['estados_prestamo'].get('PRESTADO', {})
        
        asunto = f'ðŸ“‹ Nuevo PrÃ©stamo Solicitado - {prestamo_info.get("material", "Material")}'
        
        html = f'''
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>{NotificationService._generar_estilos_base()}</style>
        </head>
        <body>
            <div class="container">
                <div class="header" style="background: linear-gradient(135deg, {estado_config.get('color', '#ffc107')} 0%, #e0a800 100%);">
                    <h1>ðŸ“‹ Nuevo PrÃ©stamo Solicitado</h1>
                </div>
                <div class="content">
                    <p>Se ha registrado un nuevo prÃ©stamo que requiere aprobaciÃ³n:</p>
                    
                    <div class="card" style="border-left-color: {estado_config.get('color', '#ffc107')};">
                        <div class="detail-row">
                            <span class="detail-label">Elemento:</span>
                            <span class="detail-value">{prestamo_info.get('material', 'N/A')}</span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-label">Cantidad:</span>
                            <span class="badge" style="background: {ESTILOS['colores']['primario']}; color: white;">
                                {prestamo_info.get('cantidad', 0)} unidades
                            </span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-label">Solicitante:</span>
                            <span class="detail-value">{prestamo_info.get('solicitante_nombre', 'N/A')}</span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-label">Oficina:</span>
                            <span class="detail-value">{prestamo_info.get('oficina_nombre', 'N/A')}</span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-label">Evento:</span>
                            <span class="detail-value">{prestamo_info.get('evento', 'N/A')}</span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-label">Fecha DevoluciÃ³n Prevista:</span>
                            <span class="detail-value">{prestamo_info.get('fecha_prevista', 'N/A')}</span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-label">Estado:</span>
                            <span class="badge" style="background: {estado_config.get('bg', '#fff3cd')}; color: {estado_config.get('color', '#856404')};">
                                ðŸ“‹ Pendiente de AprobaciÃ³n
                            </span>
                        </div>
                    </div>
                </div>
                <div class="footer">
                    <p>Sistema de GestiÃ³n de Inventarios - Qualitas Colombia</p>
                </div>
            </div>
        </body>
        </html>
        '''
        
        texto = f'''
NUEVO PRÃ‰STAMO SOLICITADO
=========================

Elemento: {prestamo_info.get('material', 'N/A')}
Cantidad: {prestamo_info.get('cantidad', 0)} unidades
Solicitante: {prestamo_info.get('solicitante_nombre', 'N/A')}
Oficina: {prestamo_info.get('oficina_nombre', 'N/A')}
Evento: {prestamo_info.get('evento', 'N/A')}
Fecha DevoluciÃ³n Prevista: {prestamo_info.get('fecha_prevista', 'N/A')}

---
Sistema de GestiÃ³n de Inventarios - Qualitas Colombia
        '''
        
        exitos = 0
        for email in emails_gestores:
            if NotificationService._enviar_email(email, asunto, html, texto):
                exitos += 1
        
        return exitos > 0

    @staticmethod
    def notificar_cambio_estado_prestamo(prestamo_info, estado_nuevo, usuario_accion, observacion=''):
        """Notifica al solicitante cuando cambia el estado de su prÃ©stamo"""
        
        email_destino = prestamo_info.get('email_solicitante')
        
        if not email_destino:
            logger.warning(f"No se encontrÃ³ email para notificar prÃ©stamo {prestamo_info.get('id')}")
            return False
        
        fecha_actual = datetime.now().strftime('%d/%m/%Y %H:%M')
        estado_config = ESTILOS['estados_prestamo'].get(estado_nuevo, {})
        
        asunto = f'{estado_config.get("icono", "ðŸ“‹")} PrÃ©stamo {estado_nuevo} - {prestamo_info.get("material", "Material")}'
        
        observacion_html = f'<div class="detail-row"><span class="detail-label">ObservaciÃ³n:</span><span class="detail-value">{observacion}</span></div>' if observacion else ''
        
        html = f'''
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>{NotificationService._generar_estilos_base()}</style>
        </head>
        <body>
            <div class="container">
                <div class="header" style="background: linear-gradient(135deg, {estado_config.get('color', ESTILOS['colores']['primario'])} 0%, {ESTILOS['colores']['primario_oscuro']} 100%);">
                    <h1>{estado_config.get('icono', 'ðŸ“‹')} PrÃ©stamo {estado_nuevo}</h1>
                </div>
                <div class="content">
                    <p>Hola <strong>{prestamo_info.get('solicitante_nombre', '')}</strong>,</p>
                    <p>Tu prÃ©stamo ha sido actualizado:</p>
                    
                    <div class="card" style="border-left-color: {estado_config.get('color', ESTILOS['colores']['primario'])};">
                        <div class="detail-row">
                            <span class="detail-label">Elemento:</span>
                            <span class="detail-value">{prestamo_info.get('material', 'N/A')}</span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-label">Cantidad:</span>
                            <span class="detail-value">{prestamo_info.get('cantidad', 0)} unidades</span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-label">Nuevo Estado:</span>
                            <span class="badge" style="background: {estado_config.get('bg', '#e9ecef')}; color: {estado_config.get('color', '#333')};">
                                {estado_config.get('icono', '')} {estado_nuevo}
                            </span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-label">Procesado por:</span>
                            <span class="detail-value">{usuario_accion}</span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-label">Fecha:</span>
                            <span class="detail-value">{fecha_actual}</span>
                        </div>
                        {observacion_html}
                    </div>
                </div>
                <div class="footer">
                    <p>Sistema de GestiÃ³n de Inventarios - Qualitas Colombia</p>
                </div>
            </div>
        </body>
        </html>
        '''
        
        texto_observacion = f'\nObservaciÃ³n: {observacion}' if observacion else ''
        
        texto = f'''
ACTUALIZACIÃ“N DE PRÃ‰STAMO
=========================

Elemento: {prestamo_info.get('material', 'N/A')}
Cantidad: {prestamo_info.get('cantidad', 0)} unidades
Nuevo Estado: {estado_nuevo}
Procesado por: {usuario_accion}
Fecha: {fecha_actual}{texto_observacion}

---
Sistema de GestiÃ³n de Inventarios - Qualitas Colombia
        '''
        
        return NotificationService._enviar_email(email_destino, asunto, html, texto)


# ============================================================================
# FUNCIONES DE CONVENIENCIA (compatibilidad con cÃ³digo existente)
# ============================================================================

def notificar_asignacion_inventario(destinatario_email, destinatario_nombre, 
                                     producto_info, cantidad, oficina_nombre, asignador_nombre):
    """Wrapper para compatibilidad con cÃ³digo existente"""
    return NotificationService.enviar_notificacion_asignacion(
        destinatario_email, destinatario_nombre, producto_info, 
        cantidad, oficina_nombre, asignador_nombre
    )

def notificar_solicitud(solicitud_info, tipo_notificacion, **kwargs):
    """
    FunciÃ³n genÃ©rica para notificar sobre solicitudes
    """
    if tipo_notificacion == 'creada':
        return NotificationService.notificar_solicitud_creada(solicitud_info)
    elif tipo_notificacion in ['aprobada', 'rechazada', 'entregada', 'devuelta']:
        return NotificationService.notificar_cambio_estado_solicitud(
            solicitud_info, 
            kwargs.get('estado_anterior', 'Pendiente'),
            tipo_notificacion.capitalize(),
            kwargs.get('usuario_accion', 'Sistema'),
            kwargs.get('observacion', '')
        )
    elif tipo_notificacion == 'novedad':
        return NotificationService.notificar_novedad_registrada(
            solicitud_info, 
            kwargs.get('novedad_info', {})
        )
    return False

def notificar_prestamo(prestamo_info, tipo_notificacion, **kwargs):
    """
    FunciÃ³n genÃ©rica para notificar sobre prÃ©stamos
    """
    if tipo_notificacion == 'creado':
        return NotificationService.notificar_prestamo_creado(prestamo_info)
    else:
        estado_map = {
            'aprobado': 'APROBADO',
            'aprobado_parcial': 'APROBADO_PARCIAL',
            'rechazado': 'RECHAZADO',
            'devuelto': 'DEVUELTO'
        }
        return NotificationService.notificar_cambio_estado_prestamo(
            prestamo_info,
            estado_map.get(tipo_notificacion, tipo_notificacion.upper()),
            kwargs.get('usuario_accion', 'Sistema'),
            kwargs.get('observacion', '')
        )


# ============================================================================
# FUNCIÃ“N PARA VERIFICAR DISPONIBILIDAD DEL SERVICIO
# ============================================================================

def servicio_notificaciones_disponible():"""
Servicio unificado de notificaciones por email
VersiÃ³n compatible con entorno virtual envirt
"""
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from database import get_database_connection
import os

logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURACIÃ“N DE EMAIL
# ============================================================================
# ============================================================================
# COLORES Y ESTILOS COMPARTIDOS
# ============================================================================
ESTILOS = {
    'colores': {
        'primario': '#0d6efd',
        'primario_oscuro': '#0a58ca',
        'exito': '#198754',
        'peligro': '#dc3545',
        'advertencia': '#ffc107',
        'info': '#0dcaf0',
        'secundario': '#6c757d',
        'claro': '#f8f9fa',
        'oscuro': '#212529'
    },
    'estados_solicitud': {
        'Pendiente': {'color': '#ffc107', 'icono': 'â³', 'bg': '#fff3cd'},
        'Aprobada': {'color': '#198754', 'icono': 'âœ…', 'bg': '#d1e7dd'},
        'Rechazada': {'color': '#dc3545', 'icono': 'âŒ', 'bg': '#f8d7da'},
        'Entregada Parcial': {'color': '#0dcaf0', 'icono': 'ðŸ“¦', 'bg': '#cff4fc'},
        'Completada': {'color': '#198754', 'icono': 'âœ”ï¸', 'bg': '#d1e7dd'},
        'Devuelta': {'color': '#6c757d', 'icono': 'â†©ï¸', 'bg': '#e9ecef'},
        'Novedad Registrada': {'color': '#fd7e14', 'icono': 'âš ï¸', 'bg': '#ffe5d0'},
        'Novedad Aceptada': {'color': '#198754', 'icono': 'âœ…', 'bg': '#d1e7dd'},
        'Novedad Rechazada': {'color': '#dc3545', 'icono': 'âŒ', 'bg': '#f8d7da'}
    },
    'estados_prestamo': {
        'PRESTADO': {'color': '#ffc107', 'icono': 'ðŸ“‹', 'bg': '#fff3cd'},
        'APROBADO': {'color': '#198754', 'icono': 'âœ…', 'bg': '#d1e7dd'},
        'APROBADO_PARCIAL': {'color': '#0dcaf0', 'icono': 'ðŸ“¦', 'bg': '#cff4fc'},
        'RECHAZADO': {'color': '#dc3545', 'icono': 'âŒ', 'bg': '#f8d7da'},
        'DEVUELTO': {'color': '#6c757d', 'icono': 'â†©ï¸', 'bg': '#e9ecef'}
    }
}


# ============================================================================
# CLASE PRINCIPAL DE NOTIFICACIONES
# ============================================================================
class NotificationService:
    """Servicio unificado para enviar notificaciones por email"""
    
    # ========================================================================
    # MÃ‰TODOS AUXILIARES
    # ========================================================================
    
    @staticmethod
    def _obtener_email_usuario(usuario_id):
        """Obtiene el email de un usuario por su ID"""
        conn = get_database_connection()
        if not conn:
            return None
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT CorreoElectronico FROM Usuarios WHERE UsuarioId = ? AND Activo = 1",
                (usuario_id,)
            )
            row = cursor.fetchone()
            return row[0] if row else None
        except Exception:
            logger.warning(f"No se pudo obtener email del usuario ID: {usuario_id}")
            return None
        finally:
            cursor.close()
            conn.close()
    
    @staticmethod
    def _obtener_emails_aprobadores():
        """Obtiene los emails de todos los aprobadores activos"""
        conn = get_database_connection()
        if not conn:
            return []
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT DISTINCT u.CorreoElectronico 
                FROM Aprobadores a
                INNER JOIN Usuarios u ON a.UsuarioId = u.UsuarioId
                WHERE a.Activo = 1 AND u.Activo = 1 AND u.CorreoElectronico IS NOT NULL
            """)
            return [row[0] for row in cursor.fetchall() if row[0]]
        except Exception:
            logger.warning("Error obteniendo emails de aprobadores")
            return []
        finally:
            cursor.close()
            conn.close()
    
    @staticmethod
    def _obtener_emails_gestores():
        """Obtiene emails de administradores y lÃ­deres de inventario"""
        conn = get_database_connection()
        if not conn:
            return []
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT CorreoElectronico 
                FROM Usuarios 
                WHERE Activo = 1 
                AND CorreoElectronico IS NOT NULL
                AND Rol IN ('administrador', 'lider_inventario', 'Administrador', 'Lider_inventario')
            """)
            return [row[0] for row in cursor.fetchall() if row[0]]
        except Exception:
            logger.warning("Error obteniendo emails de gestores")
            return []
        finally:
            cursor.close()
            conn.close()
    
    @staticmethod
    def _generar_estilos_base():
        """Genera los estilos CSS base para todos los emails"""
        return f'''
            body {{
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                line-height: 1.6;
                color: #333;
                max-width: 600px;
                margin: 0 auto;
                padding: 20px;
                background-color: #f5f5f5;
            }}
            .container {{
                background: white;
                border-radius: 10px;
                overflow: hidden;
                box-shadow: 0 4px 15px rgba(0,0,0,0.1);
            }}
            .header {{
                background: linear-gradient(135deg, {ESTILOS['colores']['primario']} 0%, {ESTILOS['colores']['primario_oscuro']} 100%);
                color: white;
                padding: 30px;
                text-align: center;
            }}
            .header h1 {{
                margin: 0;
                font-size: 24px;
            }}
            .content {{
                padding: 30px;
            }}
            .card {{
                background: {ESTILOS['colores']['claro']};
                border-radius: 10px;
                padding: 20px;
                margin: 20px 0;
                border-left: 4px solid {ESTILOS['colores']['primario']};
            }}
            .detail-row {{
                display: flex;
                justify-content: space-between;
                padding: 10px 0;
                border-bottom: 1px solid #eee;
            }}
            .detail-label {{
                color: #666;
                font-weight: 500;
            }}
            .detail-value {{
                font-weight: bold;
                color: #333;
            }}
            .badge {{
                display: inline-block;
                padding: 5px 15px;
                border-radius: 20px;
                font-weight: bold;
                font-size: 14px;
            }}
            .footer {{
                background: #e9ecef;
                padding: 20px;
                text-align: center;
                font-size: 12px;
                color: #666;
            }}
            .btn {{
                display: inline-block;
                background: {ESTILOS['colores']['primario']};
                color: white;
                padding: 12px 30px;
                text-decoration: none;
                border-radius: 5px;
                margin-top: 20px;
                font-weight: bold;
            }}
        '''
    
    @staticmethod
    def _enviar_email(destinatario_email, asunto, contenido_html, contenido_texto):
        """Envía el email usando SMTP - Soporta SSL (puerto 465) y STARTTLS (puerto 587/25)"""
        if not EMAIL_CONFIG:
            logger.warning("Configuración de email no disponible")
            return False
            
        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = asunto
            msg['From'] = f'{EMAIL_CONFIG["from_name"]} <{EMAIL_CONFIG["from_email"]}>'
            msg['To'] = destinatario_email
            
            part1 = MIMEText(contenido_texto, 'plain', 'utf-8')
            part2 = MIMEText(contenido_html, 'html', 'utf-8')
            msg.attach(part1)
            msg.attach(part2)
            
            smtp_server = EMAIL_CONFIG['smtp_server']
            smtp_port = EMAIL_CONFIG['smtp_port']
            use_tls = EMAIL_CONFIG['use_tls']
            
            logger.info(f"Conectando a SMTP: {sanitizar_ip(smtp_server)}:{smtp_port} (SSL={smtp_port == 465})")
            
            # Puerto 465 usa SSL implícito (SMTPS)
            # Puertos 25, 587 usan STARTTLS
            if smtp_port == 465:
                # SSL implícito - usar SMTP_SSL
                server = smtplib.SMTP_SSL(smtp_server, smtp_port, timeout=30)
                logger.info("Usando SMTP_SSL (SSL implícito)")
            else:
                # STARTTLS - usar SMTP normal y luego starttls()
                server = smtplib.SMTP(smtp_server, smtp_port, timeout=30)
                server.ehlo()
                if use_tls:
                    server.starttls()
                    server.ehlo()
                    logger.info("Usando STARTTLS")
            
            # Autenticación si está configurada
            if EMAIL_CONFIG.get('smtp_user') and EMAIL_CONFIG.get('smtp_password'):
                server.login(EMAIL_CONFIG['smtp_user'], EMAIL_CONFIG['smtp_password'])
                logger.info("Autenticación SMTP completada")
            
            server.sendmail(EMAIL_CONFIG['from_email'], destinatario_email, msg.as_string())
            server.quit()
            
            logger.info("✅ Email enviado exitosamente")
            return True
            
        except smtplib.SMTPAuthenticationError as e:
            logger.error(f"Error de autenticación SMTP: {e}")
            return False
        except smtplib.SMTPConnectError as e:
            logger.error(f"Error de conexión SMTP: {e}")
            return False
        except smtplib.SMTPException as e:
            logger.error(f"Error SMTP: {e}")
            return False
        except Exception as e:
            logger.warning(f"Error enviando email: {e}")
            import traceback
            logger.debug(f"Traceback: {traceback.format_exc()}")
            return False

    # ========================================================================
    # NOTIFICACIONES - INVENTARIO CORPORATIVO
    # ========================================================================
    
    @staticmethod
    def enviar_notificacion_asignacion(destinatario_email, destinatario_nombre, 
                                        producto_info, cantidad, oficina_nombre,
                                        asignador_nombre):
        """EnvÃ­a notificaciÃ³n de asignaciÃ³n de producto del inventario corporativo"""
        fecha_actual = datetime.now().strftime('%d/%m/%Y %H:%M')
        
        asunto = f'ðŸ“¦ AsignaciÃ³n de Inventario - {producto_info.get("nombre", "Producto")}'
        
        html = f'''
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>{NotificationService._generar_estilos_base()}</style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>ðŸ“¦ Nueva AsignaciÃ³n de Inventario</h1>
                </div>
                <div class="content">
                    <p>Hola <strong>{destinatario_nombre}</strong>,</p>
                    <p>Se te ha asignado el siguiente elemento del inventario corporativo:</p>
                    
                    <div class="card">
                        <h3 style="color: {ESTILOS['colores']['primario']}; margin-top: 0;">
                            {producto_info.get('nombre', 'Producto')}
                        </h3>
                        <div class="detail-row">
                            <span class="detail-label">CÃ³digo:</span>
                            <span class="detail-value">{producto_info.get('codigo_unico', 'N/A')}</span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-label">CategorÃ­a:</span>
                            <span class="detail-value">{producto_info.get('categoria', 'N/A')}</span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-label">Cantidad Asignada:</span>
                            <span class="badge" style="background: {ESTILOS['colores']['exito']}; color: white;">
                                {cantidad} unidad(es)
                            </span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-label">Oficina Destino:</span>
                            <span class="detail-value">{oficina_nombre}</span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-label">Asignado por:</span>
                            <span class="detail-value">{asignador_nombre}</span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-label">Fecha:</span>
                            <span class="detail-value">{fecha_actual}</span>
                        </div>
                    </div>
                    
                    <p style="color: #666;">
                        Por favor, confirma la recepciÃ³n de este elemento con el Ã¡rea de inventario.
                    </p>
                </div>
                <div class="footer">
                    <p>Este es un mensaje automÃ¡tico del Sistema de GestiÃ³n de Inventarios.</p>
                    <p>Qualitas Colombia - {datetime.now().year}</p>
                </div>
            </div>
        </body>
        </html>
        '''
        
        texto = f'''
NUEVA ASIGNACIÃ“N DE INVENTARIO CORPORATIVO
==========================================

Hola {destinatario_nombre},

Se te ha asignado: {producto_info.get('nombre', 'Producto')}
CÃ³digo: {producto_info.get('codigo_unico', 'N/A')}
Cantidad: {cantidad} unidad(es)
Oficina: {oficina_nombre}
Asignado por: {asignador_nombre}
Fecha: {fecha_actual}

---
Sistema de GestiÃ³n de Inventarios - Qualitas Colombia
        '''
        
        return NotificationService._enviar_email(destinatario_email, asunto, html, texto)
    
    @staticmethod
    def enviar_notificacion_asignacion_con_confirmacion(destinatario_email, destinatario_nombre, 
                                                        producto_info, cantidad, oficina_nombre,
                                                        asignador_nombre, token_confirmacion=None,
                                                        base_url='http://localhost:5000'):
        """
        EnvÃ­a notificaciÃ³n de asignaciÃ³n de producto con link de confirmaciÃ³n.
        """
        fecha_actual = datetime.now().strftime('%d/%m/%Y %H:%M')
        
        # Generar link de confirmaciÃ³n si hay token
        link_confirmacion = None
        if token_confirmacion:
            link_confirmacion = f"{base_url}/confirmacion/confirmar-asignacion/{token_confirmacion}"
        
        asunto = f'ðŸ“¦ AsignaciÃ³n de Inventario - {producto_info.get("nombre", "Producto")}'
        
        # Construir el bloque de confirmaciÃ³n por separado
        bloque_confirmacion = ''
        if token_confirmacion and link_confirmacion:
            bloque_confirmacion = f'''
                    <div class="card" style="background: #fff3cd; border-left-color: #ffc107;">
                        <h4 style="color: #856404; margin-top: 0;">âš ï¸ ACCIÃ“N REQUERIDA</h4>
                        <p style="color: #856404; margin-bottom: 15px;">
                            Debe confirmar la recepciÃ³n de este elemento dentro de los prÃ³ximos <strong>8 dÃ­as</strong>.
                        </p>
                        <center>
                            <a href="{link_confirmacion}" class="btn" style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);">
                                âœ… CONFIRMAR RECEPCIÃ“N
                            </a>
                        </center>
                        <p style="font-size: 12px; color: #666; margin-top: 15px; margin-bottom: 0;">
                            Si el botÃ³n no funciona, copie y pegue este enlace en su navegador:<br>
                            <a href="{link_confirmacion}" style="word-break: break-all;">{link_confirmacion}</a>
                        </p>
                    </div>
            '''
        else:
            bloque_confirmacion = '<p style="color: #666;">Por favor, confirma la recepciÃ³n de este elemento con el Ã¡rea de inventario.</p>'
        
        html = f'''
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>{NotificationService._generar_estilos_base()}</style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>ðŸ“¦ Nueva AsignaciÃ³n de Inventario</h1>
                </div>
                <div class="content">
                    <p>Hola <strong>{destinatario_nombre}</strong>,</p>
                    <p>Se te ha asignado el siguiente elemento del inventario corporativo:</p>
                    
                    <div class="card">
                        <h3 style="color: {ESTILOS['colores']['primario']}; margin-top: 0;">
                            {producto_info.get('nombre', 'Producto')}
                        </h3>
                        <div class="detail-row">
                            <span class="detail-label">CÃ³digo:</span>
                            <span class="detail-value">{producto_info.get('codigo_unico', 'N/A')}</span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-label">CategorÃ­a:</span>
                            <span class="detail-value">{producto_info.get('categoria', 'N/A')}</span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-label">Cantidad Asignada:</span>
                            <span class="badge" style="background: {ESTILOS['colores']['exito']}; color: white;">
                                {cantidad} unidad(es)
                            </span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-label">Oficina Destino:</span>
                            <span class="detail-value">{oficina_nombre}</span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-label">Asignado por:</span>
                            <span class="detail-value">{asignador_nombre}</span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-label">Fecha:</span>
                            <span class="detail-value">{fecha_actual}</span>
                        </div>
                    </div>
                    
                    {bloque_confirmacion}
                    
                    <p style="color: #666; font-size: 14px; margin-top: 20px;">
                        Si tiene alguna pregunta o problema con esta asignaciÃ³n, 
                        por favor contacte al departamento de inventario.
                    </p>
                </div>
                <div class="footer">
                    <p>Este es un mensaje automÃ¡tico del Sistema de GestiÃ³n de Inventarios.</p>
                    <p>Qualitas Colombia - {datetime.now().year}</p>
                </div>
            </div>
        </body>
        </html>
        '''
        
        texto_confirmacion = ''
        if token_confirmacion and link_confirmacion:
            texto_confirmacion = f'''
IMPORTANTE: Debe confirmar la recepciÃ³n dentro de los prÃ³ximos 8 dÃ­as.
Link de confirmaciÃ³n: {link_confirmacion}
'''
        
        texto = f'''
NUEVA ASIGNACIÃ“N DE INVENTARIO CORPORATIVO
==========================================

Hola {destinatario_nombre},

Se te ha asignado: {producto_info.get('nombre', 'Producto')}
CÃ³digo: {producto_info.get('codigo_unico', 'N/A')}
Cantidad: {cantidad} unidad(es)
Oficina: {oficina_nombre}
Asignado por: {asignador_nombre}
Fecha: {fecha_actual}

{texto_confirmacion}
---
Sistema de GestiÃ³n de Inventarios - Qualitas Colombia
        '''
        
        return NotificationService._enviar_email(destinatario_email, asunto, html, texto)
    
    @staticmethod
    def enviar_notificacion_confirmacion_asignacion(asignacion_id, producto_nombre, 
                                                     usuario_nombre, usuario_email):
        """
        EnvÃ­a notificaciÃ³n a los gestores cuando el usuario confirma la recepciÃ³n.
        """
        emails_gestores = NotificationService._obtener_emails_gestores()
        
        if not emails_gestores:
            logger.warning("No hay gestores configurados para notificar confirmaciÃ³n")
            return False
        
        fecha_actual = datetime.now().strftime('%d/%m/%Y %H:%M')
        
        asunto = f"âœ… ConfirmaciÃ³n de RecepciÃ³n: {producto_nombre}"
        
        html = f'''
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>{NotificationService._generar_estilos_base()}</style>
        </head>
        <body>
            <div class="container">
                <div class="header" style="background: linear-gradient(135deg, {ESTILOS['colores']['exito']} 0%, #146c43 100%);">
                    <h1>âœ… RecepciÃ³n Confirmada</h1>
                </div>
                <div class="content">
                    <p>Se ha confirmado la recepciÃ³n del siguiente producto:</p>
                    
                    <div class="card" style="border-left-color: {ESTILOS['colores']['exito']};">
                        <div class="detail-row">
                            <span class="detail-label">Producto:</span>
                            <span class="detail-value">{producto_nombre}</span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-label">Usuario:</span>
                            <span class="detail-value">{usuario_nombre}</span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-label">Email:</span>
                            <span class="detail-value">{usuario_email}</span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-label">ID AsignaciÃ³n:</span>
                            <span class="detail-value">#{asignacion_id}</span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-label">Fecha de confirmaciÃ³n:</span>
                            <span class="badge" style="background: {ESTILOS['colores']['exito']}; color: white;">
                                {fecha_actual}
                            </span>
                        </div>
                    </div>
                    
                    <p style="color: #666;">
                        El usuario ha confirmado exitosamente la recepciÃ³n del elemento asignado.
                    </p>
                </div>
                <div class="footer">
                    <p>Sistema de GestiÃ³n de Inventarios - Qualitas Colombia</p>
                </div>
            </div>
        </body>
        </html>
        '''
        
        texto = f'''
CONFIRMACIÃ“N DE RECEPCIÃ“N
=========================

Producto: {producto_nombre}
Usuario: {usuario_nombre}
Email: {usuario_email}
ID AsignaciÃ³n: #{asignacion_id}
Fecha de confirmaciÃ³n: {fecha_actual}

El usuario ha confirmado exitosamente la recepciÃ³n del elemento.

---
Sistema de GestiÃ³n de Inventarios - Qualitas Colombia
        '''
        
        exitos = 0
        for email in emails_gestores:
            if NotificationService._enviar_email(email, asunto, html, texto):
                exitos += 1
        
        return exitos > 0

    # ========================================================================
    # NOTIFICACIONES - MATERIAL POP (SOLICITUDES)
    # ========================================================================
    
    @staticmethod
    def notificar_solicitud_creada(solicitud_info):
        """Notifica a los aprobadores cuando se crea una nueva solicitud"""
        emails_aprobadores = NotificationService._obtener_emails_aprobadores()
        
        if not emails_aprobadores:
            logger.warning("No hay aprobadores configurados para notificar")
            return False
        
        fecha_actual = datetime.now().strftime('%d/%m/%Y %H:%M')
        estado_config = ESTILOS['estados_solicitud'].get('Pendiente', {})
        
        asunto = f'ðŸ“‹ Nueva Solicitud de Material - {solicitud_info.get("material_nombre", "Material")}'
        
        html = f'''
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>{NotificationService._generar_estilos_base()}</style>
        </head>
        <body>
            <div class="container">
                <div class="header" style="background: linear-gradient(135deg, {estado_config.get('color', '#ffc107')} 0%, #e0a800 100%);">
                    <h1>ðŸ“‹ Nueva Solicitud de Material</h1>
                </div>
                <div class="content">
                    <p>Se ha creado una nueva solicitud que requiere su aprobaciÃ³n:</p>
                    
                    <div class="card" style="border-left-color: {estado_config.get('color', '#ffc107')};">
                        <div class="detail-row">
                            <span class="detail-label">Material:</span>
                            <span class="detail-value">{solicitud_info.get('material_nombre', 'N/A')}</span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-label">Cantidad Solicitada:</span>
                            <span class="badge" style="background: {ESTILOS['colores']['primario']}; color: white;">
                                {solicitud_info.get('cantidad_solicitada', 0)} unidades
                            </span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-label">Oficina Solicitante:</span>
                            <span class="detail-value">{solicitud_info.get('oficina_nombre', 'N/A')}</span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-label">Solicitante:</span>
                            <span class="detail-value">{solicitud_info.get('usuario_solicitante', 'N/A')}</span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-label">Estado:</span>
                            <span class="badge" style="background: {estado_config.get('bg', '#fff3cd')}; color: {estado_config.get('color', '#856404')};">
                                â³ Pendiente de AprobaciÃ³n
                            </span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-label">Fecha:</span>
                            <span class="detail-value">{fecha_actual}</span>
                        </div>
                    </div>
                    
                    <p style="color: #666;">
                        Por favor, revise y procese esta solicitud a la brevedad.
                    </p>
                </div>
                <div class="footer">
                    <p>Sistema de GestiÃ³n de Inventarios - Qualitas Colombia</p>
                </div>
            </div>
        </body>
        </html>
        '''
        
        texto = f'''
NUEVA SOLICITUD DE MATERIAL
===========================

Material: {solicitud_info.get('material_nombre', 'N/A')}
Cantidad: {solicitud_info.get('cantidad_solicitada', 0)} unidades
Oficina: {solicitud_info.get('oficina_nombre', 'N/A')}
Solicitante: {solicitud_info.get('usuario_solicitante', 'N/A')}
Estado: Pendiente de AprobaciÃ³n
Fecha: {fecha_actual}

---
Sistema de GestiÃ³n de Inventarios - Qualitas Colombia
        '''
        
        exitos = 0
        for email in emails_aprobadores:
            if NotificationService._enviar_email(email, asunto, html, texto):
                exitos += 1
        
        return exitos > 0

    @staticmethod
    def notificar_cambio_estado_solicitud(solicitud_info, estado_anterior, estado_nuevo, 
                                           usuario_accion, observacion=''):
        """Notifica al solicitante cuando cambia el estado de su solicitud"""
        
        email_destino = solicitud_info.get('email_solicitante')
        
        if not email_destino:
            logger.warning(f"No se encontrÃ³ email para notificar solicitud {solicitud_info.get('id')}")
            return False
        
        fecha_actual = datetime.now().strftime('%d/%m/%Y %H:%M')
        estado_config = ESTILOS['estados_solicitud'].get(estado_nuevo, {})
        
        asunto = f'{estado_config.get("icono", "ðŸ“‹")} Solicitud {estado_nuevo} - {solicitud_info.get("material_nombre", "Material")}'
        
        observacion_html = f'<div class="detail-row"><span class="detail-label">ObservaciÃ³n:</span><span class="detail-value">{observacion}</span></div>' if observacion else ''
        
        html = f'''
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>{NotificationService._generar_estilos_base()}</style>
        </head>
        <body>
            <div class="container">
                <div class="header" style="background: linear-gradient(135deg, {estado_config.get('color', ESTILOS['colores']['primario'])} 0%, {ESTILOS['colores']['primario_oscuro']} 100%);">
                    <h1>{estado_config.get('icono', 'ðŸ“‹')} Solicitud {estado_nuevo}</h1>
                </div>
                <div class="content">
                    <p>Hola <strong>{solicitud_info.get('usuario_solicitante', '')}</strong>,</p>
                    <p>Tu solicitud de material ha cambiado de estado:</p>
                    
                    <div class="card" style="border-left-color: {estado_config.get('color', ESTILOS['colores']['primario'])};">
                        <div class="detail-row">
                            <span class="detail-label">Material:</span>
                            <span class="detail-value">{solicitud_info.get('material_nombre', 'N/A')}</span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-label">Cantidad:</span>
                            <span class="detail-value">{solicitud_info.get('cantidad_solicitada', 0)} unidades</span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-label">Estado Anterior:</span>
                            <span class="detail-value">{estado_anterior}</span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-label">Nuevo Estado:</span>
                            <span class="badge" style="background: {estado_config.get('bg', '#e9ecef')}; color: {estado_config.get('color', '#333')};">
                                {estado_config.get('icono', '')} {estado_nuevo}
                            </span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-label">Procesado por:</span>
                            <span class="detail-value">{usuario_accion}</span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-label">Fecha:</span>
                            <span class="detail-value">{fecha_actual}</span>
                        </div>
                        {observacion_html}
                    </div>
                </div>
                <div class="footer">
                    <p>Sistema de GestiÃ³n de Inventarios - Qualitas Colombia</p>
                </div>
            </div>
        </body>
        </html>
        '''
        
        texto_observacion = f'\nObservaciÃ³n: {observacion}' if observacion else ''
        
        texto = f'''
ACTUALIZACIÃ“N DE SOLICITUD
==========================

Material: {solicitud_info.get('material_nombre', 'N/A')}
Cantidad: {solicitud_info.get('cantidad_solicitada', 0)} unidades
Estado Anterior: {estado_anterior}
Nuevo Estado: {estado_nuevo}
Procesado por: {usuario_accion}
Fecha: {fecha_actual}{texto_observacion}

---
Sistema de GestiÃ³n de Inventarios - Qualitas Colombia
        '''
        
        return NotificationService._enviar_email(email_destino, asunto, html, texto)

    @staticmethod
    def notificar_novedad_registrada(solicitud_info, novedad_info):
        """Notifica a los gestores cuando se registra una novedad"""
        emails_gestores = NotificationService._obtener_emails_gestores()
        
        if not emails_gestores:
            return False
        
        fecha_actual = datetime.now().strftime('%d/%m/%Y %H:%M')
        
        asunto = f'âš ï¸ Nueva Novedad Registrada - Solicitud #{solicitud_info.get("id", "N/A")}'
        
        html = f'''
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>{NotificationService._generar_estilos_base()}</style>
        </head>
        <body>
            <div class="container">
                <div class="header" style="background: linear-gradient(135deg, #fd7e14 0%, #e65c00 100%);">
                    <h1>âš ï¸ Nueva Novedad Registrada</h1>
                </div>
                <div class="content">
                    <p>Se ha registrado una novedad que requiere su atenciÃ³n:</p>
                    
                    <div class="card" style="border-left-color: #fd7e14;">
                        <div class="detail-row">
                            <span class="detail-label">Solicitud #:</span>
                            <span class="detail-value">{solicitud_info.get('id', 'N/A')}</span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-label">Material:</span>
                            <span class="detail-value">{solicitud_info.get('material_nombre', 'N/A')}</span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-label">Tipo de Novedad:</span>
                            <span class="badge" style="background: #ffe5d0; color: #fd7e14;">
                                {novedad_info.get('tipo', 'N/A')}
                            </span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-label">DescripciÃ³n:</span>
                            <span class="detail-value">{novedad_info.get('descripcion', 'N/A')}</span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-label">Cantidad Afectada:</span>
                            <span class="detail-value">{novedad_info.get('cantidad_afectada', 0)}</span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-label">Registrado por:</span>
                            <span class="detail-value">{novedad_info.get('usuario_registra', 'N/A')}</span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-label">Fecha:</span>
                            <span class="detail-value">{fecha_actual}</span>
                        </div>
                    </div>
                    
                    <p style="color: #666;">
                        Por favor, revise y gestione esta novedad.
                    </p>
                </div>
                <div class="footer">
                    <p>Sistema de GestiÃ³n de Inventarios - Qualitas Colombia</p>
                </div>
            </div>
        </body>
        </html>
        '''
        
        texto = f'''
NUEVA NOVEDAD REGISTRADA
========================

Solicitud #: {solicitud_info.get('id', 'N/A')}
Material: {solicitud_info.get('material_nombre', 'N/A')}
Tipo: {novedad_info.get('tipo', 'N/A')}
DescripciÃ³n: {novedad_info.get('descripcion', 'N/A')}
Cantidad Afectada: {novedad_info.get('cantidad_afectada', 0)}
Registrado por: {novedad_info.get('usuario_registra', 'N/A')}

---
Sistema de GestiÃ³n de Inventarios - Qualitas Colombia
        '''
        
        exitos = 0
        for email in emails_gestores:
            if NotificationService._enviar_email(email, asunto, html, texto):
                exitos += 1
        
        return exitos > 0

    # ========================================================================
    # NOTIFICACIONES - PRÃ‰STAMOS
    # ========================================================================
    
    @staticmethod
    def notificar_prestamo_creado(prestamo_info):
        """Notifica a los gestores cuando se crea un nuevo prÃ©stamo"""
        emails_gestores = NotificationService._obtener_emails_gestores()
        
        if not emails_gestores:
            return False
        
        fecha_actual = datetime.now().strftime('%d/%m/%Y %H:%M')
        estado_config = ESTILOS['estados_prestamo'].get('PRESTADO', {})
        
        asunto = f'ðŸ“‹ Nuevo PrÃ©stamo Solicitado - {prestamo_info.get("material", "Material")}'
        
        html = f'''
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>{NotificationService._generar_estilos_base()}</style>
        </head>
        <body>
            <div class="container">
                <div class="header" style="background: linear-gradient(135deg, {estado_config.get('color', '#ffc107')} 0%, #e0a800 100%);">
                    <h1>ðŸ“‹ Nuevo PrÃ©stamo Solicitado</h1>
                </div>
                <div class="content">
                    <p>Se ha registrado un nuevo prÃ©stamo que requiere aprobaciÃ³n:</p>
                    
                    <div class="card" style="border-left-color: {estado_config.get('color', '#ffc107')};">
                        <div class="detail-row">
                            <span class="detail-label">Elemento:</span>
                            <span class="detail-value">{prestamo_info.get('material', 'N/A')}</span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-label">Cantidad:</span>
                            <span class="badge" style="background: {ESTILOS['colores']['primario']}; color: white;">
                                {prestamo_info.get('cantidad', 0)} unidades
                            </span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-label">Solicitante:</span>
                            <span class="detail-value">{prestamo_info.get('solicitante_nombre', 'N/A')}</span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-label">Oficina:</span>
                            <span class="detail-value">{prestamo_info.get('oficina_nombre', 'N/A')}</span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-label">Evento:</span>
                            <span class="detail-value">{prestamo_info.get('evento', 'N/A')}</span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-label">Fecha DevoluciÃ³n Prevista:</span>
                            <span class="detail-value">{prestamo_info.get('fecha_prevista', 'N/A')}</span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-label">Estado:</span>
                            <span class="badge" style="background: {estado_config.get('bg', '#fff3cd')}; color: {estado_config.get('color', '#856404')};">
                                ðŸ“‹ Pendiente de AprobaciÃ³n
                            </span>
                        </div>
                    </div>
                </div>
                <div class="footer">
                    <p>Sistema de GestiÃ³n de Inventarios - Qualitas Colombia</p>
                </div>
            </div>
        </body>
        </html>
        '''
        
        texto = f'''
NUEVO PRÃ‰STAMO SOLICITADO
=========================

Elemento: {prestamo_info.get('material', 'N/A')}
Cantidad: {prestamo_info.get('cantidad', 0)} unidades
Solicitante: {prestamo_info.get('solicitante_nombre', 'N/A')}
Oficina: {prestamo_info.get('oficina_nombre', 'N/A')}
Evento: {prestamo_info.get('evento', 'N/A')}
Fecha DevoluciÃ³n Prevista: {prestamo_info.get('fecha_prevista', 'N/A')}

---
Sistema de GestiÃ³n de Inventarios - Qualitas Colombia
        '''
        
        exitos = 0
        for email in emails_gestores:
            if NotificationService._enviar_email(email, asunto, html, texto):
                exitos += 1
        
        return exitos > 0

    @staticmethod
    def notificar_cambio_estado_prestamo(prestamo_info, estado_nuevo, usuario_accion, observacion=''):
        """Notifica al solicitante cuando cambia el estado de su prÃ©stamo"""
        
        email_destino = prestamo_info.get('email_solicitante')
        
        if not email_destino:
            logger.warning(f"No se encontrÃ³ email para notificar prÃ©stamo {prestamo_info.get('id')}")
            return False
        
        fecha_actual = datetime.now().strftime('%d/%m/%Y %H:%M')
        estado_config = ESTILOS['estados_prestamo'].get(estado_nuevo, {})
        
        asunto = f'{estado_config.get("icono", "ðŸ“‹")} PrÃ©stamo {estado_nuevo} - {prestamo_info.get("material", "Material")}'
        
        observacion_html = f'<div class="detail-row"><span class="detail-label">ObservaciÃ³n:</span><span class="detail-value">{observacion}</span></div>' if observacion else ''
        
        html = f'''
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>{NotificationService._generar_estilos_base()}</style>
        </head>
        <body>
            <div class="container">
                <div class="header" style="background: linear-gradient(135deg, {estado_config.get('color', ESTILOS['colores']['primario'])} 0%, {ESTILOS['colores']['primario_oscuro']} 100%);">
                    <h1>{estado_config.get('icono', 'ðŸ“‹')} PrÃ©stamo {estado_nuevo}</h1>
                </div>
                <div class="content">
                    <p>Hola <strong>{prestamo_info.get('solicitante_nombre', '')}</strong>,</p>
                    <p>Tu prÃ©stamo ha sido actualizado:</p>
                    
                    <div class="card" style="border-left-color: {estado_config.get('color', ESTILOS['colores']['primario'])};">
                        <div class="detail-row">
                            <span class="detail-label">Elemento:</span>
                            <span class="detail-value">{prestamo_info.get('material', 'N/A')}</span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-label">Cantidad:</span>
                            <span class="detail-value">{prestamo_info.get('cantidad', 0)} unidades</span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-label">Nuevo Estado:</span>
                            <span class="badge" style="background: {estado_config.get('bg', '#e9ecef')}; color: {estado_config.get('color', '#333')};">
                                {estado_config.get('icono', '')} {estado_nuevo}
                            </span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-label">Procesado por:</span>
                            <span class="detail-value">{usuario_accion}</span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-label">Fecha:</span>
                            <span class="detail-value">{fecha_actual}</span>
                        </div>
                        {observacion_html}
                    </div>
                </div>
                <div class="footer">
                    <p>Sistema de GestiÃ³n de Inventarios - Qualitas Colombia</p>
                </div>
            </div>
        </body>
        </html>
        '''
        
        texto_observacion = f'\nObservaciÃ³n: {observacion}' if observacion else ''
        
        texto = f'''
ACTUALIZACIÃ“N DE PRÃ‰STAMO
=========================

Elemento: {prestamo_info.get('material', 'N/A')}
Cantidad: {prestamo_info.get('cantidad', 0)} unidades
Nuevo Estado: {estado_nuevo}
Procesado por: {usuario_accion}
Fecha: {fecha_actual}{texto_observacion}

---
Sistema de GestiÃ³n de Inventarios - Qualitas Colombia
        '''
        
        return NotificationService._enviar_email(email_destino, asunto, html, texto)


# ============================================================================
# FUNCIONES DE CONVENIENCIA
# ============================================================================

def notificar_asignacion_inventario(destinatario_email, destinatario_nombre, 
                                     producto_info, cantidad, oficina_nombre, asignador_nombre):
    """Wrapper para compatibilidad con cÃ³digo existente"""
    return NotificationService.enviar_notificacion_asignacion(
        destinatario_email, destinatario_nombre, producto_info, 
        cantidad, oficina_nombre, asignador_nombre
    )

def notificar_solicitud(solicitud_info, tipo_notificacion, **kwargs):
    """
    FunciÃ³n genÃ©rica para notificar sobre solicitudes
    """
    if tipo_notificacion == 'creada':
        return NotificationService.notificar_solicitud_creada(solicitud_info)
    elif tipo_notificacion in ['aprobada', 'rechazada', 'entregada', 'devuelta']:
        return NotificationService.notificar_cambio_estado_solicitud(
            solicitud_info, 
            kwargs.get('estado_anterior', 'Pendiente'),
            tipo_notificacion.capitalize(),
            kwargs.get('usuario_accion', 'Sistema'),
            kwargs.get('observacion', '')
        )
    elif tipo_notificacion == 'novedad':
        return NotificationService.notificar_novedad_registrada(
            solicitud_info, 
            kwargs.get('novedad_info', {})
        )
    return False

def notificar_prestamo(prestamo_info, tipo_notificacion, **kwargs):
    """
    FunciÃ³n genÃ©rica para notificar sobre prÃ©stamos
    """
    if tipo_notificacion == 'creado':
        return NotificationService.notificar_prestamo_creado(prestamo_info)
    else:
        estado_map = {
            'aprobado': 'APROBADO',
            'aprobado_parcial': 'APROBADO_PARCIAL',
            'rechazado': 'RECHAZADO',
            'devuelto': 'DEVUELTO'
        }
        return NotificationService.notificar_cambio_estado_prestamo(
            prestamo_info,
            estado_map.get(tipo_notificacion, tipo_notificacion.upper()),
            kwargs.get('usuario_accion', 'Sistema'),
            kwargs.get('observacion', '')
        )

def servicio_notificaciones_disponible():
    """Verifica si el servicio de notificaciones estÃ¡ disponible"""
    if not EMAIL_CONFIG:
        logger.warning("âš ï¸ Servicio de notificaciones no disponible: ConfiguraciÃ³n faltante")
        return False
    
    if not EMAIL_CONFIG.get('smtp_server'):
        logger.warning("âš ï¸ Servicio de notificaciones no disponible: SMTP_SERVER no configurado")
        return False
    
    if not EMAIL_CONFIG.get('from_email'):
        logger.warning("âš ï¸ Servicio de notificaciones no disponible: SMTP_FROM_EMAIL no configurado")
        return False
    
    logger.info("[OK] Servicio de notificaciones disponible")
    return True
    """
    Verifica si el servicio de notificaciones estÃ¡ disponible
    """
    if EMAIL_CONFIG is None:
        logger.warning("âš ï¸ Servicio de notificaciones no disponible: ConfiguraciÃ³n faltante")
        return False
    
    # Verificar configuraciÃ³n mÃ­nima
    if not EMAIL_CONFIG.get('smtp_server'):
        logger.warning("âš ï¸ Servicio de notificaciones no disponible: SMTP_SERVER no configurado")
        return False
    
    if not EMAIL_CONFIG.get('from_email'):
        logger.warning("âš ï¸ Servicio de notificaciones no disponible: SMTP_FROM_EMAIL no configurado")
        return False
    
    return True