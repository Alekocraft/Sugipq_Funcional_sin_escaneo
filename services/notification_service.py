# services/notification_service.py
"""
Servicio para enviar notificaciones por email.
Incluye:
- Notificaciones de asignación de inventario
- Notificaciones con confirmación de recepción
- Sistema de tokens para confirmaciones
"""

import smtplib
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate
import os
from datetime import datetime

logger = logging.getLogger(__name__)


class NotificationService:
    """
    Servicio de notificaciones por correo electrónico.
    """
    
    # Configuración SMTP
    SMTP_CONFIG = {
        'server': os.getenv('SMTP_SERVER', '10.60.0.31'),
        'port': int(os.getenv('SMTP_PORT', 25)),
        'use_tls': os.getenv('SMTP_USE_TLS', 'False').lower() == 'true',
        'from_email': os.getenv('SMTP_FROM_EMAIL', 'gestiondeInventarios@qualitascolombia.com.co'),
        'username': os.getenv('SMTP_USERNAME', ''),
        'password': os.getenv('SMTP_PASSWORD', '')
    }
    
    @staticmethod
    def _connect_smtp():
        """
        Conecta al servidor SMTP.
        
        Returns:
            smtplib.SMTP: Conexión SMTP o None si falla
        """
        try:
            logger.info(f"🔄 Conectando al servidor SMTP: {NotificationService.SMTP_CONFIG['server']}:{NotificationService.SMTP_CONFIG['port']}")
            
            if NotificationService.SMTP_CONFIG['use_tls']:
                smtp = smtplib.SMTP(NotificationService.SMTP_CONFIG['server'], 
                                   NotificationService.SMTP_CONFIG['port'])
                smtp.starttls()
            else:
                smtp = smtplib.SMTP(NotificationService.SMTP_CONFIG['server'], 
                                   NotificationService.SMTP_CONFIG['port'])
            
            # Si hay credenciales, autenticar
            if (NotificationService.SMTP_CONFIG['username'] and 
                NotificationService.SMTP_CONFIG['password']):
                smtp.login(NotificationService.SMTP_CONFIG['username'], 
                          NotificationService.SMTP_CONFIG['password'])
            
            logger.info("✅ Conexión SMTP exitosa")
            return smtp
            
        except Exception as e:
            logger.error("❌ Error conectando al SMTP: [error](%s)", type(e).__name__)
            return None
    
    @staticmethod
    def _send_email_smtp(msg):
        """
        Envía un email usando SMTP.
        
        Args:
            msg: Objeto MIMEMultipart con el email
            
        Returns:
            bool: True si se envió correctamente, False si falló
        """
        smtp = None
        try:
            smtp = NotificationService._connect_smtp()
            if not smtp:
                logger.error("❌ No se pudo conectar al servidor SMTP")
                return False
            
            # Enviar email
            smtp.send_message(msg)
            logger.info(f"✅ Email enviado exitosamente a {msg['To']}")
            return True
            
        except Exception as e:
            logger.error("❌ Error enviando email: [error](%s)", type(e).__name__)
            return False
            
        finally:
            if smtp:
                try:
                    smtp.quit()
                    logger.debug("🔌 Conexión SMTP cerrada")
                except:
                    pass
    
    @staticmethod
    def enviar_notificacion_asignacion_con_confirmacion(
        destinatario_email, 
        destinatario_nombre, 
        producto_info, 
        cantidad,
        oficina_nombre, 
        asignador_nombre,
        token_confirmacion,
        base_url
    ):
        """
        Envía notificación de asignación con enlace para confirmar recepción.
        
        Args:
            destinatario_email: Email del destinatario
            destinatario_nombre: Nombre del destinatario
            producto_info: Diccionario con información del producto
            cantidad: Cantidad asignada
            oficina_nombre: Nombre de la oficina destino
            asignador_nombre: Nombre de quien realiza la asignación
            token_confirmacion: Token para confirmación
            base_url: URL base de la aplicación
            
        Returns:
            bool: True si se envió correctamente, False si falló
        """
        try:
            logger.info(f"📧 Preparando notificación de asignación con confirmación para {destinatario_email}")
            
            # Validar datos esenciales
            if not destinatario_email:
                logger.error("❌ Email del destinatario es requerido")
                return False
            
            if not token_confirmacion:
                logger.error("❌ Token de confirmación es requerido")
                return False
            
            # Crear el enlace de confirmación
            confirmacion_url = f"{base_url}/confirmacion/verificar/{token_confirmacion}"
            logger.info(f"🔗 Generando enlace de confirmación: {confirmacion_url[:60]}...")
            
            # Detalles del producto
            producto_nombre = producto_info.get('nombre', 'Producto de inventario')
            producto_codigo = producto_info.get('codigo_unico', 'N/A')
            producto_categoria = producto_info.get('categoria', 'General')
            
            # Crear mensaje de email
            msg = MIMEMultipart('alternative')
            msg['From'] = NotificationService.SMTP_CONFIG['from_email']
            msg['To'] = destinatario_email
            msg['Date'] = formatdate(localtime=True)
            msg['Subject'] = f"📦 Asignación de Inventario - {producto_nombre}"
            
            # Cuerpo del email en HTML
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Notificación de Asignación</title>
                <style>
                    body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                    .container {{ max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #ddd; border-radius: 5px; }}
                    .header {{ background-color: #f8f9fa; padding: 15px; border-bottom: 1px solid #ddd; text-align: center; }}
                    .content {{ padding: 20px; }}
                    .details {{ background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin: 20px 0; }}
                    .btn-confirm {{ display: inline-block; background-color: #28a745; color: white; 
                                 padding: 12px 24px; text-decoration: none; border-radius: 5px; 
                                 font-weight: bold; margin: 15px 0; }}
                    .footer {{ margin-top: 30px; padding-top: 20px; border-top: 1px solid #ddd; 
                             font-size: 12px; color: #666; text-align: center; }}
                    .important {{ color: #dc3545; font-weight: bold; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h2>📦 Sistema de Gestión de Inventarios</h2>
                        <h3>Asignación de Producto</h3>
                    </div>
                    
                    <div class="content">
                        <p>Estimado/a <strong>{destinatario_nombre}</strong>,</p>
                        
                        <p>Se le ha asignado un producto del inventario corporativo:</p>
                        
                        <div class="details">
                            <h4>📋 Detalles de la Asignación</h4>
                            <p><strong>Producto:</strong> {producto_nombre}</p>
                            <p><strong>Código:</strong> {producto_codigo}</p>
                            <p><strong>Categoría:</strong> {producto_categoria}</p>
                            <p><strong>Cantidad:</strong> {cantidad} unidad(es)</p>
                            <p><strong>Oficina Destino:</strong> {oficina_nombre}</p>
                            <p><strong>Asignado por:</strong> {asignador_nombre}</p>
                            <p><strong>Fecha de asignación:</strong> {datetime.now().strftime('%d/%m/%Y %H:%M')}</p>
                        </div>
                        
                        <p class="important">⚠️ IMPORTANTE: Debe confirmar la recepción de este producto</p>
                        
                        <p>Para confirmar que ha recibido este producto, por favor haga clic en el siguiente botón:</p>
                        
                        <div style="text-align: center; margin: 25px 0;">
                            <a href="{confirmacion_url}" class="btn-confirm">
                                ✅ CONFIRMAR RECEPCIÓN
                            </a>
                        </div>
                        
                        <p>O copie y pegue este enlace en su navegador:</p>
                        <p><small>{confirmacion_url}</small></p>
                        
                        <p><strong>Nota:</strong> Este enlace es válido por <span class="important">8 días</span> a partir de la fecha de asignación.</p>
                        
                        <p>Si usted no ha recibido este producto o existe algún error, por favor contacte al área de inventarios inmediatamente.</p>
                    </div>
                    
                    <div class="footer">
                        <p>Este es un mensaje automático del Sistema de Gestión de Inventarios de Qualitas Colombia.</p>
                        <p>Por favor no responda a este correo.</p>
                        <p>© {datetime.now().year} Qualitas Colombia - Todos los derechos reservados</p>
                    </div>
                </div>
            </body>
            </html>
            """
            
            # Versión de texto plano
            text_content = f"""
            ASIGNACIÓN DE INVENTARIO - SISTEMA DE GESTIÓN DE INVENTARIOS
            
            Estimado/a {destinatario_nombre},
            
            Se le ha asignado un producto del inventario corporativo:
            
            📋 DETALLES DE LA ASIGNACIÓN:
            ------------------------------
            Producto: {producto_nombre}
            Código: {producto_codigo}
            Categoría: {producto_categoria}
            Cantidad: {cantidad} unidad(es)
            Oficina Destino: {oficina_nombre}
            Asignado por: {asignador_nombre}
            Fecha de asignación: {datetime.now().strftime('%d/%m/%Y %H:%M')}
            
            ⚠️ IMPORTANTE: Debe confirmar la recepción de este producto
            
            Para confirmar que ha recibido este producto, utilice el siguiente enlace:
            
            {confirmacion_url}
            
            Nota: Este enlace es válido por 8 días a partir de la fecha de asignación.
            
            Si usted no ha recibido este producto o existe algún error, por favor contacte al área de inventarios inmediatamente.
            
            --
            Este es un mensaje automático del Sistema de Gestión de Inventarios de Qualitas Colombia.
            Por favor no responda a este correo.
            © {datetime.now().year} Qualitas Colombia - Todos los derechos reservados
            """
            
            # Adjuntar ambas versiones
            part1 = MIMEText(text_content, 'plain')
            part2 = MIMEText(html_content, 'html')
            
            msg.attach(part1)
            msg.attach(part2)
            
            # Enviar el email
            success = NotificationService._send_email_smtp(msg)
            
            if success:
                logger.info(f"✅ Notificación de asignación con confirmación enviada a {destinatario_email}")
                return True
            else:
                logger.error(f"❌ No se pudo enviar notificación a {destinatario_email}")
                return False
                
        except Exception as e:
            logger.error("❌ Error en enviar_notificacion_asignacion_con_confirmacion: [error](%s)", type(e).__name__)
            import traceback
            logger.error(f"❌ Traceback: {traceback.format_exc()}")
            return False
    
    @staticmethod
    def enviar_notificacion_asignacion_simple(
        destinatario_email, 
        destinatario_nombre, 
        producto_info, 
        cantidad,
        oficina_nombre, 
        asignador_nombre
    ):
        """
        Envía notificación de asignación simple (sin confirmación).
        
        Args:
            destinatario_email: Email del destinatario
            destinatario_nombre: Nombre del destinatario
            producto_info: Diccionario con información del producto
            cantidad: Cantidad asignada
            oficina_nombre: Nombre de la oficina destino
            asignador_nombre: Nombre de quien realiza la asignación
            
        Returns:
            bool: True si se envió correctamente, False si falló
        """
        try:
            logger.info(f"📧 Preparando notificación de asignación simple para {destinatario_email}")
            
            # Validar datos esenciales
            if not destinatario_email:
                logger.error("❌ Email del destinatario es requerido")
                return False
            
            # Detalles del producto
            producto_nombre = producto_info.get('nombre', 'Producto de inventario')
            producto_codigo = producto_info.get('codigo_unico', 'N/A')
            producto_categoria = producto_info.get('categoria', 'General')
            
            # Crear mensaje de email
            msg = MIMEMultipart('alternative')
            msg['From'] = NotificationService.SMTP_CONFIG['from_email']
            msg['To'] = destinatario_email
            msg['Date'] = formatdate(localtime=True)
            msg['Subject'] = f"📦 Asignación de Inventario - {producto_nombre}"
            
            # Cuerpo del email en HTML
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Notificación de Asignación</title>
                <style>
                    body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                    .container {{ max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #ddd; border-radius: 5px; }}
                    .header {{ background-color: #f8f9fa; padding: 15px; border-bottom: 1px solid #ddd; text-align: center; }}
                    .content {{ padding: 20px; }}
                    .details {{ background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin: 20px 0; }}
                    .footer {{ margin-top: 30px; padding-top: 20px; border-top: 1px solid #ddd; 
                             font-size: 12px; color: #666; text-align: center; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h2>📦 Sistema de Gestión de Inventarios</h2>
                        <h3>Asignación de Producto</h3>
                    </div>
                    
                    <div class="content">
                        <p>Estimado/a <strong>{destinatario_nombre}</strong>,</p>
                        
                        <p>Se le ha asignado un producto del inventario corporativo:</p>
                        
                        <div class="details">
                            <h4>📋 Detalles de la Asignación</h4>
                            <p><strong>Producto:</strong> {producto_nombre}</p>
                            <p><strong>Código:</strong> {producto_codigo}</p>
                            <p><strong>Categoría:</strong> {producto_categoria}</p>
                            <p><strong>Cantidad:</strong> {cantidad} unidad(es)</p>
                            <p><strong>Oficina Destino:</strong> {oficina_nombre}</p>
                            <p><strong>Asignado por:</strong> {asignador_nombre}</p>
                            <p><strong>Fecha de asignación:</strong> {datetime.now().strftime('%d/%m/%Y %H:%M')}</p>
                        </div>
                        
                        <p>Este producto ha sido registrado en el sistema de gestión de inventarios.</p>
                        
                        <p>Si existe algún error o discrepancia, por favor contacte al área de inventarios.</p>
                    </div>
                    
                    <div class="footer">
                        <p>Este es un mensaje automático del Sistema de Gestión de Inventarios de Qualitas Colombia.</p>
                        <p>Por favor no responda a este correo.</p>
                        <p>© {datetime.now().year} Qualitas Colombia - Todos los derechos reservados</p>
                    </div>
                </div>
            </body>
            </html>
            """
            
            # Versión de texto plano
            text_content = f"""
            ASIGNACIÓN DE INVENTARIO - SISTEMA DE GESTIÓN DE INVENTARIOS
            
            Estimado/a {destinatario_nombre},
            
            Se le ha asignado un producto del inventario corporativo:
            
            📋 DETALLES DE LA ASIGNACIÓN:
            ------------------------------
            Producto: {producto_nombre}
            Código: {producto_codigo}
            Categoría: {producto_categoria}
            Cantidad: {cantidad} unidad(es)
            Oficina Destino: {oficina_nombre}
            Asignado por: {asignador_nombre}
            Fecha de asignación: {datetime.now().strftime('%d/%m/%Y %H:%M')}
            
            Este producto ha sido registrado en el sistema de gestión de inventarios.
            
            Si existe algún error o discrepancia, por favor contacte al área de inventarios.
            
            --
            Este es un mensaje automático del Sistema de Gestión de Inventarios de Qualitas Colombia.
            Por favor no responda a este correo.
            © {datetime.now().year} Qualitas Colombia - Todos los derechos reservados
            """
            
            # Adjuntar ambas versiones
            part1 = MIMEText(text_content, 'plain')
            part2 = MIMEText(html_content, 'html')
            
            msg.attach(part1)
            msg.attach(part2)
            
            # Enviar el email
            success = NotificationService._send_email_smtp(msg)
            
            if success:
                logger.info(f"✅ Notificación de asignación simple enviada a {destinatario_email}")
                return True
            else:
                logger.error(f"❌ No se pudo enviar notificación simple a {destinatario_email}")
                return False
                
        except Exception as e:
            logger.error("❌ Error en enviar_notificacion_asignacion_simple: [error](%s)", type(e).__name__)
            import traceback
            logger.error(f"❌ Traceback: {traceback.format_exc()}")
            return False
    
    @staticmethod
    def enviar_notificacion_confirmacion_exitosa(
        destinatario_email, 
        destinatario_nombre, 
        producto_info, 
        asignador_nombre
    ):
        """
        Envía notificación de confirmación exitosa al asignador.
        
        Args:
            destinatario_email: Email del asignador
            destinatario_nombre: Nombre del asignador
            producto_info: Diccionario con información del producto
            asignador_nombre: Nombre de quien realizó la asignación
            
        Returns:
            bool: True si se envió correctamente, False si falló
        """
        try:
            logger.info(f"📧 Preparando notificación de confirmación exitosa para {destinatario_email}")
            
            # Validar datos esenciales
            if not destinatario_email:
                logger.error("❌ Email del destinatario es requerido")
                return False
            
            # Detalles del producto
            producto_nombre = producto_info.get('nombre', 'Producto de inventario')
            producto_codigo = producto_info.get('codigo_unico', 'N/A')
            
            # Crear mensaje de email
            msg = MIMEMultipart('alternative')
            msg['From'] = NotificationService.SMTP_CONFIG['from_email']
            msg['To'] = destinatario_email
            msg['Date'] = formatdate(localtime=True)
            msg['Subject'] = f"✅ Confirmación de Recepción - {producto_nombre}"
            
            # Cuerpo del email en HTML
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Confirmación de Recepción</title>
                <style>
                    body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                    .container {{ max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #ddd; border-radius: 5px; }}
                    .header {{ background-color: #d4edda; padding: 15px; border-bottom: 1px solid #c3e6cb; text-align: center; color: #155724; }}
                    .content {{ padding: 20px; }}
                    .details {{ background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin: 20px 0; }}
                    .footer {{ margin-top: 30px; padding-top: 20px; border-top: 1px solid #ddd; 
                             font-size: 12px; color: #666; text-align: center; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h2>✅ Sistema de Gestión de Inventarios</h2>
                        <h3>Confirmación de Recepción Exitosa</h3>
                    </div>
                    
                    <div class="content">
                        <p>Estimado/a <strong>{destinatario_nombre}</strong>,</p>
                        
                        <p>Le informamos que la asignación del siguiente producto ha sido <strong>confirmada exitosamente</strong> por el destinatario:</p>
                        
                        <div class="details">
                            <h4>📋 Detalles del Producto</h4>
                            <p><strong>Producto:</strong> {producto_nombre}</p>
                            <p><strong>Código:</strong> {producto_codigo}</p>
                            <p><strong>Fecha de confirmación:</strong> {datetime.now().strftime('%d/%m/%Y %H:%M')}</p>
                        </div>
                        
                        <p>✅ <strong>Estado:</strong> La recepción ha sido confirmada correctamente.</p>
                        <p>📋 <strong>Proceso:</strong> Este producto ha completado el ciclo de asignación y confirmación en el sistema.</p>
                    </div>
                    
                    <div class="footer">
                        <p>Este es un mensaje automático del Sistema de Gestión de Inventarios de Qualitas Colombia.</p>
                        <p>Por favor no responda a este correo.</p>
                        <p>© {datetime.now().year} Qualitas Colombia - Todos los derechos reservados</p>
                    </div>
                </div>
            </body>
            </html>
            """
            
            # Versión de texto plano
            text_content = f"""
            CONFIRMACIÓN DE RECEPCIÓN EXITOSA - SISTEMA DE GESTIÓN DE INVENTARIOS
            
            Estimado/a {destinatario_nombre},
            
            Le informamos que la asignación del siguiente producto ha sido CONFIRMADA EXITOSAMENTE por el destinatario:
            
            📋 DETALLES DEL PRODUCTO:
            --------------------------
            Producto: {producto_nombre}
            Código: {producto_codigo}
            Fecha de confirmación: {datetime.now().strftime('%d/%m/%Y %H:%M')}
            
            ✅ Estado: La recepción ha sido confirmada correctamente.
            📋 Proceso: Este producto ha completado el ciclo de asignación y confirmación en el sistema.
            
            --
            Este es un mensaje automático del Sistema de Gestión de Inventarios de Qualitas Colombia.
            Por favor no responda a este correo.
            © {datetime.now().year} Qualitas Colombia - Todos los derechos reservados
            """
            
            # Adjuntar ambas versiones
            part1 = MIMEText(text_content, 'plain')
            part2 = MIMEText(html_content, 'html')
            
            msg.attach(part1)
            msg.attach(part2)
            
            # Enviar el email
            success = NotificationService._send_email_smtp(msg)
            
            if success:
                logger.info(f"✅ Notificación de confirmación exitosa enviada a {destinatario_email}")
                return True
            else:
                logger.error(f"❌ No se pudo enviar notificación de confirmación a {destinatario_email}")
                return False
                
        except Exception as e:
            logger.error("❌ Error en enviar_notificacion_confirmacion_exitosa: [error](%s)", type(e).__name__)
            import traceback
            logger.error(f"❌ Traceback: {traceback.format_exc()}")
            return False
    
    @staticmethod
    def enviar_notificacion_general(
        destinatario_email,
        destinatario_nombre,
        asunto,
        mensaje_html,
        mensaje_texto=None
    ):
        """
        Envía una notificación general.
        
        Args:
            destinatario_email: Email del destinatario
            destinatario_nombre: Nombre del destinatario
            asunto: Asunto del email
            mensaje_html: Contenido HTML del mensaje
            mensaje_texto: Contenido en texto plano (opcional)
            
        Returns:
            bool: True si se envió correctamente, False si falló
        """
        try:
            logger.info(f"📧 Preparando notificación general para {destinatario_email}")
            
            # Validar datos esenciales
            if not destinatario_email:
                logger.error("❌ Email del destinatario es requerido")
                return False
            
            # Crear mensaje de email
            msg = MIMEMultipart('alternative')
            msg['From'] = NotificationService.SMTP_CONFIG['from_email']
            msg['To'] = destinatario_email
            msg['Date'] = formatdate(localtime=True)
            msg['Subject'] = asunto
            
            # Adjuntar versión de texto plano si se proporciona
            if mensaje_texto:
                part1 = MIMEText(mensaje_texto, 'plain')
                msg.attach(part1)
            
            # Adjuntar versión HTML
            part2 = MIMEText(mensaje_html, 'html')
            msg.attach(part2)
            
            # Enviar el email
            success = NotificationService._send_email_smtp(msg)
            
            if success:
                logger.info(f"✅ Notificación general enviada a {destinatario_email}")
                return True
            else:
                logger.error(f"❌ No se pudo enviar notificación general a {destinatario_email}")
                return False
                
        except Exception as e:
            logger.error("❌ Error en enviar_notificacion_general: [error](%s)", type(e).__name__)
            import traceback
            logger.error(f"❌ Traceback: {traceback.format_exc()}")
            return False
    
    @staticmethod
    def test_conexion_smtp():
        """
        Prueba la conexión SMTP.
        
        Returns:
            dict: Resultado de la prueba
        """
        try:
            logger.info("🔧 Probando conexión SMTP...")
            
            smtp = NotificationService._connect_smtp()
            if smtp:
                smtp.quit()
                logger.info("✅ Prueba SMTP exitosa")
                return {
                    'success': True,
                    'message': 'Conexión SMTP exitosa',
                    'config': {
                        'server': NotificationService.SMTP_CONFIG['server'],
                        'port': NotificationService.SMTP_CONFIG['port'],
                        'use_tls': NotificationService.SMTP_CONFIG['use_tls'],
                        'from_email': NotificationService.SMTP_CONFIG['from_email']
                    }
                }
            else:
                logger.error("❌ Prueba SMTP fallida")
                return {
                    'success': False,
                    'message': 'No se pudo conectar al servidor SMTP',
                    'config': NotificationService.SMTP_CONFIG
                }
                
        except Exception as e:
            logger.error("❌ Error en prueba SMTP: [error](%s)", type(e).__name__)
            return {
                'success': False,
                'message': f'Error: {str(e)}',
                'config': NotificationService.SMTP_CONFIG
            }