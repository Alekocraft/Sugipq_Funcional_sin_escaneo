#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para encontrar caracteres no UTF-8 en archivos Python y HTML.
"""

import os
import sys
import argparse
from pathlib import Path

def es_caracter_utf8_valido(byte_sequence):
    """
    Verifica si una secuencia de bytes es válida en UTF-8.
    """
    try:
        byte_sequence.decode('utf-8')
        return True
    except UnicodeDecodeError:
        return False

def buscar_caracteres_no_utf8_en_archivo(ruta_archivo):
    """
    Busca caracteres no UTF-8 en un archivo y devuelve las líneas problemáticas.
    """
    problemas = []
    
    try:
        # Intentar leer como UTF-8 primero
        with open(ruta_archivo, 'r', encoding='utf-8') as f:
            lineas = f.readlines()
    except UnicodeDecodeError:
        # Si falla, leer como bytes y analizar línea por línea
        try:
            with open(ruta_archivo, 'rb') as f:
                contenido = f.read()
                
            # Convertir a líneas manteniendo los bytes
            lineas_bytes = contenido.split(b'\n')
            
            for num_linea, linea_bytes in enumerate(lineas_bytes, 1):
                if not es_caracter_utf8_valido(linea_bytes):
                    # Decodificar lo que se pueda para mostrar contexto
                    try:
                        contexto = linea_bytes.decode('utf-8', errors='replace')
                    except:
                        contexto = "[Contenido binario no decodificable]"
                    
                    problemas.append({
                        'linea': num_linea,
                        'contenido': contexto,
                        'bytes_problematicos': linea_bytes
                    })
                    
        except Exception as e:
            problemas.append({
                'linea': 0,
                'contenido': f"Error al leer archivo: {e}",
                'bytes_problematicos': b''
            })
    
    return problemas

def buscar_en_carpeta(carpeta, extensiones=None):
    """
    Busca archivos con extensiones específicas en una carpeta y sus subcarpetas.
    """
    if extensiones is None:
        extensiones = ['.py', '.html', '.htm']
    
    archivos = []
    carpeta_path = Path(carpeta)
    
    for ext in extensiones:
        archivos.extend(carpeta_path.rglob(f'*{ext}'))
    
    return archivos

def mostrar_problemas(ruta_archivo, problemas):
    """
    Muestra los problemas encontrados en un formato legible.
    """
    if problemas:
        print(f"\n{'='*80}")
        print(f"ARCHIVO: {ruta_archivo}")
        print(f"{'='*80}")
        
        for problema in problemas:
            print(f"\nLínea {problema['linea']}:")
            print(f"Contenido: {problema['contenido'][:100]}...")
            
            # Mostrar bytes problemáticos en formato hexadecimal
            if problema['bytes_problematicos']:
                bytes_hex = problema['bytes_problematicos'].hex()
                print(f"Bytes (hex): {bytes_hex[:50]}...")
            
            print(f"{'-'*40}")

def main():
    parser = argparse.ArgumentParser(
        description='Buscar caracteres no UTF-8 en archivos Python y HTML.'
    )
    parser.add_argument(
        'carpeta',
        nargs='?',
        default='.',
        help='Carpeta donde buscar (por defecto: carpeta actual)'
    )
    parser.add_argument(
        '--extensiones',
        nargs='+',
        default=['.py', '.html', '.htm'],
        help='Extensiones de archivo a buscar (por defecto: .py .html .htm)'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Mostrar archivos que sí son válidos UTF-8'
    )
    
    args = parser.parse_args()
    
    carpeta = args.carpeta
    
    if not os.path.exists(carpeta):
        print(f"Error: La carpeta '{carpeta}' no existe.")
        sys.exit(1)
    
    print(f"Buscando archivos en: {os.path.abspath(carpeta)}")
    print(f"Extensiones buscadas: {', '.join(args.extensiones)}")
    print(f"{'='*80}")
    
    archivos = buscar_en_carpeta(carpeta, args.extensiones)
    
    if not archivos:
        print("No se encontraron archivos con las extensiones especificadas.")
        sys.exit(0)
    
    print(f"Se encontraron {len(archivos)} archivos para analizar.")
    
    archivos_con_problemas = 0
    archivos_analizados = 0
    
    for archivo_path in archivos:
        try:
            problemas = buscar_caracteres_no_utf8_en_archivo(archivo_path)
            archivos_analizados += 1
            
            if problemas:
                archivos_con_problemas += 1
                mostrar_problemas(archivo_path, problemas)
            elif args.verbose:
                print(f"✓ {archivo_path} - OK")
                
        except Exception as e:
            print(f"\nError al procesar {archivo_path}: {e}")
    
    print(f"\n{'='*80}")
    print("RESUMEN:")
    print(f"  Archivos analizados: {archivos_analizados}")
    print(f"  Archivos con problemas UTF-8: {archivos_con_problemas}")
    print(f"  Archivos correctos: {archivos_analizados - archivos_con_problemas}")
    
    if archivos_con_problemas > 0:
        print(f"\n¡Se encontraron problemas en {archivos_con_problemas} archivo(s)!")
        return 1
    else:
        print(f"\n¡Todos los archivos son válidos UTF-8!")
        return 0

if __name__ == "__main__":
    sys.exit(main())