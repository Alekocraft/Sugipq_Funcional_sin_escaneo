#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DIAGNÓSTICO COMPLETO DE ENDPOINTS DE ESTADÍSTICAS
==================================================
Script para identificar por qué Material POP e Inventario Corporativo
no cargan datos en el dashboard mientras que Préstamos sí funciona.

Ejecutar: python diagnostico_dashboard.py
"""

import sys
import os

# Agregar el directorio del proyecto al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("=" * 80)
print("DIAGNÓSTICO DE ENDPOINTS DE ESTADÍSTICAS - Dashboard SUGIPQ")
print("=" * 80)
print()

# ==============================================================================
# PASO 1: Verificar importaciones
# ==============================================================================
print("📦 PASO 1: Verificando importaciones básicas...")
print("-" * 80)

try:
    from flask import Flask, session, jsonify
    print("✅ Flask importado correctamente")
except ImportError as e:
    print(f"❌ Error importando Flask: {e}")
    sys.exit(1)

try:
    from config.database import get_db_connection
    print("✅ Módulo database importado correctamente")
except ImportError as e:
    print(f"❌ Error importando database: {e}")
    print("   Verifica que existe: config/database.py")

try:
    from models.materiales_model import MaterialModel
    print("✅ MaterialModel importado correctamente")
except ImportError as e:
    print(f"❌ Error importando MaterialModel: {e}")
    print("   Verifica que existe: models/materiales_model.py")

try:
    from models.inventario_corporativo_model import InventarioCorporativoModel
    print("✅ InventarioCorporativoModel importado correctamente")
except ImportError as e:
    print(f"❌ Error importando InventarioCorporativoModel: {e}")
    print("   Verifica que existe: models/inventario_corporativo_model.py")

print()

# ==============================================================================
# PASO 2: Verificar blueprints registrados
# ==============================================================================
print("📋 PASO 2: Verificando blueprints registrados en la app...")
print("-" * 80)

try:
    from app import app
    print("✅ App Flask importada correctamente")
    print()
    
    print("Blueprints registrados:")
    for blueprint_name, blueprint in app.blueprints.items():
        url_prefix = blueprint.url_prefix or '/'
        print(f"  ✓ {blueprint_name:30s} → {url_prefix}")
    
    print()
    
    # Verificar blueprints críticos
    required_blueprints = {
        'materiales': '/materiales',
        'inventario_corporativo': '/inventario-corporativo',
        'prestamos': '/prestamos'
    }
    
    print("Verificando blueprints requeridos:")
    for bp_name, expected_prefix in required_blueprints.items():
        if bp_name in app.blueprints:
            actual_prefix = app.blueprints[bp_name].url_prefix
            if actual_prefix == expected_prefix:
                print(f"  ✅ {bp_name}: {actual_prefix}")
            else:
                print(f"  ⚠️  {bp_name}: esperado {expected_prefix}, encontrado {actual_prefix}")
        else:
            print(f"  ❌ {bp_name}: NO REGISTRADO")
    
except ImportError as e:
    print(f"❌ Error importando app: {e}")
    print("   No se puede continuar sin la app")
    sys.exit(1)

print()

# ==============================================================================
# PASO 3: Verificar rutas específicas
# ==============================================================================
print("🛣️  PASO 3: Verificando rutas de API de estadísticas...")
print("-" * 80)

routes_to_check = [
    '/materiales/api/estadisticas-dashboard',
    '/inventario-corporativo/api/estadisticas-dashboard',
    '/prestamos/api/estadisticas-dashboard'
]

print("Rutas registradas que contienen 'estadisticas':")
for rule in app.url_map.iter_rules():
    if 'estadisticas' in rule.rule.lower():
        methods = ', '.join(rule.methods - {'HEAD', 'OPTIONS'})
        print(f"  ✓ {rule.rule:50s} [{methods:10s}] → {rule.endpoint}")

print()
print("Verificando rutas específicas:")
for route in routes_to_check:
    found = False
    for rule in app.url_map.iter_rules():
        if rule.rule == route:
            found = True
            methods = ', '.join(rule.methods - {'HEAD', 'OPTIONS'})
            print(f"  ✅ {route:60s} [{methods}]")
            break
    if not found:
        print(f"  ❌ {route:60s} [NO ENCONTRADA]")

print()

# ==============================================================================
# PASO 4: Test de conexión a base de datos
# ==============================================================================
print("🗄️  PASO 4: Verificando conexión a base de datos...")
print("-" * 80)

try:
    conn = get_db_connection()
    if conn:
        print("✅ Conexión a base de datos establecida")
        cursor = conn.cursor()
        
        # Test query simple
        cursor.execute("SELECT @@VERSION")
        version = cursor.fetchone()
        print(f"   SQL Server Version: {version[0][:50]}...")
        
        cursor.close()
        conn.close()
    else:
        print("❌ No se pudo establecer conexión a la base de datos")
except Exception as e:
    print(f"❌ Error conectando a base de datos: {e}")

print()

# ==============================================================================
# PASO 5: Test de endpoints con requests simulados
# ==============================================================================
print("🧪 PASO 5: Testeando endpoints con contexto de Flask...")
print("-" * 80)

def test_endpoint(endpoint_path, endpoint_name):
    """Testear un endpoint específico"""
    print(f"\nTesteando: {endpoint_name}")
    print(f"URL: {endpoint_path}")
    
    with app.test_client() as client:
        # Simular sesión de usuario
        with client.session_transaction() as sess:
            sess['usuario_id'] = 1
            sess['usuario_nombre'] = 'admin'
            sess['rol'] = 'administrador'
            sess['oficina_id'] = 1
            sess['oficina_nombre'] = 'COQ'
        
        try:
            response = client.get(endpoint_path)
            
            print(f"  Status Code: {response.status_code}")
            
            if response.status_code == 200:
                try:
                    data = response.get_json()
                    print(f"  ✅ Respuesta JSON válida")
                    print(f"  Datos retornados:")
                    for key, value in data.items():
                        print(f"    - {key}: {value}")
                    return True
                except Exception as e:
                    print(f"  ❌ Error parseando JSON: {e}")
                    print(f"  Respuesta raw: {response.data[:200]}")
                    return False
            elif response.status_code == 404:
                print(f"  ❌ Endpoint NO ENCONTRADO (404)")
                print(f"  Verifica que la ruta esté correctamente registrada")
                return False
            elif response.status_code == 500:
                print(f"  ❌ Error interno del servidor (500)")
                print(f"  Respuesta: {response.data[:200]}")
                return False
            else:
                print(f"  ⚠️  Status inesperado: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"  ❌ Error ejecutando request: {e}")
            import traceback
            traceback.print_exc()
            return False

# Testear los 3 endpoints
results = {}
results['materiales'] = test_endpoint(
    '/materiales/api/estadisticas-dashboard',
    'Material POP'
)

results['inventario'] = test_endpoint(
    '/inventario-corporativo/api/estadisticas-dashboard',
    'Inventario Corporativo'
)

results['prestamos'] = test_endpoint(
    '/prestamos/api/estadisticas-dashboard',
    'Préstamos'
)

print()

# ==============================================================================
# PASO 6: Verificar que los modelos funcionen
# ==============================================================================
print("🔍 PASO 6: Verificando que los modelos puedan obtener datos...")
print("-" * 80)

print("\nMaterial POP (MaterialModel):")
try:
    materiales = MaterialModel.obtener_todos()
    if materiales:
        print(f"  ✅ MaterialModel.obtener_todos() retorna {len(materiales)} materiales")
    else:
        print(f"  ⚠️  MaterialModel.obtener_todos() retorna lista vacía o None")
except Exception as e:
    print(f"  ❌ Error llamando MaterialModel.obtener_todos(): {e}")
    import traceback
    traceback.print_exc()

print("\nInventario Corporativo (InventarioCorporativoModel):")
try:
    inventario = InventarioCorporativoModel.obtener_todos()
    if inventario:
        print(f"  ✅ InventarioCorporativoModel.obtener_todos() retorna {len(inventario)} productos")
    else:
        print(f"  ⚠️  InventarioCorporativoModel.obtener_todos() retorna lista vacía o None")
except Exception as e:
    print(f"  ❌ Error llamando InventarioCorporativoModel.obtener_todos(): {e}")
    import traceback
    traceback.print_exc()

print()

# ==============================================================================
# PASO 7: Verificar archivos de blueprints
# ==============================================================================
print("📁 PASO 7: Verificando archivos de blueprints...")
print("-" * 80)

files_to_check = [
    ('routes/materiales.py', 'Blueprint de materiales'),
    ('routes/inventario_corporativo.py', 'Blueprint de inventario'),
    ('routes/prestamos.py', 'Blueprint de préstamos'),
]

for filepath, description in files_to_check:
    if os.path.exists(filepath):
        print(f"  ✅ {description:40s} → {filepath}")
        
        # Verificar que contenga la ruta de API
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            if 'api/estadisticas-dashboard' in content:
                print(f"     ✓ Contiene ruta 'api/estadisticas-dashboard'")
            else:
                print(f"     ⚠️  NO contiene ruta 'api/estadisticas-dashboard'")
    else:
        print(f"  ❌ {description:40s} → {filepath} NO EXISTE")

print()

# ==============================================================================
# RESUMEN FINAL
# ==============================================================================
print("=" * 80)
print("📊 RESUMEN DEL DIAGNÓSTICO")
print("=" * 80)
print()

print("Resultados de tests de endpoints:")
for endpoint_name, success in results.items():
    status = "✅ FUNCIONA" if success else "❌ FALLA"
    print(f"  {endpoint_name:20s}: {status}")

print()
print("DIAGNÓSTICO COMPLETADO")
print("=" * 80)

# Sugerencias basadas en resultados
print()
print("💡 SUGERENCIAS:")
print()

if not results['materiales']:
    print("❌ Material POP NO funciona:")
    print("   1. Verifica que el blueprint 'materiales' esté registrado en app.py")
    print("   2. Verifica que existe routes/materiales.py")
    print("   3. Verifica que la ruta '/api/estadisticas-dashboard' esté definida")
    print("   4. Revisa los logs de Flask para errores al cargar el blueprint")
    print()

if not results['inventario']:
    print("❌ Inventario Corporativo NO funciona:")
    print("   1. Verifica que el blueprint 'inventario_corporativo' esté registrado")
    print("   2. Verifica que existe routes/inventario_corporativo.py")
    print("   3. Verifica que la ruta '/api/estadisticas-dashboard' esté definida")
    print("   4. Revisa los logs de Flask para errores al cargar el blueprint")
    print()

if results['prestamos'] and not (results['materiales'] or results['inventario']):
    print("⚠️  PATRÓN DETECTADO:")
    print("   Préstamos funciona pero Material POP e Inventario no.")
    print("   Posibles causas:")
    print("   - Los blueprints no están registrados en app.py")
    print("   - Los archivos tienen errores de sintaxis que impiden su carga")
    print("   - Las rutas están definidas con nombre diferente")
    print()

if all(results.values()):
    print("✅ TODOS LOS ENDPOINTS FUNCIONAN")
    print("   El problema puede estar en:")
    print("   - El JavaScript del dashboard.html no se está ejecutando")
    print("   - Hay un error en la consola del navegador (F12)")
    print("   - Las URLs en el fetch() no coinciden con las rutas")
    print()
    print("   Próximo paso: Revisar F12 → Console en el navegador")

print()
print("Para más información, revisa los logs de Flask mientras ejecutas este script.")
print()