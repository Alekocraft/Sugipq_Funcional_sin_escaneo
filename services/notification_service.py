# services/notification_service.py
"""
Servicio unificado de notificaciones por email para:
- Inventario Corporativo (asignaciones)
- Material POP (solicitudes y novedades)
- Préstamos
"""
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from database import get_database_connection

logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURACIÓN DE EMAIL
# ============================================================================
EMAIL_CONFIG = {
    'smtp_server': '10.60.0.30',   
    'smtp_port': 25,   
    'use_tls': False,
    'smtp_user': 'lramirez@qualitascolombia.com.co',   
    'smtp_password': 'Metallica1022963*',
    'from_email': 'lramirez@qualitascolombia.com.co',
    'from_name': 'Sistema de Gestión de Inventarios'
}

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
        'Pendiente': {'color': '#ffc107', 'icono': '⏳', 'bg': '#fff3cd'},
        'Aprobada': {'color': '#198754', 'icono': '✅', 'bg': '#d1e7dd'},
        'Rechazada': {'color': '#dc3545', 'icono': '❌', 'bg': '#f8d7da'},
        'Entregada Parcial': {'color': '#0dcaf0', 'icono': '📦', 'bg': '#cff4fc'},
        'Completada': {'color': '#198754', 'icono': '✔️', 'bg': '#d1e7dd'},
        'Devuelta': {'color': '#6c757d', 'icono': '↩️', 'bg': '#e9ecef'},
        'Novedad Registrada': {'color': '#fd7e14', 'icono': '⚠️', 'bg': '#ffe5d0'},
        'Novedad Aceptada': {'color': '#198754', 'icono': '✅', 'bg': '#d1e7dd'},
        'Novedad Rechazada': {'color': '#dc3545', 'icono': '❌', 'bg': '#f8d7da'}
    },
    'estados_prestamo': {
        'PRESTADO': {'color': '#ffc107', 'icono': '📋', 'bg': '#fff3cd'},
        'APROBADO': {'color': '#198754', 'icono': '✅', 'bg': '#d1e7dd'},
        'APROBADO_PARCIAL': {'color': '#0dcaf0', 'icono': '📦', 'bg': '#cff4fc'},
        'RECHAZADO': {'color': '#dc3545', 'icono': '❌', 'bg': '#f8d7da'},
        'DEVUELTO': {'color': '#6c757d', 'icono': '↩️', 'bg': '#e9ecef'}
    }
}


# ============================================================================
# CLASE PRINCIPAL DE NOTIFICACIONES
# ============================================================================
class NotificationService:
    """Servicio unificado para enviar notificaciones por email"""
    
    # ========================================================================
    # MÉTODOS AUXILIARES
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
        except Exception as e:
            logger.error(f"Error obteniendo email de usuario {usuario_id}: {e}")
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
        except Exception as e:
            logger.error(f"Error obteniendo emails de aprobadores: {e}")
            return []
        finally:
            cursor.close()
            conn.close()
    
    @staticmethod
    def _obtener_emails_gestores():
        """Obtiene emails de administradores y líderes de inventario"""
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
        except Exception as e:
            logger.error(f"Error obteniendo emails de gestores: {e}")
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
        """Envía el email usando SMTP"""
        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = asunto
            msg['From'] = f'{EMAIL_CONFIG["from_name"]} <{EMAIL_CONFIG["from_email"]}>'
            msg['To'] = destinatario_email
            
            part1 = MIMEText(contenido_texto, 'plain', 'utf-8')
            part2 = MIMEText(contenido_html, 'html', 'utf-8')
            msg.attach(part1)
            msg.attach(part2)
            
            server = smtplib.SMTP(EMAIL_CONFIG['smtp_server'], EMAIL_CONFIG['smtp_port'], timeout=30)
            
            if EMAIL_CONFIG['use_tls']:
                server.starttls()
            
            if EMAIL_CONFIG['smtp_user'] and EMAIL_CONFIG['smtp_password']:
                server.login(EMAIL_CONFIG['smtp_user'], EMAIL_CONFIG['smtp_password'])
            
            server.sendmail(EMAIL_CONFIG['from_email'], destinatario_email, msg.as_string())
            server.quit()
            
            logger.info(f"✅ Email enviado exitosamente a {destinatario_email}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error enviando email: {e}")
            return False

    # ========================================================================
    # NOTIFICACIONES - INVENTARIO CORPORATIVO
    # ========================================================================
    
    @staticmethod
    def enviar_notificacion_asignacion(destinatario_email, destinatario_nombre, 
                                        producto_info, cantidad, oficina_nombre,
                                        asignador_nombre):
        """Envía notificación de asignación de producto del inventario corporativo"""
        fecha_actual = datetime.now().strftime('%d/%m/%Y %H:%M')
        
        asunto = f'📦 Asignación de Inventario - {producto_info.get("nombre", "Producto")}'
        
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
                    <h1>📦 Nueva Asignación de Inventario</h1>
                </div>
                <div class="content">
                    <p>Hola <strong>{destinatario_nombre}</strong>,</p>
                    <p>Se te ha asignado el siguiente elemento del inventario corporativo:</p>
                    
                    <div class="card">
                        <h3 style="color: {ESTILOS['colores']['primario']}; margin-top: 0;">
                            {producto_info.get('nombre', 'Producto')}
                        </h3>
                        <div class="detail-row">
                            <span class="detail-label">Código:</span>
                            <span class="detail-value">{producto_info.get('codigo_unico', 'N/A')}</span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-label">Categoría:</span>
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
                        Por favor, confirma la recepción de este elemento con el área de inventario.
                    </p>
                </div>
                <div class="footer">
                    <p>Este es un mensaje automático del Sistema de Gestión de Inventarios.</p>
                    <p>Qualitas Colombia - {datetime.now().year}</p>
                </div>
            </div>
        </body>
        </html>
        '''
        
        texto = f'''
NUEVA ASIGNACIÓN DE INVENTARIO CORPORATIVO
==========================================

Hola {destinatario_nombre},

Se te ha asignado: {producto_info.get('nombre', 'Producto')}
Código: {producto_info.get('codigo_unico', 'N/A')}
Cantidad: {cantidad} unidad(es)
Oficina: {oficina_nombre}
Asignado por: {asignador_nombre}
Fecha: {fecha_actual}

---
Sistema de Gestión de Inventarios - Qualitas Colombia
        '''
        
        return NotificationService._enviar_email(destinatario_email, asunto, html, texto)

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
        
        asunto = f'📋 Nueva Solicitud de Material - {solicitud_info.get("material_nombre", "Material")}'
        
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
                    <h1>📋 Nueva Solicitud de Material</h1>
                </div>
                <div class="content">
                    <p>Se ha creado una nueva solicitud que requiere su aprobación:</p>
                    
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
                                ⏳ Pendiente de Aprobación
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
                    <p>Sistema de Gestión de Inventarios - Qualitas Colombia</p>
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
Estado: Pendiente de Aprobación
Fecha: {fecha_actual}

---
Sistema de Gestión de Inventarios - Qualitas Colombia
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
            logger.warning(f"No se encontró email para notificar solicitud {solicitud_info.get('id')}")
            return False
        
        fecha_actual = datetime.now().strftime('%d/%m/%Y %H:%M')
        estado_config = ESTILOS['estados_solicitud'].get(estado_nuevo, {})
        
        asunto = f'{estado_config.get("icono", "📋")} Solicitud {estado_nuevo} - {solicitud_info.get("material_nombre", "Material")}'
        
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
                    <h1>{estado_config.get('icono', '📋')} Solicitud {estado_nuevo}</h1>
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
                        {f'<div class="detail-row"><span class="detail-label">Observación:</span><span class="detail-value">{observacion}</span></div>' if observacion else ''}
                    </div>
                </div>
                <div class="footer">
                    <p>Sistema de Gestión de Inventarios - Qualitas Colombia</p>
                </div>
            </div>
        </body>
        </html>
        '''
        
        texto = f'''
ACTUALIZACIÓN DE SOLICITUD
==========================

Material: {solicitud_info.get('material_nombre', 'N/A')}
Cantidad: {solicitud_info.get('cantidad_solicitada', 0)} unidades
Estado Anterior: {estado_anterior}
Nuevo Estado: {estado_nuevo}
Procesado por: {usuario_accion}
Fecha: {fecha_actual}
{f'Observación: {observacion}' if observacion else ''}

---
Sistema de Gestión de Inventarios - Qualitas Colombia
        '''
        
        return NotificationService._enviar_email(email_destino, asunto, html, texto)

    @staticmethod
    def notificar_novedad_registrada(solicitud_info, novedad_info):
        """Notifica a los gestores cuando se registra una novedad"""
        emails_gestores = NotificationService._obtener_emails_gestores()
        
        if not emails_gestores:
            return False
        
        fecha_actual = datetime.now().strftime('%d/%m/%Y %H:%M')
        
        asunto = f'⚠️ Nueva Novedad Registrada - Solicitud #{solicitud_info.get("id", "N/A")}'
        
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
                    <h1>⚠️ Nueva Novedad Registrada</h1>
                </div>
                <div class="content">
                    <p>Se ha registrado una novedad que requiere su atención:</p>
                    
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
                            <span class="detail-label">Descripción:</span>
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
                    <p>Sistema de Gestión de Inventarios - Qualitas Colombia</p>
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
Descripción: {novedad_info.get('descripcion', 'N/A')}
Cantidad Afectada: {novedad_info.get('cantidad_afectada', 0)}
Registrado por: {novedad_info.get('usuario_registra', 'N/A')}

---
Sistema de Gestión de Inventarios - Qualitas Colombia
        '''
        
        exitos = 0
        for email in emails_gestores:
            if NotificationService._enviar_email(email, asunto, html, texto):
                exitos += 1
        
        return exitos > 0

    # ========================================================================
    # NOTIFICACIONES - PRÉSTAMOS
    # ========================================================================
    
    @staticmethod
    def notificar_prestamo_creado(prestamo_info):
        """Notifica a los gestores cuando se crea un nuevo préstamo"""
        emails_gestores = NotificationService._obtener_emails_gestores()
        
        if not emails_gestores:
            return False
        
        fecha_actual = datetime.now().strftime('%d/%m/%Y %H:%M')
        estado_config = ESTILOS['estados_prestamo'].get('PRESTADO', {})
        
        asunto = f'📋 Nuevo Préstamo Solicitado - {prestamo_info.get("material", "Material")}'
        
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
                    <h1>📋 Nuevo Préstamo Solicitado</h1>
                </div>
                <div class="content">
                    <p>Se ha registrado un nuevo préstamo que requiere aprobación:</p>
                    
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
                            <span class="detail-label">Fecha Devolución Prevista:</span>
                            <span class="detail-value">{prestamo_info.get('fecha_prevista', 'N/A')}</span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-label">Estado:</span>
                            <span class="badge" style="background: {estado_config.get('bg', '#fff3cd')}; color: {estado_config.get('color', '#856404')};">
                                📋 Pendiente de Aprobación
                            </span>
                        </div>
                    </div>
                </div>
                <div class="footer">
                    <p>Sistema de Gestión de Inventarios - Qualitas Colombia</p>
                </div>
            </div>
        </body>
        </html>
        '''
        
        texto = f'''
NUEVO PRÉSTAMO SOLICITADO
=========================

Elemento: {prestamo_info.get('material', 'N/A')}
Cantidad: {prestamo_info.get('cantidad', 0)} unidades
Solicitante: {prestamo_info.get('solicitante_nombre', 'N/A')}
Oficina: {prestamo_info.get('oficina_nombre', 'N/A')}
Evento: {prestamo_info.get('evento', 'N/A')}
Fecha Devolución Prevista: {prestamo_info.get('fecha_prevista', 'N/A')}

---
Sistema de Gestión de Inventarios - Qualitas Colombia
        '''
        
        exitos = 0
        for email in emails_gestores:
            if NotificationService._enviar_email(email, asunto, html, texto):
                exitos += 1
        
        return exitos > 0

    @staticmethod
    def notificar_cambio_estado_prestamo(prestamo_info, estado_nuevo, usuario_accion, observacion=''):
        """Notifica al solicitante cuando cambia el estado de su préstamo"""
        
        email_destino = prestamo_info.get('email_solicitante')
        
        if not email_destino:
            logger.warning(f"No se encontró email para notificar préstamo {prestamo_info.get('id')}")
            return False
        
        fecha_actual = datetime.now().strftime('%d/%m/%Y %H:%M')
        estado_config = ESTILOS['estados_prestamo'].get(estado_nuevo, {})
        
        asunto = f'{estado_config.get("icono", "📋")} Préstamo {estado_nuevo} - {prestamo_info.get("material", "Material")}'
        
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
                    <h1>{estado_config.get('icono', '📋')} Préstamo {estado_nuevo}</h1>
                </div>
                <div class="content">
                    <p>Hola <strong>{prestamo_info.get('solicitante_nombre', '')}</strong>,</p>
                    <p>Tu préstamo ha sido actualizado:</p>
                    
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
                        {f'<div class="detail-row"><span class="detail-label">Observación:</span><span class="detail-value">{observacion}</span></div>' if observacion else ''}
                    </div>
                </div>
                <div class="footer">
                    <p>Sistema de Gestión de Inventarios - Qualitas Colombia</p>
                </div>
            </div>
        </body>
        </html>
        '''
        
        texto = f'''
ACTUALIZACIÓN DE PRÉSTAMO
=========================

Elemento: {prestamo_info.get('material', 'N/A')}
Cantidad: {prestamo_info.get('cantidad', 0)} unidades
Nuevo Estado: {estado_nuevo}
Procesado por: {usuario_accion}
Fecha: {fecha_actual}
{f'Observación: {observacion}' if observacion else ''}

---
Sistema de Gestión de Inventarios - Qualitas Colombia
        '''
        
        return NotificationService._enviar_email(email_destino, asunto, html, texto)


# ============================================================================
# FUNCIONES DE CONVENIENCIA (compatibilidad con código existente)
# ============================================================================

def notificar_asignacion_inventario(destinatario_email, destinatario_nombre, 
                                     producto_info, cantidad, oficina_nombre, asignador_nombre):
    """Wrapper para compatibilidad con código existente"""
    return NotificationService.enviar_notificacion_asignacion(
        destinatario_email, destinatario_nombre, producto_info, 
        cantidad, oficina_nombre, asignador_nombre
    )

def notificar_solicitud(solicitud_info, tipo_notificacion, **kwargs):
    """
    Función genérica para notificar sobre solicitudes
    
    Args:
        solicitud_info: Diccionario con información de la solicitud
        tipo_notificacion: 'creada', 'aprobada', 'rechazada', 'entregada', etc.
        **kwargs: Argumentos adicionales según el tipo
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
    Función genérica para notificar sobre préstamos
    
    Args:
        prestamo_info: Diccionario con información del préstamo
        tipo_notificacion: 'creado', 'aprobado', 'rechazado', 'devuelto'
        **kwargs: Argumentos adicionales
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
