#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de Diagnóstico de Notificaciones - Compatible con Windows
Sistema de Gestión de Inventarios - Qualitas Colombia

VERSIÓN SIN EMOJIS PARA COMPATIBILIDAD CON CMD DE WINDOWS
"""

import smtplib
import socket
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import sys
import io

# Configurar stdout para UTF-8 (Windows)
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# Configuración de logging SIN emojis
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('diagnostico_notificaciones.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Símbolos ASCII en lugar de emojis
OK = "[OK]"
FAIL = "[FAIL]"
WARN = "[WARN]"
INFO = "[INFO]"

# ============================================================================
# CONFIGURACIÓN ACTUAL DEL SISTEMA
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
# PRUEBAS DE DIAGNÓSTICO
# ============================================================================

def print_section(title):
    """Imprime una sección visual"""
    print("\n" + "="*70)
    print(f" {title}")
    print("="*70 + "\n")

def test_1_dns_resolution():
    """Prueba 1: Resolución DNS del servidor SMTP"""
    print_section("PRUEBA 1: Resolución DNS")
    
    try:
        smtp_server = EMAIL_CONFIG['smtp_server']
        ip_address = socket.gethostbyname(smtp_server)
        logger.info(f"{OK} DNS OK - {smtp_server} resuelve a {ip_address}")
        return True, ip_address
    except socket.gaierror as e:
        logger.error(f"{FAIL} Error DNS - No se puede resolver {smtp_server}: {e}")
        return False, None
    except Exception as e:
        logger.error(f"{FAIL} Error inesperado en resolución DNS: {e}")
        return False, None

def test_2_tcp_connection():
    """Prueba 2: Conectividad TCP al puerto SMTP"""
    print_section("PRUEBA 2: Conectividad TCP")
    
    smtp_server = EMAIL_CONFIG['smtp_server']
    smtp_port = EMAIL_CONFIG['smtp_port']
    
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10)
        result = sock.connect_ex((smtp_server, smtp_port))
        sock.close()
        
        if result == 0:
            logger.info(f"{OK} Conectividad TCP OK - Puerto {smtp_port} está abierto en {smtp_server}")
            return True
        else:
            logger.error(f"{FAIL} Puerto {smtp_port} CERRADO en {smtp_server}")
            logger.error("   Posibles causas:")
            logger.error("   - Firewall bloqueando el puerto")
            logger.error("   - Servidor SMTP no está escuchando en este puerto")
            logger.error("   - Configuración de red incorrecta")
            return False
    except socket.timeout:
        logger.error(f"{FAIL} TIMEOUT - No se pudo conectar a {smtp_server}:{smtp_port} en 10 segundos")
        return False
    except Exception as e:
        logger.error(f"{FAIL} Error en conexión TCP: {e}")
        return False

def test_3_smtp_handshake():
    """Prueba 3: Handshake SMTP básico"""
    print_section("PRUEBA 3: Handshake SMTP")
    
    try:
        logger.info(f"Intentando conectar a {EMAIL_CONFIG['smtp_server']}:{EMAIL_CONFIG['smtp_port']}...")
        server = smtplib.SMTP(EMAIL_CONFIG['smtp_server'], EMAIL_CONFIG['smtp_port'], timeout=30)
        server.set_debuglevel(1)
        
        logger.info(f"{OK} Handshake SMTP exitoso")
        ehlo_response = server.ehlo()
        if ehlo_response[0] == 250:
            logger.info(f"   Respuesta del servidor: {ehlo_response[1].decode()}")
        
        if EMAIL_CONFIG['use_tls']:
            logger.info("   Intentando STARTTLS...")
            server.starttls()
            logger.info(f"   {OK} TLS habilitado")
        
        server.quit()
        return True
    except smtplib.SMTPConnectError as e:
        logger.error(f"{FAIL} Error de conexión SMTP: {e}")
        return False
    except smtplib.SMTPServerDisconnected as e:
        logger.error(f"{FAIL} Servidor desconectó: {e}")
        return False
    except Exception as e:
        logger.error(f"{FAIL} Error en handshake SMTP: {e}")
        return False

def test_4_smtp_authentication():
    """Prueba 4: Autenticación SMTP (si se requiere)"""
    print_section("PRUEBA 4: Autenticación SMTP")
    
    if not EMAIL_CONFIG['smtp_user'] or not EMAIL_CONFIG['smtp_password']:
        logger.info(f"{WARN} No hay credenciales configuradas - Asumiendo servidor sin autenticación")
        return True
    
    try:
        server = smtplib.SMTP(EMAIL_CONFIG['smtp_server'], EMAIL_CONFIG['smtp_port'], timeout=30)
        
        if EMAIL_CONFIG['use_tls']:
            server.starttls()
        
        logger.info(f"Intentando autenticar como {EMAIL_CONFIG['smtp_user']}...")
        server.login(EMAIL_CONFIG['smtp_user'], EMAIL_CONFIG['smtp_password'])
        logger.info(f"{OK} Autenticación exitosa")
        
        server.quit()
        return True
    except smtplib.SMTPAuthenticationError as e:
        logger.error(f"{FAIL} Error de autenticación: {e}")
        logger.error("   Verifica usuario y contraseña")
        return False
    except smtplib.SMTPException as e:
        logger.error(f"{FAIL} Error SMTP durante autenticación: {e}")
        return False
    except Exception as e:
        logger.error(f"{FAIL} Error inesperado: {e}")
        return False

def test_5_send_test_email(destinatario_email):
    """Prueba 5: Envío de email de prueba"""
    print_section(f"PRUEBA 5: Envío de Email de Prueba a {destinatario_email}")
    
    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = f'[PRUEBA] Sistema de Inventarios - {datetime.now().strftime("%d/%m/%Y %H:%M")}'
        msg['From'] = f'{EMAIL_CONFIG["from_name"]} <{EMAIL_CONFIG["from_email"]}>'
        msg['To'] = destinatario_email
        
        texto = f'''
PRUEBA DE NOTIFICACIONES
=========================

Este es un email de prueba del Sistema de Gestión de Inventarios.

Si recibes este mensaje, significa que:
[OK] La configuración SMTP es correcta
[OK] El servidor puede enviar emails
[OK] No hay bloqueos de firewall
[OK] La ruta de red es funcional

Fecha/Hora: {datetime.now().strftime("%d/%m/%Y %H:%M:%S")}

---
Sistema de Gestión de Inventarios - Qualitas Colombia
        '''
        
        html = f'''
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    line-height: 1.6;
                    color: #333;
                    max-width: 600px;
                    margin: 0 auto;
                    padding: 20px;
                }}
                .header {{
                    background: linear-gradient(135deg, #0d6efd 0%, #0a58ca 100%);
                    color: white;
                    padding: 30px;
                    text-align: center;
                    border-radius: 10px 10px 0 0;
                }}
                .content {{
                    background: white;
                    padding: 30px;
                    border: 1px solid #ddd;
                }}
                .success {{
                    background: #d1e7dd;
                    color: #0f5132;
                    padding: 15px;
                    border-radius: 5px;
                    margin: 20px 0;
                }}
                .footer {{
                    background: #e9ecef;
                    padding: 20px;
                    text-align: center;
                    font-size: 12px;
                    color: #666;
                    border-radius: 0 0 10px 10px;
                }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>Prueba de Notificaciones</h1>
            </div>
            <div class="content">
                <h2>Sistema de Gestión de Inventarios</h2>
                <p>Este es un email de prueba para verificar la configuración SMTP.</p>
                
                <div class="success">
                    <strong>[OK] Configuración exitosa!</strong><br>
                    Si recibes este mensaje, el sistema de notificaciones está funcionando correctamente.
                </div>
                
                <p><strong>Detalles de la prueba:</strong></p>
                <ul>
                    <li>Servidor SMTP: {EMAIL_CONFIG['smtp_server']}:{EMAIL_CONFIG['smtp_port']}</li>
                    <li>Fecha/Hora: {datetime.now().strftime("%d/%m/%Y %H:%M:%S")}</li>
                    <li>Desde: {EMAIL_CONFIG['from_email']}</li>
                    <li>TLS: {'Habilitado' if EMAIL_CONFIG['use_tls'] else 'Deshabilitado'}</li>
                </ul>
            </div>
            <div class="footer">
                <p>Sistema de Gestión de Inventarios - Qualitas Colombia</p>
                <p>Este es un mensaje automático de prueba</p>
            </div>
        </body>
        </html>
        '''
        
        part1 = MIMEText(texto, 'plain', 'utf-8')
        part2 = MIMEText(html, 'html', 'utf-8')
        msg.attach(part1)
        msg.attach(part2)
        
        logger.info("Conectando al servidor SMTP...")
        server = smtplib.SMTP(EMAIL_CONFIG['smtp_server'], EMAIL_CONFIG['smtp_port'], timeout=30)
        server.set_debuglevel(1)
        
        if EMAIL_CONFIG['use_tls']:
            server.starttls()
        
        if EMAIL_CONFIG['smtp_user'] and EMAIL_CONFIG['smtp_password']:
            server.login(EMAIL_CONFIG['smtp_user'], EMAIL_CONFIG['smtp_password'])
        
        logger.info(f"Enviando email a {destinatario_email}...")
        server.sendmail(EMAIL_CONFIG['from_email'], destinatario_email, msg.as_string())
        server.quit()
        
        logger.info(f"{OK} Email enviado exitosamente a {destinatario_email}")
        logger.info("   Revisa la bandeja de entrada (y spam) del destinatario")
        return True
        
    except smtplib.SMTPRecipientsRefused as e:
        logger.error(f"{FAIL} Destinatario rechazado: {e}")
        logger.error("   El servidor rechazó el destinatario. Verifica que el email sea válido.")
        return False
    except smtplib.SMTPSenderRefused as e:
        logger.error(f"{FAIL} Remitente rechazado: {e}")
        logger.error("   El servidor rechazó el remitente. Verifica el 'from_email'.")
        return False
    except Exception as e:
        logger.error(f"{FAIL} Error enviando email: {e}")
        return False

def test_6_manual_telnet_instructions():
    """Prueba 6: Instrucciones para prueba manual con telnet"""
    print_section("PRUEBA 6: Instrucciones para Prueba Manual con Telnet")
    
    print(f"""
Para probar manualmente la conectividad SMTP usando telnet, ejecuta:

En Windows:
-----------
1. Abre CMD o PowerShell como administrador
2. Ejecuta: telnet {EMAIL_CONFIG['smtp_server']} {EMAIL_CONFIG['smtp_port']}

Si telnet no está instalado en Windows, instálalo con:
- Panel de Control > Programas > Activar o desactivar características de Windows
- Marca "Cliente Telnet"

O usa PowerShell:
Test-NetConnection -ComputerName {EMAIL_CONFIG['smtp_server']} -Port {EMAIL_CONFIG['smtp_port']}

En Linux/Mac:
-------------
telnet {EMAIL_CONFIG['smtp_server']} {EMAIL_CONFIG['smtp_port']}

Comandos SMTP para probar manualmente:
---------------------------------------
Una vez conectado, escribe estos comandos uno por uno:

EHLO localhost
MAIL FROM:<{EMAIL_CONFIG['from_email']}>
RCPT TO:<TU_EMAIL_AQUI>
DATA
Subject: Prueba Manual
From: {EMAIL_CONFIG['from_email']}
To: TU_EMAIL_AQUI

Este es un email de prueba manual.
.
QUIT

Notas:
------
- Después de escribir ".", el servidor enviará el email
- Si ves "220" al conectar, la conexión es exitosa
- Si ves "250", el comando fue aceptado
- Si ves errores 5XX, hay un problema de configuración
    """)

def run_diagnostics(test_email=None):
    """Ejecuta todos los diagnósticos"""
    
    print("\n" + "="*70)
    print(" DIAGNOSTICO DE NOTIFICACIONES - SISTEMA DE INVENTARIOS")
    print("="*70)
    print(f"\nFecha: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    print(f"Servidor SMTP: {EMAIL_CONFIG['smtp_server']}:{EMAIL_CONFIG['smtp_port']}")
    print(f"Usuario SMTP: {EMAIL_CONFIG['smtp_user']}")
    print(f"TLS: {'Habilitado' if EMAIL_CONFIG['use_tls'] else 'Deshabilitado'}")
    
    results = {
        'dns': False,
        'tcp': False,
        'handshake': False,
        'auth': False,
        'email': False
    }
    
    # Ejecutar pruebas
    results['dns'], ip = test_1_dns_resolution()
    
    if results['dns']:
        results['tcp'] = test_2_tcp_connection()
    
    if results['tcp']:
        results['handshake'] = test_3_smtp_handshake()
    
    if results['handshake']:
        results['auth'] = test_4_smtp_authentication()
    
    if results['auth'] and test_email:
        results['email'] = test_5_send_test_email(test_email)
    elif results['auth'] and not test_email:
        logger.warning(f"{WARN} No se proporcionó email de prueba. Usa: python diagnostico_notificaciones.py tu@email.com")
    
    test_6_manual_telnet_instructions()
    
    # Resumen final
    print_section("RESUMEN DEL DIAGNÓSTICO")
    
    status_symbol = lambda x: OK if x else FAIL
    
    print(f"{status_symbol(results['dns'])} Resolución DNS")
    print(f"{status_symbol(results['tcp'])} Conectividad TCP")
    print(f"{status_symbol(results['handshake'])} Handshake SMTP")
    print(f"{status_symbol(results['auth'])} Autenticación")
    if test_email:
        print(f"{status_symbol(results['email'])} Envío de Email de Prueba")
    
    all_passed = all([results['dns'], results['tcp'], results['handshake'], results['auth']])
    
    if all_passed:
        print(f"\n{OK} TODAS LAS PRUEBAS BÁSICAS PASARON")
        if test_email and results['email']:
            print(f"   {OK} Email de prueba enviado a {test_email}")
            print("   Revisa la bandeja de entrada (y spam) del destinatario")
        elif test_email and not results['email']:
            print(f"   {WARN} Las pruebas básicas pasaron pero falló el envío del email")
            print("   Revisa los logs arriba para más detalles")
    else:
        print(f"\n{WARN} ALGUNAS PRUEBAS FALLARON")
        print("\nPOSIBLES CAUSAS Y SOLUCIONES:")
        
        if not results['dns']:
            print(f"\n{FAIL} DNS:")
            print("   - Verifica que '10.60.0.30' sea la IP correcta del servidor SMTP")
            print("   - Prueba hacer ping: ping 10.60.0.30")
        
        if not results['tcp']:
            print(f"\n{FAIL} Conectividad TCP:")
            print("   - Verifica que no haya firewall bloqueando el puerto 25")
            print("   - Verifica que el servidor SMTP esté corriendo")
            print("   - Intenta con telnet (ver instrucciones arriba)")
        
        if not results['handshake']:
            print(f"\n{FAIL} Handshake SMTP:")
            print("   - El servidor puede no ser un servidor SMTP")
            print("   - El puerto puede estar bloqueado después de la conexión")
        
        if not results['auth']:
            print(f"\n{FAIL} Autenticación:")
            print("   - Verifica usuario y contraseña")
            print("   - El servidor puede no requerir autenticación")
        
        if test_email and not results['email']:
            print(f"\n{FAIL} Envío de Email:")
            print("   - Revisa los logs detallados arriba")
            print("   - El servidor puede estar rechazando emails")
    
    print("\n" + "="*70)
    print(" Log completo guardado en: diagnostico_notificaciones.log")
    print("="*70 + "\n")
    
    return all_passed

if __name__ == "__main__":
    test_email = sys.argv[1] if len(sys.argv) > 1 else None
    
    if not test_email:
        print(f"\n{WARN} USO RECOMENDADO:")
        print(f"   python {sys.argv[0]} tu@email.com")
        print("\n   Ejecutando diagnóstico sin envío de email de prueba...\n")
    
    success = run_diagnostics(test_email)
    
    sys.exit(0 if success else 1)
