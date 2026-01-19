#!/usr/bin/env python3
"""
Script de validación de vulnerabilidades de ALTO riesgo
Basado en: SUGIPQ-V1_05012026_Vulnerabilities.pdf

Total de vulnerabilidades de ALTO riesgo a validar: 64

Categorías principales:
1. Unvalidated untrusted input in log (CWE-117) - 29 defectos
2. Avoid sensitive information exposure through error messages (CWE-209) - 256 defectos 
3. Execution After Redirect (EAR) (CWE-698) - 93 defectos
4. Autocomplete enabled for sensitive form fields (CWE-525) - 11 defectos
5. Do not write IP address in source code (CWE-200) - 3 defectos
6. Improper Neutralization of links to external sites (CWE-1022) - 3 defectos
7. URL Redirection to Untrusted Site (CWE-601) - 3 defectos (2 en JS, 1 en Python)
8. Insecure transport in HTTP servers (CWE-311) - 2 defectos

Autor: Sistema de Validación de Seguridad
Fecha: 2026-01-06
"""

import os
import re
import sys
from pathlib import Path
from typing import List, Dict, Tuple
from datetime import datetime
import json

class ValidadorVulnerabilidades:
    """Validador de vulnerabilidades de seguridad de alto riesgo"""
    
    # Configuración de exclusiones
    CARPETAS_EXCLUIDAS = {
        'envt2',
        'venv',
        'env',
        '.venv',
        '__pycache__',
        '.git',
        'node_modules',
        '.pytest_cache',
        '.mypy_cache',
        'build',
        'dist',
        '*.egg-info'
    }
    
    ARCHIVOS_EXCLUIDOS = {
        'test.py',
        'validar_dia8.py',
        '.env.py',
        'generar_estructura.bat',
        'validar_vulnerabilidades_alto.py',  # Excluir el propio script
        'validar_seguridad.sh'
    }
    
    PATRONES_EXCLUIDOS = {
        'test_*.py',
        '*_test.py',
        'setup.py',
        'conftest.py'
    }
    
    def __init__(self, ruta_raiz: str = "."):
        self.ruta_raiz = Path(ruta_raiz)
        self.resultados = []
        self.vulnerabilidades_encontradas = 0
        self.vulnerabilidades_corregidas = 0
        self.archivos_con_problemas = {}  # {archivo: [lista de problemas]}
        self.archivos_seguros = set()
        self.archivos_excluidos_count = 0
        self.carpetas_excluidas_count = 0
        
        # Cargar configuración de exclusiones si existe
        self._cargar_configuracion_exclusiones()
    
    def _cargar_configuracion_exclusiones(self):
        """Carga configuración de exclusiones desde archivo si existe"""
        archivo_config = self.ruta_raiz / "exclusiones.conf"
        
        if not archivo_config.exists():
            return
        
        try:
            import configparser
            config = configparser.ConfigParser()
            config.read(archivo_config, encoding='utf-8')
            
            # Cargar carpetas excluidas adicionales
            if 'carpetas_excluidas' in config:
                carpetas_adicionales = [
                    linea.strip() 
                    for linea in config['carpetas_excluidas'] 
                    if linea.strip() and not linea.strip().startswith('#')
                ]
                self.CARPETAS_EXCLUIDAS.update(carpetas_adicionales)
            
            # Cargar archivos excluidos adicionales
            if 'archivos_excluidos' in config:
                archivos_adicionales = [
                    linea.strip() 
                    for linea in config['archivos_excluidos'] 
                    if linea.strip() and not linea.strip().startswith('#')
                ]
                self.ARCHIVOS_EXCLUIDOS.update(archivos_adicionales)
            
            # Cargar patrones excluidos adicionales
            if 'patrones_excluidos' in config:
                patrones_adicionales = [
                    linea.strip() 
                    for linea in config['patrones_excluidos'] 
                    if linea.strip() and not linea.strip().startswith('#')
                ]
                self.PATRONES_EXCLUIDOS.update(patrones_adicionales)
            
            self.log(f"✓ Configuración cargada desde: {archivo_config}", "SUCCESS")
            
        except Exception as e:
            self.log(f"⚠️  Error cargando configuración: {e}", "WARNING")
            self.log("Usando configuración por defecto", "INFO")
    
    def log(self, mensaje: str, nivel: str = "INFO"):
        """Registra mensajes con formato"""
        colores = {
            "INFO": "\033[94m",
            "SUCCESS": "\033[92m",
            "WARNING": "\033[93m",
            "ERROR": "\033[91m",
            "RESET": "\033[0m"
        }
        color = colores.get(nivel, colores["INFO"])
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"{color}[{timestamp}] [{nivel}] {mensaje}{colores['RESET']}")
    
    def obtener_archivos_a_analizar(self, patron: str) -> List[Path]:
        """Obtiene lista de archivos a analizar, excluyendo los configurados"""
        archivos = []
        carpetas_ya_contadas = set()
        archivos_escaneados = 0
        archivos_filtrados = 0
        
        for archivo in self.ruta_raiz.rglob(patron):
            archivos_escaneados += 1
            
            # Normalizar ruta para Windows/Linux
            ruta_str = str(archivo.absolute()).replace('\\', '/')
            
            # Debug: primeros archivos
            if archivos_escaneados <= 5:
                self.log(f"   Escaneando: {ruta_str}", "INFO")
            
            # Verificar si está en carpeta excluida
            excluir = False
            carpeta_excluida = None
            
            for carpeta in self.CARPETAS_EXCLUIDAS:
                # Buscar el nombre de carpeta en la ruta completa
                # Usar separador / después de normalizar
                if f'/{carpeta}/' in ruta_str or ruta_str.startswith(f'{carpeta}/'):
                    excluir = True
                    carpeta_excluida = carpeta
                    archivos_filtrados += 1
                    break
                # También verificar al final de la ruta
                ruta_parts = ruta_str.split('/')
                if carpeta in ruta_parts:
                    excluir = True
                    carpeta_excluida = carpeta
                    archivos_filtrados += 1
                    break
            
            if excluir and carpeta_excluida:
                # Contar la carpeta solo una vez
                if carpeta_excluida not in carpetas_ya_contadas:
                    self.carpetas_excluidas_count += 1
                    carpetas_ya_contadas.add(carpeta_excluida)
                continue  # Saltar este archivo
            
            # Verificar nombre de archivo excluido
            if archivo.name in self.ARCHIVOS_EXCLUIDOS:
                self.archivos_excluidos_count += 1
                archivos_filtrados += 1
                continue
            
            # Verificar patrones
            from fnmatch import fnmatch
            patron_coincide = False
            for patron_excl in self.PATRONES_EXCLUIDOS:
                if fnmatch(archivo.name, patron_excl):
                    self.archivos_excluidos_count += 1
                    archivos_filtrados += 1
                    patron_coincide = True
                    break
            
            if patron_coincide:
                continue
            
            # Si llegamos aquí, el archivo debe analizarse
            archivos.append(archivo)
        
        self.log(f"   Total escaneados: {archivos_escaneados}, Filtrados: {archivos_filtrados}, A analizar: {len(archivos)}", "INFO")
        
        return archivos
    
    def agregar_resultado(self, categoria: str, archivo: str, linea: int, 
                         estado: str, detalle: str = ""):
        """Agrega un resultado de validación"""
        self.resultados.append({
            "categoria": categoria,
            "archivo": archivo,
            "linea": linea,
            "estado": estado,
            "detalle": detalle,
            "timestamp": datetime.now().isoformat()
        })
        
        if estado == "VULNERABLE":
            self.vulnerabilidades_encontradas += 1
            # Rastrear archivos con problemas
            if archivo not in self.archivos_con_problemas:
                self.archivos_con_problemas[archivo] = []
            self.archivos_con_problemas[archivo].append({
                'linea': linea,
                'categoria': categoria,
                'detalle': detalle
            })
        elif estado == "CORREGIDO":
            self.vulnerabilidades_corregidas += 1
            # Marcar archivo como procesado
            if archivo not in self.archivos_con_problemas:
                self.archivos_seguros.add(archivo)

    # =========================================================================
    # VALIDACIÓN 1: CWE-117 - Unvalidated untrusted input in log
    # =========================================================================
    def validar_logs_seguros(self) -> int:
        """
        Valida que no se registren datos no sanitizados en logs
        Total esperado: 29 vulnerabilidades
        """
        self.log("🔍 Validando CWE-117: Logs con datos no sanitizados...", "INFO")
        encontradas = 0
        
        # Patrones peligrosos en logs
        patrones_peligrosos = [
            (r'logger\.(info|debug|warning|error|critical)\([^)]*\{[^}]*request\.(form|args|json|data)', 
             "Datos de request directos en log"),
            (r'logger\.(info|debug|warning|error|critical)\([^)]*f["\'].*\{(username|password|email|cedula|identificacion)',
             "Datos sensibles sin sanitizar en log"),
            (r'logger\.(info|debug|warning|error|critical)\([^)]*\{session\[',
             "Datos de sesión sin sanitizar en log"),
        ]
        
        archivos_python = self.obtener_archivos_a_analizar("*.py")
        
        for archivo in archivos_python:
            try:
                with open(archivo, 'r', encoding='utf-8', errors='ignore') as f:
                    lineas = f.readlines()
                    for num_linea, linea in enumerate(lineas, 1):
                        for patron, descripcion in patrones_peligrosos:
                            if re.search(patron, linea):
                                # Verificar si usa funciones de sanitización
                                if 'sanitizar_' in linea or 'sanitize_' in linea:
                                    self.agregar_resultado(
                                        "CWE-117: Log Injection",
                                        str(archivo.relative_to(self.ruta_raiz)),
                                        num_linea,
                                        "CORREGIDO",
                                        f"Usa sanitización: {descripcion}"
                                    )
                                else:
                                    self.agregar_resultado(
                                        "CWE-117: Log Injection",
                                        str(archivo.relative_to(self.ruta_raiz)),
                                        num_linea,
                                        "VULNERABLE",
                                        descripcion
                                    )
                                    encontradas += 1
            except Exception as e:
                self.log(f"Error procesando {archivo}: {e}", "WARNING")
                
        self.log(f"✓ CWE-117: {encontradas} vulnerabilidades encontradas", 
                "WARNING" if encontradas > 0 else "SUCCESS")
        return encontradas

    # =========================================================================
    # VALIDACIÓN 2: CWE-209 - Sensitive information in error messages
    # =========================================================================
    def validar_mensajes_error(self) -> int:
        """
        Valida que no se expongan detalles técnicos en mensajes de error
        Total esperado: 256 vulnerabilidades
        """
        self.log("🔍 Validando CWE-209: Información sensible en errores...", "INFO")
        encontradas = 0
        
        # Patrones de exposición de información sensible
        patrones = [
            (r'print\s*\(\s*f?["\'].*\{e\}', "Excepción completa en print()"),
            (r'logger\.(error|warning)\s*\([^)]*\{e\}', "Excepción en log sin sanitizar"),
            (r'logger\.(error|warning)\s*\([^)]*\{str\(e\)\}', "str(e) en log"),
            (r'traceback\.(print_exc|format_exc)\(\)', "Stack trace expuesto"),
        ]
        
        archivos_python = self.obtener_archivos_a_analizar("*.py")
        
        for archivo in archivos_python:
            try:
                with open(archivo, 'r', encoding='utf-8', errors='ignore') as f:
                    lineas = f.readlines()
                    for num_linea, linea in enumerate(lineas, 1):
                        for patron, descripcion in patrones:
                            if re.search(patron, linea):
                                # Verificar si está en bloque try/except apropiado
                                # y si hay sanitización
                                if 'exc_info=True' in linea:
                                    estado = "VULNERABLE"
                                    detalle = f"{descripcion} - exc_info expone detalles"
                                    encontradas += 1
                                elif re.search(r'print\s*\(\s*f?["\'].*\{e\}', linea):
                                    estado = "VULNERABLE"
                                    detalle = f"{descripcion} - Usar logger en lugar de print"
                                    encontradas += 1
                                else:
                                    # Verificar contexto
                                    estado = "REVISAR"
                                    detalle = descripcion
                                    
                                self.agregar_resultado(
                                    "CWE-209: Information Exposure",
                                    str(archivo.relative_to(self.ruta_raiz)),
                                    num_linea,
                                    estado,
                                    detalle
                                )
            except Exception as e:
                self.log(f"Error procesando {archivo}: {e}", "WARNING")
                
        self.log(f"✓ CWE-209: {encontradas} vulnerabilidades encontradas", 
                "WARNING" if encontradas > 0 else "SUCCESS")
        return encontradas

    # =========================================================================
    # VALIDACIÓN 3: CWE-698 - Execution After Redirect (EAR)
    # =========================================================================
    def validar_execution_after_redirect(self) -> int:
        """
        Valida que después de redirect() se use return
        Total esperado: 93 vulnerabilidades
        """
        self.log("🔍 Validando CWE-698: Execution After Redirect...", "INFO")
        encontradas = 0
        
        archivos_python = self.obtener_archivos_a_analizar("*.py")
        
        for archivo in archivos_python:
            try:
                with open(archivo, 'r', encoding='utf-8', errors='ignore') as f:
                    lineas = f.readlines()
                    for num_linea, linea in enumerate(lineas, 1):
                        # Buscar líneas con redirect
                        if 'redirect(' in linea and 'return' not in linea:
                            # Verificar que no sea parte de un return en otra línea
                            linea_siguiente = lineas[num_linea] if num_linea < len(lineas) else ""
                            
                            if 'return' not in linea_siguiente:
                                self.agregar_resultado(
                                    "CWE-698: Execution After Redirect",
                                    str(archivo.relative_to(self.ruta_raiz)),
                                    num_linea,
                                    "VULNERABLE",
                                    "redirect() sin return - código puede ejecutarse después"
                                )
                                encontradas += 1
                            else:
                                self.agregar_resultado(
                                    "CWE-698: Execution After Redirect",
                                    str(archivo.relative_to(self.ruta_raiz)),
                                    num_linea,
                                    "CORREGIDO",
                                    "return después de redirect"
                                )
            except Exception as e:
                self.log(f"Error procesando {archivo}: {e}", "WARNING")
                
        self.log(f"✓ CWE-698: {encontradas} vulnerabilidades encontradas", 
                "WARNING" if encontradas > 0 else "SUCCESS")
        return encontradas

    # =========================================================================
    # VALIDACIÓN 4: CWE-525 - Autocomplete en campos sensibles
    # =========================================================================
    def validar_autocomplete_sensible(self) -> int:
        """
        Valida que campos de contraseña tengan autocomplete="off"
        Total esperado: 11 vulnerabilidades
        """
        self.log("🔍 Validando CWE-525: Autocomplete en campos sensibles...", "INFO")
        encontradas = 0
        
        archivos_html = self.obtener_archivos_a_analizar("*.html")
        
        for archivo in archivos_html:
            try:
                with open(archivo, 'r', encoding='utf-8', errors='ignore') as f:
                    contenido = f.read()
                    lineas = contenido.split('\n')
                    
                    for num_linea, linea in enumerate(lineas, 1):
                        # Buscar inputs de contraseña y datos sensibles
                        if re.search(r'<input[^>]*type=["\']password["\']', linea):
                            if 'autocomplete="off"' not in linea and 'autocomplete="new-password"' not in linea:
                                self.agregar_resultado(
                                    "CWE-525: Autocomplete Enabled",
                                    str(archivo.relative_to(self.ruta_raiz)),
                                    num_linea,
                                    "VULNERABLE",
                                    "Campo password sin autocomplete='off'"
                                )
                                encontradas += 1
                            else:
                                self.agregar_resultado(
                                    "CWE-525: Autocomplete Enabled",
                                    str(archivo.relative_to(self.ruta_raiz)),
                                    num_linea,
                                    "CORREGIDO",
                                    "Campo password con autocomplete deshabilitado"
                                )
                                
                        # También validar campos de email, username, etc.
                        campos_sensibles = ['email', 'username', 'cedula', 'identificacion']
                        for campo in campos_sensibles:
                            if re.search(rf'<input[^>]*name=["\'][^"\']*{campo}[^"\']*["\']', linea, re.IGNORECASE):
                                if 'autocomplete="off"' not in linea:
                                    self.agregar_resultado(
                                        "CWE-525: Autocomplete Enabled",
                                        str(archivo.relative_to(self.ruta_raiz)),
                                        num_linea,
                                        "VULNERABLE",
                                        f"Campo {campo} sin autocomplete='off'"
                                    )
                                    encontradas += 1
            except Exception as e:
                self.log(f"Error procesando {archivo}: {e}", "WARNING")
                
        self.log(f"✓ CWE-525: {encontradas} vulnerabilidades encontradas", 
                "WARNING" if encontradas > 0 else "SUCCESS")
        return encontradas

    # =========================================================================
    # VALIDACIÓN 5: CWE-200 - IPs hardcodeadas
    # =========================================================================
    def validar_ips_hardcodeadas(self) -> int:
        """
        Valida que no haya IPs hardcodeadas en el código
        Total esperado: 3 vulnerabilidades
        """
        self.log("🔍 Validando CWE-200: IPs hardcodeadas...", "INFO")
        encontradas = 0
        
        # Patrón para detectar IPs
        patron_ip = r'\b(?:\d{1,3}\.){3}\d{1,3}\b'
        
        archivos_python = self.obtener_archivos_a_analizar("*.py")
        
        for archivo in archivos_python:
            try:
                with open(archivo, 'r', encoding='utf-8', errors='ignore') as f:
                    lineas = f.readlines()
                    for num_linea, linea in enumerate(lineas, 1):
                        # Buscar IPs, pero ignorar 127.0.0.1 y 0.0.0.0
                        ips = re.findall(patron_ip, linea)
                        for ip in ips:
                            if ip not in ['127.0.0.1', '0.0.0.0', '255.255.255.255']:
                                # Verificar si usa variable de entorno
                                if 'os.getenv' in linea or 'os.environ' in linea:
                                    self.agregar_resultado(
                                        "CWE-200: Hardcoded IP",
                                        str(archivo.relative_to(self.ruta_raiz)),
                                        num_linea,
                                        "CORREGIDO",
                                        f"IP {ip} cargada desde variable de entorno"
                                    )
                                else:
                                    self.agregar_resultado(
                                        "CWE-200: Hardcoded IP",
                                        str(archivo.relative_to(self.ruta_raiz)),
                                        num_linea,
                                        "VULNERABLE",
                                        f"IP hardcodeada: {ip} - Usar variable de entorno"
                                    )
                                    encontradas += 1
            except Exception as e:
                self.log(f"Error procesando {archivo}: {e}", "WARNING")
                
        self.log(f"✓ CWE-200: {encontradas} vulnerabilidades encontradas", 
                "WARNING" if encontradas > 0 else "SUCCESS")
        return encontradas

    # =========================================================================
    # VALIDACIÓN 6: CWE-1022 - target="_blank" sin rel="noopener"
    # =========================================================================
    def validar_target_blank(self) -> int:
        """
        Valida que links con target="_blank" tengan rel="noopener noreferrer"
        Total esperado: 3 vulnerabilidades
        """
        self.log("🔍 Validando CWE-1022: target='_blank' sin protección...", "INFO")
        encontradas = 0
        
        archivos_html = self.obtener_archivos_a_analizar("*.html")
        
        for archivo in archivos_html:
            try:
                with open(archivo, 'r', encoding='utf-8', errors='ignore') as f:
                    lineas = f.readlines()
                    for num_linea, linea in enumerate(lineas, 1):
                        if 'target="_blank"' in linea or "target='_blank'" in linea:
                            if 'rel="noopener' not in linea and "rel='noopener" not in linea:
                                self.agregar_resultado(
                                    "CWE-1022: Tabnabbing",
                                    str(archivo.relative_to(self.ruta_raiz)),
                                    num_linea,
                                    "VULNERABLE",
                                    'target="_blank" sin rel="noopener noreferrer"'
                                )
                                encontradas += 1
                            else:
                                self.agregar_resultado(
                                    "CWE-1022: Tabnabbing",
                                    str(archivo.relative_to(self.ruta_raiz)),
                                    num_linea,
                                    "CORREGIDO",
                                    'target="_blank" con rel="noopener noreferrer"'
                                )
            except Exception as e:
                self.log(f"Error procesando {archivo}: {e}", "WARNING")
                
        self.log(f"✓ CWE-1022: {encontradas} vulnerabilidades encontradas", 
                "WARNING" if encontradas > 0 else "SUCCESS")
        return encontradas

    # =========================================================================
    # VALIDACIÓN 7: CWE-601 - Open Redirect
    # =========================================================================
    def validar_open_redirect(self) -> int:
        """
        Valida redirecciones no validadas
        Total esperado: 3 vulnerabilidades (2 JS, 1 Python)
        """
        self.log("🔍 Validando CWE-601: Open Redirect...", "INFO")
        encontradas = 0
        
        # Python
        archivos_python = self.obtener_archivos_a_analizar("*.py")
        for archivo in archivos_python:
            try:
                with open(archivo, 'r', encoding='utf-8', errors='ignore') as f:
                    lineas = f.readlines()
                    for num_linea, linea in enumerate(lineas, 1):
                        # Buscar redirects con parámetros de request
                        if 'redirect(' in linea and ('request.args' in linea or 'request.form' in linea):
                            # Verificar si hay validación
                            if 'url_for' not in linea and 'validate' not in linea.lower():
                                self.agregar_resultado(
                                    "CWE-601: Open Redirect",
                                    str(archivo.relative_to(self.ruta_raiz)),
                                    num_linea,
                                    "VULNERABLE",
                                    "Redirect con input no validado (Python)"
                                )
                                encontradas += 1
            except Exception as e:
                self.log(f"Error procesando {archivo}: {e}", "WARNING")
        
        # JavaScript - también incluir archivos .js además de .html
        archivos_js = self.obtener_archivos_a_analizar("*.js")
        for archivo in archivos_js:
            try:
                with open(archivo, 'r', encoding='utf-8', errors='ignore') as f:
                    lineas = f.readlines()
                    for num_linea, linea in enumerate(lineas, 1):
                        if 'window.location' in linea or 'location.href' in linea:
                            # Verificar si usa variables no validadas
                            if re.search(r'(window\.location|location\.href)\s*=\s*[^"\';]+', linea):
                                self.agregar_resultado(
                                    "CWE-601: Open Redirect",
                                    str(archivo.relative_to(self.ruta_raiz)),
                                    num_linea,
                                    "VULNERABLE",
                                    "Redirect con input no validado (JavaScript)"
                                )
                                encontradas += 1
            except Exception as e:
                self.log(f"Error procesando {archivo}: {e}", "WARNING")
        
        # También buscar en HTML para JavaScript embebido
        archivos_html = self.obtener_archivos_a_analizar("*.html")
        for archivo in archivos_html:
            try:
                with open(archivo, 'r', encoding='utf-8', errors='ignore') as f:
                    lineas = f.readlines()
                    for num_linea, linea in enumerate(lineas, 1):
                        if 'window.location' in linea or 'location.href' in linea:
                            # Verificar si usa variables no validadas
                            if re.search(r'(window\.location|location\.href)\s*=\s*[^"\';]+', linea):
                                self.agregar_resultado(
                                    "CWE-601: Open Redirect",
                                    str(archivo.relative_to(self.ruta_raiz)),
                                    num_linea,
                                    "VULNERABLE",
                                    "Redirect con input no validado (JavaScript en HTML)"
                                )
                                encontradas += 1
            except Exception as e:
                self.log(f"Error procesando {archivo}: {e}", "WARNING")
                
        self.log(f"✓ CWE-601: {encontradas} vulnerabilidades encontradas", 
                "WARNING" if encontradas > 0 else "SUCCESS")
        return encontradas

    # =========================================================================
    # VALIDACIÓN 8: CWE-311 - Transporte inseguro
    # =========================================================================
    def validar_transporte_inseguro(self) -> int:
        """
        Valida uso de HTTPS/TLS en servidores y conexiones
        Total esperado: 2 vulnerabilidades
        """
        self.log("🔍 Validando CWE-311: Transporte inseguro...", "INFO")
        encontradas = 0
        
        archivos_python = self.obtener_archivos_a_analizar("*.py")
        
        for archivo in archivos_python:
            try:
                with open(archivo, 'r', encoding='utf-8', errors='ignore') as f:
                    lineas = f.readlines()
                    for num_linea, linea in enumerate(lineas, 1):
                        # Buscar app.run sin SSL
                        if 'app.run(' in linea:
                            # Verificar las siguientes líneas para ver configuración SSL
                            bloque = ''.join(lineas[num_linea-1:num_linea+5])
                            if 'ssl_context' not in bloque and 'certfile' not in bloque:
                                self.agregar_resultado(
                                    "CWE-311: Insecure Transport",
                                    str(archivo.relative_to(self.ruta_raiz)),
                                    num_linea,
                                    "VULNERABLE",
                                    "Servidor HTTP sin SSL/TLS - Usar HTTPS en producción"
                                )
                                encontradas += 1
                        
                        # Buscar SMTP sin TLS
                        if 'smtplib.SMTP(' in linea and 'starttls' not in linea:
                            # Revisar contexto
                            bloque = ''.join(lineas[max(0,num_linea-3):min(len(lineas),num_linea+3)])
                            if 'starttls()' not in bloque and 'SMTP_SSL' not in bloque:
                                self.agregar_resultado(
                                    "CWE-311: Insecure Transport",
                                    str(archivo.relative_to(self.ruta_raiz)),
                                    num_linea,
                                    "VULNERABLE",
                                    "SMTP sin TLS - Usar starttls() o SMTP_SSL"
                                )
                                encontradas += 1
            except Exception as e:
                self.log(f"Error procesando {archivo}: {e}", "WARNING")
                
        self.log(f"✓ CWE-311: {encontradas} vulnerabilidades encontradas", 
                "WARNING" if encontradas > 0 else "SUCCESS")
        return encontradas

    # =========================================================================
    # EJECUCIÓN PRINCIPAL
    # =========================================================================
    def ejecutar_validacion_completa(self):
        """Ejecuta todas las validaciones y genera reporte"""
        self.log("="*70, "INFO")
        self.log("VALIDACIÓN DE VULNERABILIDADES DE ALTO RIESGO - SUGIPQ-V1", "INFO")
        self.log("="*70, "INFO")
        self.log(f"Ruta raíz: {self.ruta_raiz.absolute()}", "INFO")
        self.log("", "INFO")
        
        # Detectar y mostrar carpetas que se van a excluir
        carpetas_encontradas = set()
        for archivo in self.ruta_raiz.rglob("*"):
            if archivo.is_file():
                ruta_str = str(archivo).replace('\\', '/')
                partes = ruta_str.split('/')
                for parte in partes:
                    if parte in self.CARPETAS_EXCLUIDAS:
                        carpetas_encontradas.add(parte)
        
        if carpetas_encontradas:
            self.log("✅ Carpetas detectadas que serán excluidas:", "SUCCESS")
            for carpeta in sorted(carpetas_encontradas):
                self.log(f"   🚫 {carpeta}", "WARNING")
            self.log("", "INFO")
        
        # Mostrar configuración de exclusiones
        self.log("📋 Configuración de Exclusiones:", "INFO")
        self.log(f"   Carpetas excluidas: {', '.join(sorted(self.CARPETAS_EXCLUIDAS))}", "INFO")
        self.log(f"   Archivos excluidos: {', '.join(sorted(self.ARCHIVOS_EXCLUIDOS))}", "INFO")
        self.log("", "INFO")
        
        total_vulnerabilidades = 0
        
        # Ejecutar todas las validaciones
        validaciones = [
            ("CWE-117: Log Injection", self.validar_logs_seguros),
            ("CWE-209: Info Exposure in Errors", self.validar_mensajes_error),
            ("CWE-698: Execution After Redirect", self.validar_execution_after_redirect),
            ("CWE-525: Autocomplete Enabled", self.validar_autocomplete_sensible),
            ("CWE-200: Hardcoded IPs", self.validar_ips_hardcodeadas),
            ("CWE-1022: Tabnabbing", self.validar_target_blank),
            ("CWE-601: Open Redirect", self.validar_open_redirect),
            ("CWE-311: Insecure Transport", self.validar_transporte_inseguro),
        ]
        
        for nombre, validacion in validaciones:
            try:
                encontradas = validacion()
                total_vulnerabilidades += encontradas
                self.log("", "INFO")
            except Exception as e:
                self.log(f"❌ Error en validación {nombre}: {e}", "ERROR")
        
        # Resumen final
        self.log("="*70, "INFO")
        self.log("RESUMEN DE VALIDACIÓN", "INFO")
        self.log("="*70, "INFO")
        self.log(f"Total vulnerabilidades encontradas: {self.vulnerabilidades_encontradas}", 
                "ERROR" if self.vulnerabilidades_encontradas > 0 else "SUCCESS")
        self.log(f"Total vulnerabilidades corregidas: {self.vulnerabilidades_corregidas}", "SUCCESS")
        self.log(f"Total validaciones realizadas: {len(self.resultados)}", "INFO")
        self.log(f"Archivos analizados: {len(self.archivos_con_problemas) + len(self.archivos_seguros)}", "INFO")
        self.log(f"Archivos excluidos del análisis: {self.archivos_excluidos_count}", "INFO")
        self.log(f"Carpetas excluidas del análisis: {self.carpetas_excluidas_count}", "INFO")
        
        # Mostrar tabla de archivos problemáticos
        if self.archivos_con_problemas:
            self.generar_tabla_archivos_problematicos()
        
        # Mostrar resumen detallado de archivos
        self.imprimir_resumen_archivos()
        
        # Generar reporte JSON
        self.generar_reporte_json()
        
        # Generar reporte HTML
        self.generar_reporte_html()
        
        return self.vulnerabilidades_encontradas == 0

    def imprimir_resumen_archivos(self):
        """Imprime un resumen detallado de archivos con problemas"""
        if not self.archivos_con_problemas:
            self.log("✅ ¡Excelente! No se encontraron archivos con vulnerabilidades", "SUCCESS")
            return
        
        self.log("", "INFO")
        self.log("="*70, "ERROR")
        self.log("📁 ARCHIVOS CON VULNERABILIDADES DETECTADAS", "ERROR")
        self.log("="*70, "ERROR")
        self.log("", "INFO")
        
        # Ordenar archivos por cantidad de problemas (de mayor a menor)
        archivos_ordenados = sorted(
            self.archivos_con_problemas.items(),
            key=lambda x: len(x[1]),
            reverse=True
        )
        
        for idx, (archivo, problemas) in enumerate(archivos_ordenados, 1):
            # Encabezado del archivo
            self.log(f"\n{idx}. 📄 {archivo}", "ERROR")
            self.log(f"   {'─' * 65}", "ERROR")
            self.log(f"   Total de vulnerabilidades: {len(problemas)}", "WARNING")
            self.log("", "INFO")
            
            # Agrupar por categoría
            categorias = {}
            for problema in problemas:
                cat = problema['categoria']
                if cat not in categorias:
                    categorias[cat] = []
                categorias[cat].append(problema)
            
            # Mostrar por categoría
            for categoria, items in categorias.items():
                self.log(f"   🔸 {categoria} ({len(items)} ocurrencia(s))", "WARNING")
                
                # Mostrar primeras 5 ocurrencias
                for item in items[:5]:
                    self.log(f"      • Línea {item['linea']}: {item['detalle']}", "INFO")
                
                if len(items) > 5:
                    self.log(f"      ... y {len(items) - 5} más", "INFO")
                
                self.log("", "INFO")
        
        # Resumen final
        self.log("="*70, "ERROR")
        self.log(f"Total de archivos afectados: {len(self.archivos_con_problemas)}", "ERROR")
        self.log(f"Total de vulnerabilidades: {self.vulnerabilidades_encontradas}", "ERROR")
        self.log("="*70, "ERROR")
        
        # Sugerencia de acción
        self.log("", "INFO")
        self.log("💡 PRÓXIMOS PASOS:", "WARNING")
        self.log("   1. Revisar el archivo HTML generado para más detalles", "INFO")
        self.log("   2. Consultar GUIA_CORRECCION_VULNERABILIDADES.md", "INFO")
        self.log("   3. Priorizar archivos con más vulnerabilidades", "INFO")
        self.log("", "INFO")
    
    def generar_tabla_archivos_problematicos(self):
        """Genera una tabla ASCII con los archivos problemáticos"""
        if not self.archivos_con_problemas:
            return
        
        self.log("", "INFO")
        self.log("┌─────────────────────────────────────────────────────────────────────┐", "WARNING")
        self.log("│                    TOP 10 ARCHIVOS CRÍTICOS                        │", "WARNING")
        self.log("├─────┬───────────────────────────────────────────────────┬──────────┤", "WARNING")
        self.log("│ #   │ Archivo                                           │ Problemas│", "WARNING")
        self.log("├─────┼───────────────────────────────────────────────────┼──────────┤", "WARNING")
        
        archivos_ordenados = sorted(
            self.archivos_con_problemas.items(),
            key=lambda x: len(x[1]),
            reverse=True
        )[:10]
        
        for idx, (archivo, problemas) in enumerate(archivos_ordenados, 1):
            # Truncar nombre de archivo si es muy largo
            nombre_corto = archivo if len(archivo) <= 45 else "..." + archivo[-42:]
            self.log(f"│ {idx:<3} │ {nombre_corto:<45} │ {len(problemas):^8} │", "WARNING")
        
        self.log("└─────┴───────────────────────────────────────────────────┴──────────┘", "WARNING")
        self.log("", "INFO")

    def generar_reporte_json(self):
        """Genera reporte en formato JSON"""
        
        # Preparar resumen de archivos
        archivos_resumen = []
        for archivo, problemas in self.archivos_con_problemas.items():
            categorias_count = {}
            for p in problemas:
                cat = p['categoria'].split(':')[0]  # Extraer solo el CWE
                categorias_count[cat] = categorias_count.get(cat, 0) + 1
            
            archivos_resumen.append({
                'archivo': archivo,
                'total_vulnerabilidades': len(problemas),
                'vulnerabilidades_por_categoria': categorias_count,
                'lineas_afectadas': sorted(set([p['linea'] for p in problemas]))
            })
        
        # Ordenar por cantidad de problemas
        archivos_resumen.sort(key=lambda x: x['total_vulnerabilidades'], reverse=True)
        
        reporte = {
            "fecha_validacion": datetime.now().isoformat(),
            "ruta_raiz": str(self.ruta_raiz.absolute()),
            "configuracion": {
                "carpetas_excluidas": sorted(list(self.CARPETAS_EXCLUIDAS)),
                "archivos_excluidos": sorted(list(self.ARCHIVOS_EXCLUIDOS)),
                "patrones_excluidos": sorted(list(self.PATRONES_EXCLUIDOS))
            },
            "resumen": {
                "total_vulnerabilidades_encontradas": self.vulnerabilidades_encontradas,
                "total_vulnerabilidades_corregidas": self.vulnerabilidades_corregidas,
                "total_validaciones": len(self.resultados),
                "archivos_afectados": len(self.archivos_con_problemas),
                "archivos_seguros": len(self.archivos_seguros),
                "archivos_excluidos": self.archivos_excluidos_count,
                "carpetas_excluidas": self.carpetas_excluidas_count
            },
            "archivos_problematicos": archivos_resumen,
            "resultados_detallados": self.resultados
        }
        
        archivo_json = self.ruta_raiz / "reporte_vulnerabilidades_alto.json"
        with open(archivo_json, 'w', encoding='utf-8') as f:
            json.dump(reporte, f, indent=2, ensure_ascii=False)
        
        self.log(f"✓ Reporte JSON generado: {archivo_json}", "SUCCESS")

    def generar_reporte_html(self):
        """Genera reporte en formato HTML"""
        
        # Preparar datos de archivos problemáticos
        archivos_criticos_html = ""
        if self.archivos_con_problemas:
            archivos_ordenados = sorted(
                self.archivos_con_problemas.items(),
                key=lambda x: len(x[1]),
                reverse=True
            )[:10]  # Top 10
            
            for idx, (archivo, problemas) in enumerate(archivos_ordenados, 1):
                # Determinar color según severidad
                if len(problemas) > 10:
                    color_class = "critico"
                elif len(problemas) > 5:
                    color_class = "alto"
                else:
                    color_class = "medio"
                
                archivos_criticos_html += f"""
                <div class="archivo-card {color_class}">
                    <div class="archivo-header">
                        <span class="archivo-numero">{idx}</span>
                        <span class="archivo-nombre">{archivo}</span>
                        <span class="archivo-count">{len(problemas)} problema(s)</span>
                    </div>
                    <div class="archivo-lineas">
                        Líneas afectadas: {', '.join(map(str, sorted(set([p['linea'] for p in problemas]))[:10]))}
                        {' ...' if len(set([p['linea'] for p in problemas])) > 10 else ''}
                    </div>
                </div>
                """
        
        html = f"""
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Reporte de Vulnerabilidades - SUGIPQ-V1</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        .container {{
            max-width: 1400px;
            margin: 0 auto;
            background-color: white;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        h1 {{
            color: #333;
            border-bottom: 3px solid #007bff;
            padding-bottom: 10px;
        }}
        h2 {{
            color: #495057;
            margin-top: 30px;
            border-left: 4px solid #007bff;
            padding-left: 15px;
        }}
        .resumen {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin: 20px 0;
        }}
        .stat-card {{
            padding: 20px;
            border-radius: 8px;
            text-align: center;
        }}
        .stat-card.vulnerable {{
            background-color: #f8d7da;
            border-left: 4px solid #dc3545;
        }}
        .stat-card.corregido {{
            background-color: #d4edda;
            border-left: 4px solid #28a745;
        }}
        .stat-card.total {{
            background-color: #d1ecf1;
            border-left: 4px solid #17a2b8;
        }}
        .stat-card.archivos {{
            background-color: #fff3cd;
            border-left: 4px solid #ffc107;
        }}
        .stat-number {{
            font-size: 36px;
            font-weight: bold;
            margin: 10px 0;
        }}
        .stat-label {{
            font-size: 14px;
            color: #666;
        }}
        
        /* Sección de archivos críticos */
        .archivos-criticos {{
            margin: 30px 0;
            padding: 20px;
            background-color: #fff8e1;
            border-radius: 8px;
            border-left: 5px solid #ff9800;
        }}
        .archivo-card {{
            margin: 15px 0;
            padding: 15px;
            border-radius: 6px;
            border-left: 4px solid #666;
        }}
        .archivo-card.critico {{
            background-color: #ffebee;
            border-left-color: #d32f2f;
        }}
        .archivo-card.alto {{
            background-color: #fff3e0;
            border-left-color: #f57c00;
        }}
        .archivo-card.medio {{
            background-color: #fff9c4;
            border-left-color: #fbc02d;
        }}
        .archivo-header {{
            display: flex;
            align-items: center;
            gap: 15px;
            margin-bottom: 8px;
        }}
        .archivo-numero {{
            background-color: #333;
            color: white;
            width: 30px;
            height: 30px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: bold;
            font-size: 14px;
        }}
        .archivo-nombre {{
            flex: 1;
            font-family: 'Courier New', monospace;
            font-weight: bold;
            color: #333;
        }}
        .archivo-count {{
            background-color: #dc3545;
            color: white;
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: bold;
        }}
        .archivo-lineas {{
            font-size: 13px;
            color: #666;
            font-family: 'Courier New', monospace;
            padding-left: 45px;
        }}
        
        /* Tabla de resultados */
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
        }}
        th {{
            background-color: #007bff;
            color: white;
            padding: 12px;
            text-align: left;
            position: sticky;
            top: 0;
            z-index: 10;
        }}
        td {{
            padding: 10px;
            border-bottom: 1px solid #ddd;
        }}
        tr:hover {{
            background-color: #f5f5f5;
        }}
        .badge {{
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 12px;
            font-weight: bold;
        }}
        .badge.vulnerable {{
            background-color: #dc3545;
            color: white;
        }}
        .badge.corregido {{
            background-color: #28a745;
            color: white;
        }}
        .badge.revisar {{
            background-color: #ffc107;
            color: black;
        }}
        .timestamp {{
            color: #666;
            font-size: 12px;
            text-align: right;
            margin-top: 20px;
        }}
        
        /* Filtros */
        .filtros {{
            margin: 20px 0;
            padding: 15px;
            background-color: #e9ecef;
            border-radius: 6px;
        }}
        .filtro-btn {{
            padding: 8px 16px;
            margin: 5px;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 14px;
        }}
        .filtro-btn.active {{
            background-color: #007bff;
            color: white;
        }}
        .filtro-btn:not(.active) {{
            background-color: white;
            color: #333;
        }}
        
        /* Búsqueda */
        .busqueda {{
            margin: 20px 0;
        }}
        .busqueda input {{
            width: 100%;
            padding: 10px;
            border: 2px solid #ddd;
            border-radius: 4px;
            font-size: 14px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🔒 Reporte de Validación de Vulnerabilidades de Alto Riesgo</h1>
        <p><strong>Aplicación:</strong> SUGIPQ-V1</p>
        <p><strong>Fecha de validación:</strong> {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
        
        <div style="background-color: #e7f3ff; padding: 15px; border-radius: 6px; margin: 20px 0; border-left: 4px solid #2196F3;">
            <h3 style="margin-top: 0; color: #1976D2;">ℹ️ Configuración del Análisis</h3>
            <p><strong>Carpetas excluidas:</strong> {', '.join(sorted(self.CARPETAS_EXCLUIDAS))}</p>
            <p><strong>Archivos excluidos:</strong> {', '.join(sorted(self.ARCHIVOS_EXCLUIDOS))}</p>
            <p style="margin-bottom: 0;"><strong>Total archivos omitidos:</strong> {self.archivos_excluidos_count}</p>
        </div>
        
        <div class="resumen">
            <div class="stat-card vulnerable">
                <div class="stat-label">Vulnerabilidades Encontradas</div>
                <div class="stat-number">{self.vulnerabilidades_encontradas}</div>
            </div>
            <div class="stat-card corregido">
                <div class="stat-label">Vulnerabilidades Corregidas</div>
                <div class="stat-number">{self.vulnerabilidades_corregidas}</div>
            </div>
            <div class="stat-card archivos">
                <div class="stat-label">Archivos Afectados</div>
                <div class="stat-number">{len(self.archivos_con_problemas)}</div>
            </div>
            <div class="stat-card total">
                <div class="stat-label">Total Validaciones</div>
                <div class="stat-number">{len(self.resultados)}</div>
            </div>
        </div>
        
        {f'''
        <div class="archivos-criticos">
            <h2>⚠️ Top 10 Archivos Críticos</h2>
            <p style="margin-bottom: 20px; color: #666;">Estos archivos requieren atención prioritaria por tener múltiples vulnerabilidades.</p>
            {archivos_criticos_html}
        </div>
        ''' if self.archivos_con_problemas else '<div class="stat-card corregido"><h2>✅ ¡Excelente! No hay archivos con vulnerabilidades</h2></div>'}
        
        <h2>📋 Detalle Completo de Resultados</h2>
        
        <div class="busqueda">
            <input type="text" id="buscarArchivo" placeholder="🔍 Buscar por archivo o categoría..." onkeyup="filtrarTabla()">
        </div>
        
        <div class="filtros">
            <strong>Filtrar por estado:</strong>
            <button class="filtro-btn active" onclick="filtrarEstado('todos')">Todos</button>
            <button class="filtro-btn" onclick="filtrarEstado('vulnerable')">Vulnerables</button>
            <button class="filtro-btn" onclick="filtrarEstado('corregido')">Corregidos</button>
            <button class="filtro-btn" onclick="filtrarEstado('revisar')">A Revisar</button>
        </div>
        
        <table id="tablaResultados">
            <thead>
                <tr>
                    <th>Categoría</th>
                    <th>Archivo</th>
                    <th>Línea</th>
                    <th>Estado</th>
                    <th>Detalle</th>
                </tr>
            </thead>
            <tbody>
"""

        for resultado in self.resultados:
            badge_class = resultado['estado'].lower().replace(' ', '_')
            html += f"""
                <tr class="fila-resultado" data-estado="{resultado['estado'].lower()}">
                    <td>{resultado['categoria']}</td>
                    <td><code>{resultado['archivo']}</code></td>
                    <td><strong>{resultado['linea']}</strong></td>
                    <td><span class="badge {badge_class}">{resultado['estado']}</span></td>
                    <td>{resultado['detalle']}</td>
                </tr>
"""

        html += """
            </tbody>
        </table>
        
        <div class="timestamp">
            Reporte generado automáticamente por el Sistema de Validación de Seguridad
        </div>
    </div>
    
    <script>
        function filtrarEstado(estado) {
            // Actualizar botones activos
            document.querySelectorAll('.filtro-btn').forEach(btn => {
                btn.classList.remove('active');
            });
            event.target.classList.add('active');
            
            // Filtrar filas
            const filas = document.querySelectorAll('.fila-resultado');
            filas.forEach(fila => {
                if (estado === 'todos') {
                    fila.style.display = '';
                } else {
                    const estadoFila = fila.getAttribute('data-estado');
                    fila.style.display = estadoFila === estado ? '' : 'none';
                }
            });
        }
        
        function filtrarTabla() {
            const input = document.getElementById('buscarArchivo');
            const filtro = input.value.toUpperCase();
            const tabla = document.getElementById('tablaResultados');
            const filas = tabla.getElementsByTagName('tr');
            
            for (let i = 1; i < filas.length; i++) {
                const fila = filas[i];
                const textoFila = fila.textContent || fila.innerText;
                
                if (textoFila.toUpperCase().indexOf(filtro) > -1) {
                    fila.style.display = '';
                } else {
                    fila.style.display = 'none';
                }
            }
        }
    </script>
</body>
</html>
"""

        archivo_html = self.ruta_raiz / "reporte_vulnerabilidades_alto.html"
        with open(archivo_html, 'w', encoding='utf-8') as f:
            f.write(html)

        self.log(f"✓ Reporte HTML generado: {archivo_html}", "SUCCESS")


def main():
    """Función principal"""
    import argparse

    parser = argparse.ArgumentParser(
        description='Validador de vulnerabilidades de alto riesgo para SUGIPQ-V1'
    )
    parser.add_argument(
        '--ruta',
        default='.',
        help='Ruta raíz del proyecto (por defecto: directorio actual)'
    )

    args = parser.parse_args()

    validador = ValidadorVulnerabilidades(args.ruta)

    try:
        resultado = validador.ejecutar_validacion_completa()
        sys.exit(0 if resultado else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Validación interrumpida por el usuario")
        sys.exit(2)
    except Exception as e:
        print(f"\n❌ Error fatal: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(3)


if __name__ == "__main__":
    main()