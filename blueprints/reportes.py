"""
BLUEPRINT DE REPORTES - VersiÃƒÂ³n mejorada con filtros avanzados
Integra la funcionalidad original con la estructura actual del sistema
"""

from flask import Blueprint, render_template, request, redirect, session, flash, url_for, jsonify, send_file
from io import BytesIO
import pandas as pd
from datetime import datetime, timedelta
from models.solicitudes_model import SolicitudModel
from models.materiales_model import MaterialModel
from models.oficinas_model import OficinaModel
from models.prestamos_model import PrestamosModel
from models.novedades_model import NovedadModel
from utils.permissions import can_access, get_office_filter
from utils.filters import filtrar_por_oficina_usuario

# Crear blueprint de reportes
reportes_bp = Blueprint('reportes', __name__, url_prefix='/reportes')

# Helpers de autenticaciÃƒÂ³n locales
def _require_login():
    return 'usuario_id' in session

# Helper para aplicar filtros segÃƒÂºn permisos
def aplicar_filtro_permisos(datos, campo_oficina='oficina_id'):
    """
    Aplica filtro de oficina segÃƒÂºn permisos del usuario
    """
    if not datos:
        return []
    
    # Si puede ver todo (administrador/lider_inventario), no filtra
    if can_access('materiales', 'view') and can_access('solicitudes', 'view'):
        return datos
    
    # Para otros roles, filtrar por su oficina
    oficina_usuario = session.get('oficina_id')
    if not oficina_usuario:
        return []
    
    # Filtrar datos por oficina
    datos_filtrados = []
    for item in datos:
        if isinstance(item, dict):
            if item.get(campo_oficina) == oficina_usuario:
                datos_filtrados.append(item)
        else:
            # Si es objeto, verificar atributo
            if hasattr(item, campo_oficina):
                if getattr(item, campo_oficina) == oficina_usuario:
                    datos_filtrados.append(item)
    
    return datos_filtrados

# ============================================================================
# RUTAS DE REPORTES
# ============================================================================

# PÃƒÂ¡gina principal de reportes
@reportes_bp.route('/')
def reportes_index():
    """PÃƒÂ¡gina principal de reportes"""
    if not _require_login():
        return redirect('/login')
    
    return render_template('reportes/index.html')

# ================================
# REPORTE DE SOLICITUDES  
# ===============================

@reportes_bp.route('/solicitudes')
def reporte_solicitudes():
    """Reporte de solicitudes con filtros avanzados - VERSIÃƒâ€œN CORREGIDA"""
    if not _require_login():
        return redirect('/login')
    
    # Verificar permisos
    if not can_access('solicitudes', 'view'):
        flash('No tiene permisos para ver reportes de solicitudes', 'warning')
        return redirect('/reportes')
    
    try:
        # Obtener parÃƒÂ¡metros de filtro
        filtro_estado = request.args.get('estado', 'todos')
        filtro_oficina = request.args.get('oficina', 'todas')
        filtro_material = request.args.get('material', '').strip()
        filtro_solicitante = request.args.get('solicitante', '').strip()
        filtro_fecha_inicio = request.args.get('fecha_inicio', '')
        filtro_fecha_fin = request.args.get('fecha_fin', '')
        
        # Obtener todas las solicitudes con detalle
        solicitudes = SolicitudModel.obtener_todas_con_detalle() or []
        
        # Aplicar filtro segÃƒÂºn permisos del usuario
        if not (session.get('rol') in ['administrador', 'lider_inventario']):
            solicitudes = filtrar_por_oficina_usuario(solicitudes, 'oficina_id')
        
        # Aplicar filtros adicionales
        solicitudes_filtradas = []
        for solicitud in solicitudes:
            # Filtro por estado
            if filtro_estado != 'todos':
                estado_solicitud = solicitud.get('estado', '').lower()
                estado_filtro = filtro_estado.lower()
                # CORRECCIÃƒâ€œN: Mejor comparaciÃƒÂ³n de estados
                if estado_filtro == 'pendiente' and 'pendiente' not in estado_solicitud:
                    continue
                elif estado_filtro == 'aprobada' and 'aprobada' not in estado_solicitud:
                    continue
                elif estado_filtro == 'rechazada' and 'rechazada' not in estado_solicitud:
                    continue
                elif estado_filtro == 'parcial' and 'parcial' not in estado_solicitud:
                    continue
                elif estado_filtro == 'completada' and 'completada' not in estado_solicitud:
                    continue
                elif estado_filtro == 'devuelta' and 'devuelta' not in estado_solicitud:
                    continue
            
            # Filtro por oficina - CORRECCIÃƒâ€œN: Usar ID en lugar de nombre
            if filtro_oficina != 'todas':
                oficina_solicitud_id = solicitud.get('oficina_id')
                # Intentar convertir ambos a string para comparaciÃƒÂ³n
                if str(oficina_solicitud_id) != str(filtro_oficina):
                    continue
            
            # Filtro por material (bÃƒÂºsqueda por parte del nombre) - CORRECCIÃƒâ€œN
            if filtro_material:
                material_nombre = str(solicitud.get('material_nombre', '')).lower()
                material_filtro = filtro_material.lower().strip()
                if material_filtro not in material_nombre:
                    continue
            
            # Filtro por solicitante (bÃƒÂºsqueda por parte del nombre) - CORRECCIÃƒâ€œN
            if filtro_solicitante:
                solicitante = str(solicitud.get('usuario_solicitante', '')).lower()
                solicitante_filtro = filtro_solicitante.lower().strip()
                if solicitante_filtro not in solicitante:
                    continue
            
            # Filtro por fecha
            if filtro_fecha_inicio:
                try:
                    fecha_solicitud_str = solicitud.get('fecha_solicitud', '')
                    if fecha_solicitud_str:
                        # Manejar diferentes formatos de fecha
                        if isinstance(fecha_solicitud_str, str):
                            fecha_solicitud = datetime.strptime(str(fecha_solicitud_str).split()[0], '%Y-%m-%d').date()
                        else:
                            fecha_solicitud = fecha_solicitud_str.date()
                        
                        fecha_inicio = datetime.strptime(filtro_fecha_inicio, '%Y-%m-%d').date()
                        if fecha_solicitud < fecha_inicio:
                            continue
                except Exception as e:
                    print(f"Ã¢Å¡Â Ã¯Â¸Â Error procesando fecha inicio: {e}")
                    continue
            
            if filtro_fecha_fin:
                try:
                    fecha_solicitud_str = solicitud.get('fecha_solicitud', '')
                    if fecha_solicitud_str:
                        # Manejar diferentes formatos de fecha
                        if isinstance(fecha_solicitud_str, str):
                            fecha_solicitud = datetime.strptime(str(fecha_solicitud_str).split()[0], '%Y-%m-%d').date()
                        else:
                            fecha_solicitud = fecha_solicitud_str.date()
                        
                        fecha_fin = datetime.strptime(filtro_fecha_fin, '%Y-%m-%d').date()
                        if fecha_solicitud > fecha_fin:
                            continue
                except Exception as e:
                    print(f"Ã¢Å¡Â Ã¯Â¸Â Error procesando fecha fin: {e}")
                    continue
            
            solicitudes_filtradas.append(solicitud)
        
        # Calcular estadÃƒÂ­sticas
        estados = {
            'pendiente': 0, 
            'aprobada': 0, 
            'rechazada': 0, 
            'parcial': 0, 
            'completada': 0, 
            'devuelta': 0
        }
        
        total_cantidad_solicitada = 0
        total_cantidad_entregada = 0
        
        for solicitud in solicitudes_filtradas:
            estado = solicitud.get('estado', 'pendiente').lower()
            if 'pendiente' in estado:
                estados['pendiente'] += 1
            elif 'aprobada' in estado:
                estados['aprobada'] += 1
            elif 'rechazada' in estado:
                estados['rechazada'] += 1
            elif 'parcial' in estado:
                estados['parcial'] += 1
            elif 'completada' in estado:
                estados['completada'] += 1
            elif 'devuelta' in estado:
                estados['devuelta'] += 1
            
            total_cantidad_solicitada += solicitud.get('cantidad_solicitada', 0)
            total_cantidad_entregada += solicitud.get('cantidad_entregada', 0)
        
        # Obtener listas para filtros
        oficinas = OficinaModel.obtener_todas() or []
        materiales = MaterialModel.obtener_todos() or []
        nombres_materiales = list(set([m.get('nombre', '') for m in materiales]))
        
        # Calcular tasa de aprobaciÃƒÂ³n
        total_solicitudes = len(solicitudes_filtradas)
        tasa_aprobacion = 0
        if total_solicitudes > 0:
            aprobadas_totales = estados['aprobada'] + estados['completada'] + estados['parcial']
            tasa_aprobacion = round((aprobadas_totales / total_solicitudes) * 100, 1)
        
        print(f"Ã°Å¸â€Â REPORTE SOLICITUDES - FILTROS APLICADOS:")
        print(f"   Filtro oficina: {filtro_oficina}")
        print(f"   Filtro material: {filtro_material}")
        print(f"   Filtro solicitante: {filtro_solicitante}")
        print(f"   Solicitudes encontradas: {len(solicitudes_filtradas)}")
        
        return render_template('reportes/solicitudes.html',
                             solicitudes=solicitudes_filtradas,
                             filtro_estado=filtro_estado,
                             filtro_oficina=filtro_oficina,
                             filtro_material=filtro_material,
                             filtro_solicitante=filtro_solicitante,
                             filtro_fecha_inicio=filtro_fecha_inicio,
                             filtro_fecha_fin=filtro_fecha_fin,
                             oficinas=oficinas,
                             nombres_materiales=nombres_materiales,
                             total_solicitudes=total_solicitudes,
                             pendientes=estados['pendiente'],
                             aprobadas=estados['aprobada'],
                             rechazadas=estados['rechazada'],
                             parciales=estados['parcial'],
                             completadas=estados['completada'],
                             devueltas=estados['devuelta'],
                             total_cantidad_solicitada=total_cantidad_solicitada,
                             total_cantidad_entregada=total_cantidad_entregada,
                             tasa_aprobacion=tasa_aprobacion)
                             
    except Exception as e:
        print(f"Ã¢ÂÅ’ Error generando reporte de solicitudes: {e}")
        import traceback
        traceback.print_exc()
        flash('Error al generar el reporte de solicitudes', 'danger')
        return render_template('reportes/solicitudes.html',
                             solicitudes=[],
                             oficinas=[],
                             nombres_materiales=[],
                             total_solicitudes=0,
                             pendientes=0,
                             aprobadas=0,
                             rechazadas=0,
                             parciales=0,
                             completadas=0,
                             devueltas=0)

# ----------------------------------
# EXPORTACIÃƒâ€œN DE SOLICITUDES A EXCEL
# ----------------------------------

@reportes_bp.route('/solicitudes/exportar/excel')
def exportar_solicitudes_excel():
    """Exporta las solicitudes filtradas a Excel - VERSIÃƒâ€œN CORREGIDA"""
    if not _require_login():
        return redirect('/login')
    
    # Verificar permisos
    if not can_access('solicitudes', 'view'):
        flash('No tiene permisos para exportar reportes de solicitudes', 'warning')
        return redirect('/reportes')
    
    try:
        # Obtener mismos filtros que en la vista
        filtro_estado = request.args.get('estado', 'todos')
        filtro_oficina = request.args.get('oficina', 'todas')
        filtro_material = request.args.get('material', '').strip()
        filtro_solicitante = request.args.get('solicitante', '').strip()
        filtro_fecha_inicio = request.args.get('fecha_inicio', '')
        filtro_fecha_fin = request.args.get('fecha_fin', '')
        
        # Obtener datos
        solicitudes = SolicitudModel.obtener_todas_con_detalle() or []
        
        # Aplicar filtro segÃƒÂºn permisos
        if not (session.get('rol') in ['administrador', 'lider_inventario']):
            solicitudes = filtrar_por_oficina_usuario(solicitudes, 'oficina_id')
        
        # Aplicar filtros adicionales (USANDO LA MISMA LÃƒâ€œGICA CORREGIDA)
        solicitudes_filtradas = []
        for solicitud in solicitudes:
            # Filtro por estado
            if filtro_estado != 'todos':
                estado_solicitud = solicitud.get('estado', '').lower()
                estado_filtro = filtro_estado.lower()
                # CORRECCIÃƒâ€œN: Mejor comparaciÃƒÂ³n de estados
                if estado_filtro == 'pendiente' and 'pendiente' not in estado_solicitud:
                    continue
                elif estado_filtro == 'aprobada' and 'aprobada' not in estado_solicitud:
                    continue
                elif estado_filtro == 'rechazada' and 'rechazada' not in estado_solicitud:
                    continue
                elif estado_filtro == 'parcial' and 'parcial' not in estado_solicitud:
                    continue
                elif estado_filtro == 'completada' and 'completada' not in estado_solicitud:
                    continue
                elif estado_filtro == 'devuelta' and 'devuelta' not in estado_solicitud:
                    continue
            
            # Filtro por oficina - CORRECCIÃƒâ€œN
            if filtro_oficina != 'todas':
                oficina_solicitud_id = solicitud.get('oficina_id')
                if str(oficina_solicitud_id) != str(filtro_oficina):
                    continue
            
            # Filtro por material - CORRECCIÃƒâ€œN
            if filtro_material:
                material_nombre = str(solicitud.get('material_nombre', '')).lower()
                material_filtro = filtro_material.lower().strip()
                if material_filtro not in material_nombre:
                    continue
            
            # Filtro por solicitante - CORRECCIÃƒâ€œN
            if filtro_solicitante:
                solicitante = str(solicitud.get('usuario_solicitante', '')).lower()
                solicitante_filtro = filtro_solicitante.lower().strip()
                if solicitante_filtro not in solicitante:
                    continue
            
            # Filtro por fecha
            if filtro_fecha_inicio:
                try:
                    fecha_solicitud_str = solicitud.get('fecha_solicitud', '')
                    if fecha_solicitud_str:
                        if isinstance(fecha_solicitud_str, str):
                            fecha_solicitud = datetime.strptime(str(fecha_solicitud_str).split()[0], '%Y-%m-%d').date()
                        else:
                            fecha_solicitud = fecha_solicitud_str.date()
                        
                        fecha_inicio = datetime.strptime(filtro_fecha_inicio, '%Y-%m-%d').date()
                        if fecha_solicitud < fecha_inicio:
                            continue
                except:
                    continue
            
            if filtro_fecha_fin:
                try:
                    fecha_solicitud_str = solicitud.get('fecha_solicitud', '')
                    if fecha_solicitud_str:
                        if isinstance(fecha_solicitud_str, str):
                            fecha_solicitud = datetime.strptime(str(fecha_solicitud_str).split()[0], '%Y-%m-%d').date()
                        else:
                            fecha_solicitud = fecha_solicitud_str.date()
                        
                        fecha_fin = datetime.strptime(filtro_fecha_fin, '%Y-%m-%d').date()
                        if fecha_solicitud > fecha_fin:
                            continue
                except:
                    continue
            
            solicitudes_filtradas.append(solicitud)
        
        # Preparar datos para Excel
        data = []
        for sol in solicitudes_filtradas:
            data.append({
                'ID': sol.get('id', ''),
                'Material': sol.get('material_nombre', ''),
                'Cantidad Solicitada': sol.get('cantidad_solicitada', 0),
                'Cantidad Entregada': sol.get('cantidad_entregada', 0),
                'Solicitante': sol.get('usuario_solicitante', ''),
                'Oficina': sol.get('oficina_nombre', ''),
                'Estado': sol.get('estado', ''),
                'Fecha Solicitud': sol.get('fecha_solicitud', ''),
                'Fecha AprobaciÃƒÂ³n': sol.get('fecha_aprobacion', ''),
                'Observaciones': sol.get('observacion', ''),
                'Usuario Aprobador': sol.get('usuario_aprobador', ''),
                'Stock Actual Material': sol.get('cantidad_disponible', '')
            })

        df = pd.DataFrame(data)
        
        # Crear archivo Excel en memoria
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Solicitudes', index=False)
            
            # Ajustar ancho de columnas
            worksheet = writer.sheets['Solicitudes']
            for column in worksheet.columns:
                max_length = 0
                column_letter = column[0].column_letter
                for cell in column:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
                adjusted_width = min(max_length + 2, 50)
                worksheet.column_dimensions[column_letter].width = adjusted_width
            
            # Agregar hoja de resumen
            summary_data = {
                'Resumen': [
                    f'Total Solicitudes: {len(solicitudes_filtradas)}',
                    f'Filtro Estado: {filtro_estado if filtro_estado != "todos" else "Todos"}',
                    f'Filtro Oficina: {filtro_oficina if filtro_oficina != "todas" else "Todas"}',
                    f'Filtro Material: {filtro_material if filtro_material else "Ninguno"}',
                    f'Filtro Solicitante: {filtro_solicitante if filtro_solicitante else "Ninguno"}',
                    f'Fecha GeneraciÃƒÂ³n: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'
                ]
            }
            df_summary = pd.DataFrame(summary_data)
            df_summary.to_excel(writer, sheet_name='Resumen', index=False)
        
        output.seek(0)

        # Crear nombre de archivo
        fecha_actual = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'reporte_solicitudes_{fecha_actual}.xlsx'

        return send_file(output,
                         mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                         as_attachment=True,
                         download_name=filename)
                         
    except Exception as e:
        print(f"Ã¢ÂÅ’ Error exportando solicitudes a Excel: {e}")
        flash('Error al exportar el reporte de solicitudes a Excel', 'danger')
        return redirect('/reportes/solicitudes')

# ============================================================================
# OTROS REPORTES
# ============================================================================

@reportes_bp.route('/materiales')
def reporte_materiales():
    """Reporte de materiales"""
    if not _require_login():
        return redirect('/login')
    
    if not can_access('materiales', 'view'):
        flash('No tiene permisos para ver reportes de materiales', 'warning')
        return redirect('/reportes')
    
    try:
        materiales = MaterialModel.obtener_todos() or []
        
        # Aplicar filtro segÃƒÂºn permisos
        if not (session.get('rol') in ['administrador', 'lider_inventario']):
            materiales = filtrar_por_oficina_usuario(materiales, 'oficina_id')
        
        # Calcular estadÃƒÂ­sticas
        valor_total_inventario = sum(m.get('valor_total', 0) or 0 for m in materiales)
        
        # Obtener estadÃƒÂ­sticas de solicitudes
        stats_dict = {}
        for mat in materiales:
            stats = SolicitudModel.obtener_estadisticas_por_material(mat['id'])
            stats_dict[mat['id']] = stats
        
        # Calcular totales
        total_solicitudes = sum(stats[0] for stats in stats_dict.values() if stats)
        total_entregado = sum(stats[3] for stats in stats_dict.values() if stats)
        
        return render_template('reportes/materiales.html',
                             materiales=materiales,
                             valor_total_inventario=valor_total_inventario,
                             stats_dict=stats_dict,
                             total_solicitudes=total_solicitudes,
                             total_entregado=total_entregado)
    except Exception as e:
        print(f"Ã¢ÂÅ’ Error generando reporte de materiales: {e}")
        flash('Error al generar el reporte de materiales', 'danger')
        return render_template('reportes/materiales.html',
                             materiales=[],
                             valor_total_inventario=0,
                             stats_dict={},
                             total_solicitudes=0,
                             total_entregado=0)

@reportes_bp.route('/inventario')
def reporte_inventario():
    """Reporte de inventario corporativo"""
    if not _require_login():
        return redirect('/login')
    
    if not can_access('inventario_corporativo', 'view'):
        flash('No tiene permisos para ver reportes de inventario', 'warning')
        return redirect('/reportes')
    
    try:
        materiales = MaterialModel.obtener_todos() or []
        
        # Aplicar filtro segÃƒÂºn permisos
        if not (session.get('rol') in ['administrador', 'lider_inventario']):
            materiales = filtrar_por_oficina_usuario(materiales, 'oficina_id')
        
        # Calcular estadÃƒÂ­sticas
        valor_total = 0
        for material in materiales:
            valor_total_material = material.get('valor_total', 0)
            try:
                valor_total += float(valor_total_material)
            except:
                valor_total += 0
        
        valor_promedio = valor_total / len(materiales) if materiales else 0
        
        # Agrupar por oficina
        ubicaciones_dict = {}
        for material in materiales:
            ubicacion = material.get('oficina_nombre', 'Sin oficina')
            if ubicacion not in ubicaciones_dict:
                ubicaciones_dict[ubicacion] = {'cantidad': 0, 'nombre': ubicacion}
            ubicaciones_dict[ubicacion]['cantidad'] += 1
        
        categorias = []
        ubicaciones = list(ubicaciones_dict.values())
        
        # Formatear productos
        productos = []
        for material in materiales:
            productos.append({
                'id': material.get('id'),
                'nombre': material.get('nombre', 'Sin nombre'),
                'valor_unitario': float(material.get('valor_unitario', 0)),
                'cantidad': int(material.get('cantidad', 0)),
                'valor_total': float(material.get('valor_total', 0)),
                'oficina_nombre': material.get('oficina_nombre', 'Sin oficina'),
                'fecha_creacion': material.get('fecha_creacion')
            })
        
        return render_template('reportes/inventario.html',
                            productos=productos,
                            total_productos=len(materiales),
                            valor_total_inventario=valor_total,
                            valor_promedio=valor_promedio,
                            categorias=categorias,
                            ubicaciones=ubicaciones)
        
    except Exception as e:
        print(f"Ã¢ÂÅ’ Error en reporte_inventario: {e}")
        flash('Error al generar el reporte de inventario', 'danger')
        return render_template('reportes/inventario.html',
                            productos=[],
                            total_productos=0,
                            valor_total_inventario=0,
                            valor_promedio=0,
                            categorias=[],
                            ubicaciones=[])

@reportes_bp.route('/novedades')
def reporte_novedades():
    """Reporte de novedades"""
    if not _require_login():
        return redirect('/login')
    
    if not can_access('novedades', 'view'):
        flash('No tiene permisos para ver reportes de novedades', 'warning')
        return redirect('/reportes')
    
    try:
        novedades = NovedadModel.obtener_todas() or []
        
        # Aplicar filtro segÃƒÂºn permisos
        if not (session.get('rol') in ['administrador', 'lider_inventario']):
            oficina_usuario = session.get('oficina_id')
            novedades = [n for n in novedades if n.get('oficina_id') == oficina_usuario]
        
        # Calcular estadÃƒÂ­sticas
        total_novedades = len(novedades)
        
        # Contar por estado
        estados = {'pendiente': 0, 'en_proceso': 0, 'resuelto': 0}
        for novedad in novedades:
            estado = novedad.get('estado', 'pendiente')
            if estado == 'pendiente':
                estados['pendiente'] += 1
            elif estado == 'en_proceso':
                estados['en_proceso'] += 1
            elif estado == 'resuelto':
                estados['resuelto'] += 1
        
        # Contar por prioridad
        prioridades = {'alta': 0, 'media': 0, 'baja': 0}
        for novedad in novedades:
            prioridad = novedad.get('prioridad', 'media')
            if prioridad == 'alta':
                prioridades['alta'] += 1
            elif prioridad == 'media':
                prioridades['media'] += 1
            elif prioridad == 'baja':
                prioridades['baja'] += 1
        
        # Tipos de novedad ÃƒÂºnicos
        tipos_novedad = list(set([n.get('tipo', 'General') for n in novedades]))
        
        # Reportantes ÃƒÂºnicos
        reportantes = list(set([n.get('usuario_registra', 'Desconocido') for n in novedades]))
        
        # Novedades recientes
        novedades_recientes = sorted(novedades, 
                                   key=lambda x: x.get('fecha_reporte', datetime.now()), 
                                   reverse=True)[:6]
        
        return render_template('reportes/novedades.html',
                             novedades=novedades,
                             total_novedades=total_novedades,
                             pendientes=estados['pendiente'],
                             en_proceso=estados['en_proceso'],
                             resueltas=estados['resuelto'],
                             prioridad_alta=prioridades['alta'],
                             prioridad_media=prioridades['media'],
                             prioridad_baja=prioridades['baja'],
                             tipos_novedad=tipos_novedad,
                             reportantes=reportantes,
                             novedades_recientes=novedades_recientes)
    except Exception as e:
        print(f"Ã¢ÂÅ’ Error en reporte_novedades: {e}")
        flash('Error al generar el reporte de novedades', 'danger')
        return render_template('reportes/novedades.html',
                             novedades=[],
                             total_novedades=0,
                             pendientes=0,
                             en_proceso=0,
                             resueltas=0,
                             prioridad_alta=0,
                             prioridad_media=0,
                             prioridad_baja=0,
                             tipos_novedad=[],
                             reportantes=[],
                             novedades_recientes=[])

@reportes_bp.route('/oficinas')
def reporte_oficinas():
    if not _require_login():
        return redirect('/login')
    
    # Verificar permisos
    if not can_access('oficinas', 'view'):
        flash('No tiene permisos para ver reportes de oficinas', 'warning')
        return redirect('/reportes')
    
    try:
        # Obtener todas las oficinas
        oficinas = OficinaModel.obtener_todas() or []
        
        print(f"Ã°Å¸â€Â DEBUG reporte_oficinas: Total oficinas obtenidas: {len(oficinas)}")
        
        rol_usuario = session.get('rol', '').lower()
        oficina_id_usuario = session.get('oficina_id')
        
        print(f"Ã°Å¸â€Â Permisos usuario - Rol: {rol_usuario}, Oficina ID: {oficina_id_usuario}")
        
        # SOLO filtrar si es rol especÃƒÂ­fico de oficina
        if rol_usuario.startswith('oficina_'):
            print(f"Ã°Å¸â€Â Filtrando solo oficina del usuario: ID {oficina_id_usuario}")
            oficinas_filtradas = []
            for o in oficinas:
                if o.get('id') == oficina_id_usuario:
                    oficinas_filtradas.append(o)
            oficinas = oficinas_filtradas
        
        print(f"Ã°Å¸â€Â Oficinas despuÃƒÂ©s de filtrar: {len(oficinas)}")
        
        # Obtener informaciÃƒÂ³n de inventario corporativo para cada oficina
        from database import get_database_connection
        
        conn = None
        try:
            conn = get_database_connection()
            cursor = conn.cursor()
            
            for oficina in oficinas:
                oficina_id = oficina.get('id')
                oficina_nombre = oficina.get('nombre', '')
                
                print(f"Ã°Å¸â€Â Procesando oficina: {oficina_nombre} (ID: {oficina_id})")
                
                try:
                    
                    cursor.execute("""
                        SELECT DISTINCT
                            pc.ProductoId,
                            pc.CodigoUnico,  -- NUEVO: CÃƒÂ³digo ÃƒÂºnico del producto
                            pc.NombreProducto,
                            pc.Descripcion,
                            pc.ValorUnitario,
                            pc.CantidadMinima,
                            pc.Activo,
                            pc.FechaCreacion,
                            pc.UsuarioCreador,
                            c.NombreCategoria,
                            -- Obtener cantidad total asignada a esta oficina
                            (
                                SELECT SUM(ach.Cantidad) 
                                FROM AsignacionesCorporativasHistorial ach 
                                WHERE ach.ProductoId = pc.ProductoId 
                                AND ach.OficinaId = ?
                                AND ach.Accion LIKE '%ASIGNAR%'
                            ) as CantidadAsignada
                        FROM ProductosCorporativos pc
                        LEFT JOIN CategoriasProductos c ON pc.CategoriaId = c.CategoriaId
                        WHERE EXISTS (
                            SELECT 1 
                            FROM AsignacionesCorporativasHistorial ach 
                            WHERE ach.ProductoId = pc.ProductoId 
                            AND ach.OficinaId = ?
                        )
                        AND pc.Activo = 1
                        ORDER BY pc.NombreProducto
                    """, (oficina_id, oficina_id))
                    
                    productos_oficina = []
                    for row in cursor.fetchall():
                        producto_id = row[0]
                        codigo_unico = row[1]  
                        cantidad_asignada = row[10] or 0  
                        valor_unitario = float(row[4] or 0)
                        valor_total = cantidad_asignada * valor_unitario
                        
                        producto = {
                            'id': producto_id,
                            'codigo_unico': codigo_unico, 
                            'nombre': row[2],
                            'descripcion': row[3] or '',
                            'cantidad': cantidad_asignada,
                            'valor_unitario': valor_unitario,
                            'valor_total': valor_total,
                            'stock_minimo': row[5] or 0,
                            'categoria': row[9] or 'General', 
                            'activo': bool(row[6]),
                            'usuario_creador': row[8] if row[8] else '',  
                            'fecha_creacion': row[7] if row[7] else None, 
                            'tipo': 'corporativo'
                        }
                        productos_oficina.append(producto)
                    
                    oficina['materiales'] = productos_oficina
                    oficina['cantidad_materiales'] = len(productos_oficina)
                    
                    # Calcular valor total del inventario corporativo para esta oficina
                    valor_total_oficina = sum(p.get('valor_total', 0) for p in productos_oficina)
                    oficina['valor_total_inventario'] = valor_total_oficina
                    
                    print(f"Ã¢Å“â€¦ Inventario corporativo para {oficina_nombre}: {len(productos_oficina)} productos")
                    
                except Exception as mat_error:
                    print(f"Ã¢Å¡Â Ã¯Â¸Â Error obteniendo inventario corporativo para oficina {oficina_id}: {mat_error}")
                    oficina['materiales'] = []
                    oficina['cantidad_materiales'] = 0
                    oficina['valor_total_inventario'] = 0
                
                try:
                    cursor.execute("""
                        SELECT TOP 5
                            sm.SolicitudId,
                            sm.CantidadSolicitada,
                            sm.CantidadEntregada,
                            sm.FechaSolicitud,
                            es.NombreEstado as Estado,
                            m.NombreElemento as MaterialNombre,
                            sm.UsuarioSolicitante,
                            sm.Observacion
                        FROM SolicitudesMaterial sm
                        INNER JOIN Materiales m ON sm.MaterialId = m.MaterialId
                        INNER JOIN EstadosSolicitud es ON sm.EstadoId = es.EstadoId
                        WHERE sm.OficinaSolicitanteId = ?
                        ORDER BY sm.FechaSolicitud DESC
                    """, (oficina_id,))
                    
                    solicitudes_oficina = []
                    for row in cursor.fetchall():
                        solicitud = {
                            'id': row[0],
                            'cantidad_solicitada': row[1],
                            'cantidad_entregada': row[2],
                            'fecha_solicitud': row[3],
                            'estado': row[4],
                            'material_nombre': row[5],
                            'usuario_solicitante': row[6],
                            'observacion': row[7] or ''
                        }
                        solicitudes_oficina.append(solicitud)
                    
                    oficina['solicitudes'] = solicitudes_oficina
                    oficina['cantidad_solicitudes'] = len(solicitudes_oficina)
                    
                except Exception as sol_error:
                    print(f"Ã¢Å¡Â Ã¯Â¸Â Error obteniendo solicitudes para oficina {oficina_id}: {sol_error}")
                    oficina['solicitudes'] = []
                    oficina['cantidad_solicitudes'] = 0
                
                # --- PrÃƒÂ©stamos de esta oficina ---
                try:
                    cursor.execute("""
                        SELECT COUNT(*) 
                        FROM PrestamosMaterial 
                        WHERE OficinaId = ? AND Activo = 1
                    """, (oficina_id,))
                    
                    result = cursor.fetchone()
                    oficina['cantidad_prestamos'] = result[0] if result else 0
                    
                except Exception as prestamo_error:
                    print(f"Ã¢Å¡Â Ã¯Â¸Â Error obteniendo prÃƒÂ©stamos para oficina {oficina_id}: {prestamo_error}")
                    oficina['cantidad_prestamos'] = 0
                
                # --- HISTORIAL DE ASIGNACIONES CORPORATIVAS - TABLA CORRECTA ---
                try:
                    # CONSULTA PRINCIPAL: Obtener historial de asignaciones corporativas
                    cursor.execute("""
                        SELECT TOP 15
                            ach.HistorialId,
                            ach.Fecha,
                            ach.Accion,
                            ach.Cantidad,
                            ach.UsuarioAccion,
                            ach.Observaciones,
                            pc.NombreProducto as MaterialNombre,
                            o2.NombreOficina as OficinaNombre
                        FROM AsignacionesCorporativasHistorial ach
                        LEFT JOIN ProductosCorporativos pc ON ach.ProductoId = pc.ProductoId
                        LEFT JOIN Oficinas o2 ON ach.OficinaId = o2.OficinaId
                        WHERE ach.OficinaId = ?
                        ORDER BY ach.Fecha DESC
                    """, (oficina_id,))
                    
                    historial_oficina = []
                    for row in cursor.fetchall():
                        movimiento = {
                            'fecha': row[1],
                            'accion': row[2] if row[2] else 'AsignaciÃƒÂ³n',
                            'material_nombre': row[6] if row[6] else f"Producto ID: {row[0]}",
                            'cantidad': row[3] if row[3] else 1,
                            'oficina_destino_nombre': row[7] if row[7] else oficina_nombre,
                            'usuario_nombre': row[4] if row[4] else 'Sistema',
                            'observaciones': row[5] if row[5] else ''
                        }
                        historial_oficina.append(movimiento)
                    
                    # TambiÃƒÂ©n buscar asignaciones regulares
                    cursor.execute("""
                        SELECT TOP 5
                            a.FechaAsignacion,
                            'AsignaciÃƒÂ³n a Usuario' as Accion,
                            a.UsuarioAsignador,
                            a.Observaciones,
                            pc.NombreProducto as MaterialNombre
                        FROM Asignaciones a
                        LEFT JOIN ProductosCorporativos pc ON a.ProductoId = pc.ProductoId
                        WHERE a.OficinaId = ? AND a.Activo = 1
                        ORDER BY a.FechaAsignacion DESC
                    """, (oficina_id,))
                    
                    asignaciones_regulares = []
                    for row in cursor.fetchall():
                        movimiento = {
                            'fecha': row[0],
                            'accion': row[1],
                            'material_nombre': row[4] if row[4] else 'Producto asignado',
                            'cantidad': 1,
                            'oficina_destino_nombre': oficina_nombre,
                            'usuario_nombre': row[2] if row[2] else 'Sistema',
                            'observaciones': row[3] if row[3] else ''
                        }
                        asignaciones_regulares.append(movimiento)
                    
                    # Combinar todos los movimientos
                    todos_movimientos = historial_oficina + asignaciones_regulares
                    
                    # Ordenar por fecha (mÃƒÂ¡s reciente primero)
                    todos_movimientos_ordenados = sorted(
                        todos_movimientos, 
                        key=lambda x: x['fecha'] if x['fecha'] else datetime.min, 
                        reverse=True
                    )[:15]  # Limitar a 15 movimientos
                    
                    oficina['movimientos'] = todos_movimientos_ordenados
                    oficina['cantidad_movimientos'] = len(todos_movimientos_ordenados)
                    
                    print(f"Ã¢Å“â€¦ Movimientos para oficina {oficina_nombre}: {len(todos_movimientos_ordenados)} registros")
                    
                    # Debug: Mostrar los primeros 3 movimientos
                    for i, mov in enumerate(todos_movimientos_ordenados[:3]):
                        print(f"   {i+1}. {mov.get('fecha')} - {mov.get('accion')}: {mov.get('material_nombre')}")
                    
                except Exception as mov_error:
                    print(f"Ã¢Å¡Â Ã¯Â¸Â Error obteniendo movimientos para oficina {oficina_id}: {mov_error}")
                    import traceback
                    traceback.print_exc()
                    oficina['movimientos'] = []
                    oficina['cantidad_movimientos'] = 0
        
        except Exception as e:
            print(f"Ã¢Å¡Â Ã¯Â¸Â Error general obteniendo datos: {e}")
            import traceback
            traceback.print_exc()
            
            for oficina in oficinas:
                oficina['materiales'] = []
                oficina['solicitudes'] = []
                oficina['movimientos'] = []
                oficina['cantidad_materiales'] = 0
                oficina['cantidad_solicitudes'] = 0
                oficina['cantidad_prestamos'] = 0
                oficina['cantidad_movimientos'] = 0
                oficina['valor_total_inventario'] = 0
        
        finally:
            if conn:
                conn.close()
        
        # Calcular totales generales
        total_materiales_oficinas = sum(o.get('cantidad_materiales', 0) for o in oficinas)
        total_solicitudes_oficinas = sum(o.get('cantidad_solicitudes', 0) for o in oficinas)
        total_valor_inventario = sum(o.get('valor_total_inventario', 0) for o in oficinas)
        total_movimientos_oficinas = sum(o.get('cantidad_movimientos', 0) for o in oficinas)
        oficinas_activas_count = len([o for o in oficinas if o.get('estado') == 'activo'])
        
        print(f"Ã¢Å“â€¦ REPORTE OFICINAS GENERADO:")
        print(f"   - Total oficinas: {len(oficinas)}")
        print(f"   - Total materiales: {total_materiales_oficinas}")
        print(f"   - Valor total inventario: ${total_valor_inventario:,.2f}")
        print(f"   - Total movimientos: {total_movimientos_oficinas}")
        
        return render_template('reportes/oficinas.html',
                             oficinas=oficinas,
                             total_oficinas=len(oficinas),
                             oficinas_activas=oficinas_activas_count,
                             total_materiales_oficinas=total_materiales_oficinas,
                             total_solicitudes_oficinas=total_solicitudes_oficinas,
                             total_movimientos_oficinas=total_movimientos_oficinas,
                             total_valor_inventario=total_valor_inventario)
        
    except Exception as e:
        print(f"Ã¢ÂÅ’ Error generando reporte de oficinas: {e}")
        import traceback
        traceback.print_exc()
        flash('Error al generar el reporte de oficinas', 'danger')
        return render_template('reportes/oficinas.html',
                             oficinas=[],
                             total_oficinas=0,
                             oficinas_activas=0,
                             total_materiales_oficinas=0,
                             total_solicitudes_oficinas=0,
                             total_movimientos_oficinas=0,
                             total_valor_inventario=0)

@reportes_bp.route('/prestamos')
def reporte_prestamos():
    """Reporte de prÃƒÂ©stamos - VERSIÃƒâ€œN COMPATIBLE CON TEMPLATE"""
    if not _require_login():
        return redirect('/login')
    
    if not (can_access('prestamos', 'view') or can_access('prestamos', 'view_own')):
        flash('No tiene permisos para ver reportes de prÃƒÂ©stamos', 'warning')
        return redirect('/reportes')
    
    try:
        from database import get_database_connection
        
        conn = get_database_connection()
        cursor = conn.cursor()
        
        # Obtener filtros del template
        filtro_estado = request.args.get('estado', '')
        filtro_oficina = request.args.get('oficina', '')
        filtro_material = request.args.get('material', '').strip()
        filtro_solicitante = request.args.get('solicitante', '').strip()
        filtro_fecha_inicio = request.args.get('fecha_inicio', '')
        filtro_fecha_fin = request.args.get('fecha_fin', '')
        
        print(f"Ã°Å¸â€Â Filtros recibidos:")
        print(f"   Estado: {filtro_estado}")
        print(f"   Oficina: {filtro_oficina}")
        print(f"   Material: {filtro_material}")
        print(f"   Solicitante: {filtro_solicitante}")
        
        # Construir consulta base con filtros
        query = """
            SELECT 
                pe.PrestamoId,
                pe.ElementoId,
                ep.NombreElemento as Material,
                pe.UsuarioSolicitanteId,
                u.NombreUsuario as SolicitanteNombre,
                pe.OficinaId,
                o.NombreOficina as OficinaNombre,
                pe.CantidadPrestada as Cantidad,
                pe.FechaPrestamo as Fecha,
                pe.FechaDevolucionPrevista as FechaPrevista,
                pe.FechaDevolucionReal,
                pe.Estado,
                pe.Evento,
                pe.Observaciones,
                pe.UsuarioPrestador,
                ep.ValorUnitario,
                (pe.CantidadPrestada * ep.ValorUnitario) as Subtotal
            FROM PrestamosElementos pe
            INNER JOIN ElementosPublicitarios ep ON pe.ElementoId = ep.ElementoId
            INNER JOIN Usuarios u ON pe.UsuarioSolicitanteId = u.UsuarioId
            INNER JOIN Oficinas o ON pe.OficinaId = o.OficinaId
            WHERE pe.Activo = 1
        """
        
        params = []
        
        # Aplicar filtro de estado
        if filtro_estado:
            query += " AND pe.Estado = ?"
            params.append(filtro_estado)
        
        # Aplicar filtro de oficina (solo para admin/lider)
        rol_usuario = session.get('rol', '').lower()
        oficina_id_usuario = session.get('oficina_id')
        
        if rol_usuario in ['administrador', 'lider_inventario']:
            if filtro_oficina:
                query += " AND pe.OficinaId = ?"
                params.append(filtro_oficina)
        else:
            # Usuario normal solo ve su oficina
            query += " AND pe.OficinaId = ?"
            params.append(oficina_id_usuario)
        
        # Aplicar filtro de material (bÃƒÂºsqueda parcial)
        if filtro_material:
            query += " AND ep.NombreElemento LIKE ?"
            params.append(f'%{filtro_material}%')
        
        # Aplicar filtro de solicitante (bÃƒÂºsqueda parcial)
        if filtro_solicitante:
            query += " AND u.NombreUsuario LIKE ?"
            params.append(f'%{filtro_solicitante}%')
        
        # Aplicar filtro de fechas
        if filtro_fecha_inicio:
            query += " AND CAST(pe.FechaPrestamo AS DATE) >= ?"
            params.append(filtro_fecha_inicio)
        
        if filtro_fecha_fin:
            query += " AND CAST(pe.FechaPrestamo AS DATE) <= ?"
            params.append(filtro_fecha_fin)
        
        # Ordenar
        query += " ORDER BY pe.FechaPrestamo DESC"
        
        print(f"Ã°Å¸â€Â Consulta SQL: {query}")
        print(f"Ã°Å¸â€Â ParÃƒÂ¡metros: {params}")
        
        cursor.execute(query, params)
        
        prestamos = []
        for row in cursor.fetchall():
            prestamo = {
                'id': row[0],
                'material': row[2],  # Nombre del material
                'cantidad': row[7],
                'valor_unitario': float(row[15] or 0),
                'subtotal': float(row[16] or 0),
                'solicitante_nombre': row[4],
                'oficina_nombre': row[6],
                'fecha': row[8],
                'fecha_prevista': row[9],
                'estado': row[11],
                'evento': row[12],
                'observaciones': row[13]
            }
            prestamos.append(prestamo)
        
        # Obtener oficinas para el filtro (solo para admin/lider)
        oficinas = []
        if rol_usuario in ['administrador', 'lider_inventario']:
            cursor.execute("SELECT OficinaId, NombreOficina FROM Oficinas WHERE Activo = 1 ORDER BY NombreOficina")
            oficinas = [{'id': row[0], 'nombre': row[1]} for row in cursor.fetchall()]
        
        conn.close()
        
        # Calcular estadÃƒÂ­sticas
        total_prestamos = len(prestamos)
        prestamos_activos = len([p for p in prestamos if p['estado'] == 'PRESTADO'])
        aprobados = len([p for p in prestamos if p['estado'] == 'APROBADO'])
        devueltos = len([p for p in prestamos if p['estado'] == 'DEVUELTO'])
        
        print(f"Ã¢Å“â€¦ PrÃƒÂ©stamos encontrados: {total_prestamos}")
        print(f"   Activos: {prestamos_activos}")
        print(f"   Aprobados: {aprobados}")
        print(f"   Devueltos: {devueltos}")
        
        return render_template('reportes/prestamos.html',
                             prestamos=prestamos,
                             total_prestamos=total_prestamos,
                             prestamos_activos=prestamos_activos,
                             aprobados=aprobados,
                             devueltos=devueltos,
                             filtro_estado=filtro_estado,
                             filtro_oficina=filtro_oficina,
                             filtro_material=filtro_material,
                             filtro_solicitante=filtro_solicitante,
                             filtro_fecha_inicio=filtro_fecha_inicio,
                             filtro_fecha_fin=filtro_fecha_fin,
                             oficinas=oficinas)
                             
    except Exception as e:
        print(f"Ã¢ÂÅ’ Error generando reporte de prÃƒÂ©stamos: {e}")
        import traceback
        traceback.print_exc()
        flash('Error al generar el reporte de prÃƒÂ©stamos', 'danger')
        return render_template('reportes/prestamos.html',
                             prestamos=[],
                             total_prestamos=0,
                             prestamos_activos=0,
                             aprobados=0,
                             devueltos=0,
                             filtro_estado='',
                             filtro_oficina='',
                             filtro_material='',
                             filtro_solicitante='',
                             filtro_fecha_inicio='',
                             filtro_fecha_fin='',
                             oficinas=[])

# ============================================================================
# RUTAS DE EXPORTACIÃƒâ€œN
# ============================================================================

@reportes_bp.route('/materiales/exportar/excel')
def exportar_materiales_excel():
    """Exporta materiales a Excel"""
    if not _require_login():
        return redirect('/login')
    
    try:
        materiales = MaterialModel.obtener_todos() or []
        
        # Aplicar filtro segÃƒÂºn permisos
        if not (session.get('rol') in ['administrador', 'lider_inventario']):
            materiales = filtrar_por_oficina_usuario(materiales, 'oficina_id')

        data = []
        for mat in materiales:
            data.append({
                'ID': mat.get('id', ''),
                'Nombre': mat.get('nombre', ''),
                'Valor Unitario': mat.get('valor_unitario', 0),
                'Stock Actual': mat.get('cantidad', 0),
                'Stock MÃƒÂ­nimo': mat.get('stock_minimo', 0) if mat.get('stock_minimo') else 0,
                'Valor Total': mat.get('valor_total', 0),
                'Oficina': mat.get('oficina_nombre', ''),
                'Creado por': mat.get('usuario_creador', ''),
                'Fecha CreaciÃƒÂ³n': mat.get('fecha_creacion', '')
            })

        df = pd.DataFrame(data)
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Materiales', index=False)
        
        output.seek(0)
        fecha_actual = datetime.now().strftime('%Y-%m-%d')
        filename = f'reporte_materiales_{fecha_actual}.xlsx'

        return send_file(output,
                         mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                         as_attachment=True,
                         download_name=filename)
    except Exception as e:
        print(f"Ã¢ÂÅ’ Error exportando materiales a Excel: {e}")
        flash('Error al exportar el reporte de materiales a Excel', 'danger')
        return redirect('/reportes')

# ============================================================================
# FUNCIONES DE EXPORTACIÃƒâ€œN A PDF - VERSIONES MEJORADAS
# ============================================================================

@reportes_bp.route('/exportar/inventario-corporativo/pdf')
def exportar_inventario_corporativo_pdf():
    """Exporta el inventario corporativo a PDF"""
    if not _require_login():
        return redirect('/login')
    
    # Verificar permisos
    if not can_access('inventario_corporativo', 'view'):
        flash('No tiene permisos para exportar inventario corporativo', 'warning')
        return redirect('/reportes')
    
    try:
        # Intentar importar reportlab
        try:
            from reportlab.lib.pagesizes import letter, landscape
            from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib import colors
            from reportlab.lib.units import inch, cm
        except ImportError:
            flash('La librerÃƒÂ­a ReportLab no estÃƒÂ¡ instalada. InstÃƒÂ¡lela con: pip install reportlab', 'danger')
            return redirect('/reportes')
        
        from database import get_database_connection
        import io
        
        conn = get_database_connection()
        
        # CONSULTA CORREGIDA - USANDO LA TABLA MATERIALES REAL
        query = """
        SELECT 
            o.NombreOficina as Oficina,
            m.NombreElemento as Material,
            m.CantidadDisponible as Cantidad,
            m.ValorUnitario,
            (m.CantidadDisponible * m.ValorUnitario) as ValorTotal,
            m.CantidadMinima as StockMinimo,
            CASE WHEN m.Activo = 1 THEN 'Activo' ELSE 'Inactivo' END as Estado,
            m.UsuarioCreador as Responsable,
            FORMAT(m.FechaCreacion, 'dd/MM/yyyy') as Fecha_Creacion
        FROM Materiales m
        INNER JOIN Oficinas o ON m.OficinaCreadoraId = o.OficinaId
        WHERE m.Activo = 1
        ORDER BY o.NombreOficina, m.NombreElemento
        """
        
        cursor = conn.cursor()
        cursor.execute(query)
        resultados = cursor.fetchall()
        
        # Obtener nombres de columnas
        column_names = [column[0] for column in cursor.description]
        conn.close()
        
        # Verificar si hay datos
        if not resultados:
            flash('No hay datos de inventario corporativo para exportar', 'warning')
            return redirect('/reportes')
        
        # Crear PDF en memoria
        buffer = io.BytesIO()
        
        # Usar landscape y ajustar mÃƒÂ¡rgenes para mejor uso del espacio
        doc = SimpleDocTemplate(
            buffer,
            pagesize=landscape(letter),
            topMargin=0.5*inch,
            bottomMargin=0.5*inch,
            leftMargin=0.5*inch,
            rightMargin=0.5*inch
        )
        
        # Estilos
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=14,
            alignment=1,  # Centrado
            spaceAfter=10
        )
        
        subtitle_style = ParagraphStyle(
            'CustomSubtitle',
            parent=styles['Normal'],
            fontSize=9,
            alignment=1,
            spaceAfter=15
        )
        
        # Preparar datos para la tabla
        data = []
        
        # TÃƒÂ­tulo
        data.append([Paragraph('<b>REPORTE DE INVENTARIO CORPORATIVO</b>', title_style)])
        data.append([Paragraph(f'Fecha de generaciÃƒÂ³n: {datetime.now().strftime("%d/%m/%Y %H:%M")}', subtitle_style)])
        data.append([''])  # Espacio
        
        # Encabezados de tabla
        data.append(column_names)
        
        # Filas de datos
        total_valor = 0
        for row in resultados:
            # Formatear valores monetarios
            formatted_row = []
            for i, value in enumerate(row):
                if column_names[i] in ['ValorUnitario', 'ValorTotal'] and value is not None:
                    try:
                        val = float(value)
                        if column_names[i] == 'ValorTotal':
                            total_valor += val
                        formatted_row.append(f"${val:,.2f}")
                    except (ValueError, TypeError):
                        formatted_row.append("$0.00")
                else:
                    formatted_row.append(str(value) if value is not None else 'N/A')
            data.append(formatted_row)
        
        total_materiales = len(resultados)
        
        # Agregar fila de totales
        data.append([''])  # Espacio
        data.append(['<b>RESUMEN</b>', '', '', '', '', '', '', '', ''])
        data.append(['Total Materiales:', str(total_materiales), '', '', '', '', '', '', ''])
        data.append(['Valor Total Inventario:', f"${total_valor:,.2f}", '', '', '', '', '', '', ''])
        
        # Crear tabla
        table = Table(data, repeatRows=4)  # Repetir encabezados en cada pÃƒÂ¡gina
        
        # Estilo de la tabla
        table_style = TableStyle([
            ('SPAN', (0, 0), (8, 0)),  # TÃƒÂ­tulo
            ('SPAN', (0, 1), (8, 1)),  # Fecha
            
            # Encabezados
            ('BACKGROUND', (0, 3), (8, 3), colors.HexColor('#4F81BD')),
            ('TEXTCOLOR', (0, 3), (8, 3), colors.whitesmoke),
            ('ALIGN', (0, 3), (8, 3), 'CENTER'),
            ('FONTNAME', (0, 3), (8, 3), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 3), (8, 3), 8),
            ('BOTTOMPADDING', (0, 3), (8, 3), 6),
            
            # Datos
            ('GRID', (0, 3), (8, -5), 0.5, colors.grey),
            ('ALIGN', (2, 4), (4, -5), 'RIGHT'),  # Cantidad y valores alineados a la derecha
            ('ALIGN', (0, 4), (1, -5), 'LEFT'),   # Oficina y Material alineados a la izquierda
            ('FONTSIZE', (0, 4), (8, -5), 7),
            ('VALIGN', (0, 0), (8, -1), 'MIDDLE'),
            
            # Resumen
            ('SPAN', (0, -3), (0, -3)),
            ('FONTNAME', (0, -3), (1, -1), 'Helvetica-Bold'),
            ('ALIGN', (0, -2), (0, -1), 'LEFT'),
            ('ALIGN', (1, -2), (1, -1), 'RIGHT'),
            ('BACKGROUND', (0, -3), (1, -1), colors.HexColor('#E8F5E8')),
        ])
        
        # Alternar colores de filas
        for i in range(4, 4 + len(resultados), 2):
            if i < len(data) - 4:
                table_style.add('BACKGROUND', (0, i), (8, i), colors.HexColor('#F5F5F5'))
        
        table.setStyle(table_style)
        
        # Ajustar ancho de columnas
        col_widths = [
            2.5*cm,  # Oficina
            3.5*cm,  # Material
            1.5*cm,  # Cantidad
            2.0*cm,  # Valor Unitario
            2.0*cm,  # Valor Total
            1.5*cm,  # Stock MÃƒÂ­nimo
            1.5*cm,  # Estado
            2.0*cm,  # Responsable
            2.0*cm   # Fecha
        ]
        table._argW = col_widths
        
        # Generar PDF
        doc.build([table])
        
        buffer.seek(0)
        
        # Crear nombre de archivo
        fecha_actual = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'reporte_inventario_corporativo_{fecha_actual}.pdf'
        
        print(f"Ã¢Å“â€¦ PDF generado exitosamente: {total_materiales} registros, valor total: ${total_valor:,.2f}")
        
        return send_file(
            buffer,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=filename
        )
        
    except Exception as e:
        print(f"Ã¢ÂÅ’ Error exportando a PDF: {e}")
        import traceback
        traceback.print_exc()
        flash(f'Error al generar el PDF del inventario: {str(e)}', 'danger')
        return redirect('/reportes')

@reportes_bp.route('/prestamos/exportar/pdf')
def exportar_prestamos_pdf():
    """Exporta el reporte de prÃƒÂ©stamos a PDF"""
    if not _require_login():
        return redirect('/login')
    
    if not (can_access('prestamos', 'view') or can_access('prestamos', 'view_own')):
        flash('No tiene permisos para exportar reportes de prÃƒÂ©stamos', 'warning')
        return redirect('/reportes')
    
    try:
        # Verificar si reportlab estÃƒÂ¡ instalado
        try:
            from reportlab.lib.pagesizes import letter, landscape
            from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib import colors
            from reportlab.lib.units import inch, cm
        except ImportError:
            flash('La librerÃƒÂ­a ReportLab no estÃƒÂ¡ instalada. InstÃƒÂ¡lela con: pip install reportlab', 'danger')
            return redirect('/reportes')
        
        from database import get_database_connection
        import io
        
        conn = get_database_connection()
        cursor = conn.cursor()
        
        # Consulta para prÃƒÂ©stamos
        query = """
        SELECT 
            pe.PrestamoId as ID,
            ep.NombreElemento as Material,
            u.NombreUsuario as Solicitante,
            o.NombreOficina as Oficina,
            pe.CantidadPrestada as Cantidad,
            FORMAT(pe.FechaPrestamo, 'dd/MM/yyyy') as Fecha_Prestamo,
            FORMAT(pe.FechaDevolucionPrevista, 'dd/MM/yyyy') as Devolucion_Prevista,
            pe.Estado,
            pe.Evento
        FROM PrestamosElementos pe
        INNER JOIN ElementosPublicitarios ep ON pe.ElementoId = ep.ElementoId
        INNER JOIN Usuarios u ON pe.UsuarioSolicitanteId = u.UsuarioId
        INNER JOIN Oficinas o ON pe.OficinaId = o.OficinaId
        WHERE pe.Activo = 1
        ORDER BY pe.FechaPrestamo DESC
        """
        
        cursor.execute(query)
        resultados = cursor.fetchall()
        
        # Obtener nombres de columnas
        column_names = [column[0] for column in cursor.description]
        conn.close()
        
        # Verificar si hay datos
        if not resultados:
            flash('No hay datos de prÃƒÂ©stamos para exportar', 'warning')
            return redirect('/reportes')
        
        # Crear PDF en memoria
        buffer = io.BytesIO()
        
        # Usar landscape para mejor uso del espacio
        doc = SimpleDocTemplate(
            buffer,
            pagesize=landscape(letter),
            topMargin=0.5*inch,
            bottomMargin=0.5*inch,
            leftMargin=0.5*inch,
            rightMargin=0.5*inch
        )
        
        # Estilos
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=14,
            alignment=1,
            spaceAfter=15
        )
        
        # Preparar datos para la tabla
        data = []
        
        # TÃƒÂ­tulo
        data.append([Paragraph('<b>REPORTE DE PRÃƒâ€°STAMOS</b>', title_style)])
        data.append([Paragraph(f'Fecha de generaciÃƒÂ³n: {datetime.now().strftime("%d/%m/%Y %H:%M")}', 
                               ParagraphStyle('Date', parent=styles['Normal'], fontSize=9, alignment=1))])
        data.append([''])  # Espacio
        
        # Encabezados de tabla
        data.append(column_names)
        
        # Filas de datos
        for row in resultados:
            data.append([str(value) if value is not None else '' for value in row])
        
        # EstadÃƒÂ­sticas
        total_prestamos = len(resultados)
        prestamos_activos = len([r for r in resultados if r[7] == 'PRESTADO'])
        
        data.append([''])  # Espacio
        data.append(['<b>ESTADÃƒÂSTICAS</b>', '', '', '', '', '', '', '', ''])
        data.append(['Total PrÃƒÂ©stamos:', str(total_prestamos), '', '', '', '', '', '', ''])
        data.append(['PrÃƒÂ©stamos Activos:', str(prestamos_activos), '', '', '', '', '', '', ''])
        
        # Crear tabla
        table = Table(data, repeatRows=3)  # Repetir encabezados
        
        # Estilo de la tabla - OPTIMIZADO PARA UNA PÃƒÂGINA
        table_style = TableStyle([
            ('SPAN', (0, 0), (-1, 0)),  # TÃƒÂ­tulo ocupa todas las columnas
            ('SPAN', (0, 1), (-1, 1)),  # Fecha ocupa todas las columnas
            
            ('BACKGROUND', (0, 2), (-1, 2), colors.HexColor('#4F81BD')),  # Encabezados
            ('TEXTCOLOR', (0, 2), (-1, 2), colors.whitesmoke),
            ('ALIGN', (0, 2), (-1, 2), 'CENTER'),
            ('FONTNAME', (0, 2), (-1, 2), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 2), (-1, 2), 8),
            ('BOTTOMPADDING', (0, 2), (-1, 2), 6),
            
            ('GRID', (0, 2), (-1, -5), 0.5, colors.gray),  # Hasta antes de estadÃƒÂ­sticas
            ('FONTSIZE', (0, 3), (-1, -5), 7),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            
            # EstadÃƒÂ­sticas
            ('FONTNAME', (0, -3), (1, -1), 'Helvetica-Bold'),
            ('ALIGN', (0, -3), (1, -1), 'LEFT'),
            ('BACKGROUND', (0, -3), (1, -1), colors.HexColor('#F2F2F2')),
        ])
        
        # Alternar colores de filas
        for i in range(3, len(data)-4, 2):
            table_style.add('BACKGROUND', (0, i), (-1, i), colors.HexColor('#F2F2F2'))
        
        table.setStyle(table_style)
        
        # Ajustar ancho de columnas especÃƒÂ­ficamente para prÃƒÂ©stamos
        col_widths = [
            1.0*cm,  # ID
            3.0*cm,  # Material
            2.5*cm,  # Solicitante
            2.0*cm,  # Oficina
            1.5*cm,  # Cantidad
            2.0*cm,  # Fecha PrÃƒÂ©stamo
            2.0*cm,  # DevoluciÃƒÂ³n Prevista
            1.5*cm,  # Estado
            2.5*cm   # Evento
        ]
        table._argW = col_widths
        
        # Generar PDF
        doc.build([table])
        
        buffer.seek(0)
        
        # Crear nombre de archivo
        fecha_actual = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'reporte_prestamos_{fecha_actual}.pdf'
        
        return send_file(
            buffer,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=filename
        )
        
    except Exception as e:
        print(f"Ã¢ÂÅ’ Error exportando prÃƒÂ©stamos a PDF: {e}")
        flash(f'Error al generar el PDF de prÃƒÂ©stamos: {str(e)}', 'danger')
        return redirect('/reportes')

@reportes_bp.route('/materiales/exportar/pdf')
def exportar_materiales_pdf():
    """Exporta el reporte de materiales a PDF"""
    if not _require_login():
        return redirect('/login')
    
    if not can_access('materiales', 'view'):
        flash('No tiene permisos para exportar reportes de materiales', 'warning')
        return redirect('/reportes')
    
    try:
        # Verificar si reportlab estÃƒÂ¡ instalado
        try:
            from reportlab.lib.pagesizes import letter, landscape
            from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib import colors
            from reportlab.lib.units import inch, cm
        except ImportError:
            flash('La librerÃƒÂ­a ReportLab no estÃƒÂ¡ instalada. InstÃƒÂ¡lela con: pip install reportlab', 'danger')
            return redirect('/reportes')
        
        from database import get_database_connection
        import io
        
        conn = get_database_connection()
        cursor = conn.cursor()
        
        # Consulta para materiales
        query = """
        SELECT 
            m.NombreElemento as Material,
            o.NombreOficina as Oficina,
            m.CantidadDisponible as Stock,
            m.ValorUnitario,
            (m.CantidadDisponible * m.ValorUnitario) as Valor_Total,
            m.CantidadMinima as Stock_Minimo,
            CASE WHEN m.Activo = 1 THEN 'Activo' ELSE 'Inactivo' END as Estado,
            m.UsuarioCreador as Responsable,
            FORMAT(m.FechaCreacion, 'dd/MM/yyyy') as Fecha_Creacion
        FROM Materiales m
        INNER JOIN Oficinas o ON m.OficinaCreadoraId = o.OficinaId
        WHERE m.Activo = 1
        ORDER BY o.NombreOficina, m.NombreElemento
        """
        
        cursor.execute(query)
        resultados = cursor.fetchall()
        
        # Obtener nombres de columnas
        column_names = [column[0] for column in cursor.description]
        conn.close()
        
        # Verificar si hay datos
        if not resultados:
            flash('No hay datos de materiales para exportar', 'warning')
            return redirect('/reportes')
        
        # Crear PDF en memoria
        buffer = io.BytesIO()
        
        # Usar landscape para mejor uso del espacio
        doc = SimpleDocTemplate(
            buffer,
            pagesize=landscape(letter),
            topMargin=0.5*inch,
            bottomMargin=0.5*inch,
            leftMargin=0.5*inch,
            rightMargin=0.5*inch
        )
        
        # Estilos
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=14,
            alignment=1,
            spaceAfter=15
        )
        
        # Preparar datos para la tabla
        data = []
        
        # TÃƒÂ­tulo
        data.append([Paragraph('<b>REPORTE DE MATERIALES</b>', title_style)])
        data.append([Paragraph(f'Fecha de generaciÃƒÂ³n: {datetime.now().strftime("%d/%m/%Y %H:%M")}', 
                               ParagraphStyle('Date', parent=styles['Normal'], fontSize=9, alignment=1))])
        data.append([''])  # Espacio
        
        # Encabezados de tabla
        data.append(column_names)
        
        # Filas de datos
        total_valor = 0
        for row in resultados:
            formatted_row = []
            for i, value in enumerate(row):
                if column_names[i] in ['ValorUnitario', 'Valor_Total'] and value is not None:
                    try:
                        val = float(value)
                        if column_names[i] == 'Valor_Total':
                            total_valor += val
                        formatted_row.append(f"${val:,.2f}")
                    except (ValueError, TypeError):
                        formatted_row.append("$0.00")
                else:
                    formatted_row.append(str(value) if value is not None else '')
            data.append(formatted_row)
        
        total_materiales = len(resultados)
        
        data.append([''])  # Espacio
        data.append(['<b>RESUMEN</b>', '', '', '', '', '', '', '', ''])
        data.append(['Total Materiales:', str(total_materiales), '', '', '', '', '', '', ''])
        data.append(['Valor Total Inventario:', f"${total_valor:,.2f}", '', '', '', '', '', '', ''])
        
        # Crear tabla
        table = Table(data, repeatRows=3)  # Repetir encabezados
        
        # Estilo de la tabla
        table_style = TableStyle([
            ('SPAN', (0, 0), (-1, 0)),
            ('SPAN', (0, 1), (-1, 1)),
            
            ('BACKGROUND', (0, 2), (-1, 2), colors.HexColor('#4F81BD')),
            ('TEXTCOLOR', (0, 2), (-1, 2), colors.whitesmoke),
            ('ALIGN', (0, 2), (-1, 2), 'CENTER'),
            ('FONTNAME', (0, 2), (-1, 2), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 2), (-1, 2), 8),
            ('BOTTOMPADDING', (0, 2), (-1, 2), 6),
            
            ('GRID', (0, 2), (-1, -5), 0.5, colors.gray),
            ('FONTSIZE', (0, 3), (-1, -5), 7),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            
            # Resumen
            ('FONTNAME', (0, -3), (1, -1), 'Helvetica-Bold'),
            ('ALIGN', (0, -3), (1, -1), 'LEFT'),
            ('BACKGROUND', (0, -3), (1, -1), colors.HexColor('#F2F2F2')),
        ])
        
        # Alternar colores de filas
        for i in range(3, len(data)-4, 2):
            table_style.add('BACKGROUND', (0, i), (-1, i), colors.HexColor('#F2F2F2'))
        
        table.setStyle(table_style)
        
        # Ajustar ancho de columnas
        col_widths = [
            3.0*cm,  # Material
            2.5*cm,  # Oficina
            1.5*cm,  # Stock
            2.0*cm,  # Valor Unitario
            2.0*cm,  # Valor Total
            1.5*cm,  # Stock MÃƒÂ­nimo
            1.5*cm,  # Estado
            2.5*cm,  # Responsable
            2.0*cm   # Fecha
        ]
        table._argW = col_widths
        
        # Generar PDF
        doc.build([table])
        
        buffer.seek(0)
        
        # Crear nombre de archivo
        fecha_actual = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'reporte_materiales_{fecha_actual}.pdf'
        
        return send_file(
            buffer,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=filename
        )
        
    except Exception as e:
        print(f"Ã¢ÂÅ’ Error exportando materiales a PDF: {e}")
        flash(f'Error al generar el PDF de materiales: {str(e)}', 'danger')
        return redirect('/reportes')

@reportes_bp.route('/material/<int:material_id>')
def material_detalle(material_id):
    """Detalle de material específico"""
    if not _require_login():
        return redirect('/login')
    
    if not can_access('materiales', 'view'):
        flash('No tiene permisos para ver detalles de materiales', 'warning')
        return redirect('/reportes')
    
    try:
        from database import get_database_connection
        
        # Obtener el material
        material = MaterialModel.obtener_por_id(material_id)
        if not material:
            flash('Material no encontrado', 'danger')
            return redirect('/reportes/materiales')
        
        # Verificar permisos de oficina
        if not (session.get('rol') in ['administrador', 'lider_inventario']):
            if material.get('oficina_id') != session.get('oficina_id'):
                flash('No tiene permisos para ver este material', 'danger')
                return redirect('/reportes/materiales')
        
        # Obtener estadísticas del material
        stats = SolicitudModel.obtener_estadisticas_por_material(material_id)
        total_solicitudes = stats[0]
        solicitudes_aprobadas = stats[1]
        
        # Obtener historial de solicitudes del material
        conn = get_database_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                sm.SolicitudId as id,
                sm.UsuarioSolicitante as usuario_nombre,
                o.NombreOficina as oficina_nombre,
                sm.CantidadSolicitada as cantidad_solicitada,
                es.NombreEstado as estado,
                sm.FechaSolicitud as fecha_solicitud,
                sm.FechaAprobacion as fecha_aprobacion,
                sm.Observacion as observacion
            FROM SolicitudesMaterial sm
            INNER JOIN Oficinas o ON sm.OficinaSolicitanteId = o.OficinaId
            INNER JOIN EstadosSolicitud es ON sm.EstadoId = es.EstadoId
            WHERE sm.MaterialId = ?
            ORDER BY sm.FechaSolicitud DESC
        """, (material_id,))
        
        solicitudes = []
        for row in cursor.fetchall():
            solicitudes.append({
                'id': row[0],
                'usuario_nombre': row[1],
                'oficina_nombre': row[2],
                'cantidad_solicitada': row[3],
                'estado': row[4],
                'fecha_solicitud': row[5],
                'fecha_aprobacion': row[6],
                'observacion': row[7]
            })
        
        conn.close()
        
        return render_template('reportes/material_detalle.html',
                             material=material,
                             solicitudes=solicitudes,
                             total_solicitudes=total_solicitudes,
                             solicitudes_aprobadas=solicitudes_aprobadas)
        
    except Exception as e:
        print(f"⚠️ Error obteniendo detalle del material: {e}")
        import traceback
        traceback.print_exc()
        flash('Error al obtener el detalle del material', 'danger')
        return redirect('/reportes/materiales')

@reportes_bp.route('/exportar/inventario-corporativo/excel')
def exportar_inventario_corporativo_excel():
    """Exporta TODO el inventario corporativo a Excel"""
    if not _require_login():
        return redirect('/login')
    
    # Verificar permisos
    if not can_access('inventario_corporativo', 'view'):
        flash('No tiene permisos para exportar inventario corporativo', 'warning')
        return redirect('/reportes')
    
    try:
        from database import get_database_connection
        
        conn = get_database_connection()
        
        # CONSULTA CORREGIDA segÃƒÂºn tu estructura de base de datos
        query = """
        SELECT 
            o.NombreOficina,
            o.Ubicacion,
            m.NombreElemento as Material,
            m.CantidadDisponible as Stock,
            m.ValorUnitario,
            (m.CantidadDisponible * m.ValorUnitario) as ValorTotal,
            m.CantidadMinima as StockMinimo,
            m.UsuarioCreador as Responsable,
            CASE WHEN m.Activo = 1 THEN 'Activo' ELSE 'Inactivo' END as Estado,
            m.FechaCreacion
        FROM Materiales m
        INNER JOIN Oficinas o ON m.OficinaCreadoraId = o.OficinaId
        WHERE m.Activo = 1
        ORDER BY o.NombreOficina, m.NombreElemento
        """
        
        df = pd.read_sql_query(query, conn)
        conn.close()
        
        print(f"Ã¢Å“â€¦ EXPORTANDO INVENTARIO CORPORATIVO: {len(df)} registros")
        print(f"   - Fuente: Tabla Materiales (INVENTARIO CORPORATIVO)")
        print(f"   - Oficinas incluidas: {df['NombreOficina'].nunique()}")
        print(f"   - Valor total exportado: ${df['ValorTotal'].sum():,.2f}")
        
        # Crear archivo Excel en memoria
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            # Hoja 1: Inventario completo
            df.to_excel(writer, sheet_name='Inventario Corporativo', index=False)
            
            # Hoja 2: Resumen por oficina
            resumen_df = df.groupby(['NombreOficina', 'Ubicacion']).agg({
                'Material': 'count',
                'Stock': 'sum',
                'ValorTotal': 'sum'
            }).reset_index()
            resumen_df.columns = ['Oficina', 'UbicaciÃƒÂ³n', 'Cantidad Materiales', 'Stock Total', 'Valor Total Inventario']
            resumen_df['Valor Total Inventario'] = resumen_df['Valor Total Inventario'].round(2)
            resumen_df.to_excel(writer, sheet_name='Resumen por Oficina', index=False)
            
            # Hoja 3: Totales generales
            totales_data = {
                'MÃƒÂ©trica': [
                    'Total Oficinas con Inventario',
                    'Total Materiales',
                    'Stock Total',
                    'Valor Total Inventario',
                    'Valor Promedio por Material',
                    'Fecha de ExportaciÃƒÂ³n'
                ],
                'Valor': [
                    resumen_df['Oficina'].nunique(),
                    df['Material'].count(),
                    int(df['Stock'].sum()),
                    f"${df['ValorTotal'].sum():,.2f}",
                    f"${df['ValorTotal'].mean():,.2f}" if len(df) > 0 else "$0.00",
                    datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                ]
            }
            totales_df = pd.DataFrame(totales_data)
            totales_df.to_excel(writer, sheet_name='Totales Generales', index=False)
        
        output.seek(0)
        
        # Crear nombre de archivo
        fecha_actual = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'inventario_corporativo_completo_{fecha_actual}.xlsx'
        
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=filename
        )
        
    except Exception as e:
        print(f"Ã¢ÂÅ’ Error exportando inventario corporativo: {e}")
        import traceback
        traceback.print_exc()
        flash('Error al exportar el inventario corporativo', 'danger')
        return redirect('/reportes')

# ============================================================================
# EXPORTACIÃƒâ€œN POR OFICINA
# ============================================================================

@reportes_bp.route('/exportar/oficina/<int:oficina_id>/<string:formato>')
def exportar_oficina_inventario(oficina_id, formato):
    """Exporta el inventario de una oficina especÃƒÂ­fica"""
    if not _require_login():
        return redirect('/login')
    
    # Verificar permisos
    if not can_access('inventario_corporativo', 'view'):
        flash('No tiene permisos para exportar inventario corporativo', 'warning')
        return redirect('/reportes')
    
    try:
        from database import get_database_connection
        
        # Obtener parÃƒÂ¡metros - CORREGIDO
        incluir_materiales = request.args.get('materiales', '1') == '1'
        incluir_movimientos = request.args.get('movimientos', '1') == '1'
        incluir_totales = request.args.get('totales', '1') == '1'
        # incluir_solicitudes no se usa en la consulta SQL, se eliminÃƒÂ³
        
        conn = get_database_connection()
        
        # Obtener informaciÃƒÂ³n de la oficina - CORREGIDO
        cursor = conn.cursor()
        cursor.execute("""
            SELECT OficinaId, NombreOficina, Ubicacion, Region, Estado
            FROM Oficinas 
            WHERE OficinaId = ?
        """, (oficina_id,))
        
        oficina_data = cursor.fetchone()
        if not oficina_data:
            flash('Oficina no encontrada', 'danger')
            return redirect('/reportes')
        
        oficina = {
            'id': oficina_data[0],
            'nombre': oficina_data[1],
            'ubicacion': oficina_data[2],
            'region': oficina_data[3],
            'estado': oficina_data[4]
        }
        
        # Obtener materiales del inventario corporativo de esta oficina - CORREGIDO
        materiales = []
        if incluir_materiales:
            # CONSULTA CORREGIDA: Usar la tabla Materiales correcta
            cursor.execute("""
                SELECT 
                    m.MaterialId,
                    m.NombreElemento,
                    m.Descripcion,
                    m.ValorUnitario,
                    m.CantidadDisponible,
                    m.CantidadMinima,
                    m.Activo,
                    m.UsuarioCreador,
                    m.FechaCreacion,
                    m.Categoria
                FROM Materiales m
                WHERE m.OficinaCreadoraId = ? AND m.Activo = 1
                ORDER BY m.NombreElemento
            """, (oficina_id,))
            
            for row in cursor.fetchall():
                valor_total = row[3] * row[4] if row[3] and row[4] else 0  # ValorUnitario * CantidadDisponible
                material = {
                    'id': row[0],
                    'nombre': row[1],
                    'descripcion': row[2] or '',
                    'valor_unitario': float(row[3] or 0),
                    'cantidad': row[4] or 0,
                    'valor_total': float(valor_total),
                    'stock_minimo': row[5] or 0,
                    'activo': bool(row[6]),
                    'usuario_creador': row[7] or '',
                    'fecha_creacion': row[8],
                    'categoria': row[9] or 'General'
                }
                materiales.append(material)
        
        # Obtener movimientos/historial - CORREGIDO
        movimientos = []
        if incluir_movimientos:
            try:
                # Buscar movimientos del inventario corporativo
                # Primero en AsignacionesCorporativasHistorial
                cursor.execute("""
                    SELECT TOP 15
                        ach.Fecha,
                        ach.Accion,
                        ach.Cantidad,
                        ach.UsuarioAccion,
                        ach.Observaciones,
                        pc.NombreProducto as MaterialNombre
                    FROM AsignacionesCorporativasHistorial ach
                    LEFT JOIN ProductosCorporativos pc ON ach.ProductoId = pc.ProductoId
                    WHERE ach.OficinaId = ?
                    ORDER BY ach.Fecha DESC
                """, (oficina_id,))
                
                for row in cursor.fetchall():
                    if row[0]:  # Solo si hay fecha
                        movimiento = {
                            'fecha': row[0],
                            'accion': row[1] or 'AsignaciÃƒÂ³n',
                            'cantidad': row[2] or 1,
                            'usuario_nombre': row[3] or 'Sistema',
                            'observaciones': row[4] or '',
                            'material_nombre': row[5] or 'Producto Corporativo'
                        }
                        movimientos.append(movimiento)
                        
            except Exception as mov_error:
                print(f"Ã¢Å¡Â Ã¯Â¸Â Error obteniendo movimientos corporativos: {mov_error}")
                
            # TambiÃƒÂ©n buscar en movimientos regulares
            try:
                cursor.execute("""
                    SELECT TOP 10
                        mh.FechaMovimiento,
                        tm.NombreTipoMovimiento as Accion,
                        mh.Cantidad,
                        u.NombreUsuario,
                        mh.Observaciones,
                        mat.NombreElemento as MaterialNombre
                    FROM MovimientosHistorial mh
                    INNER JOIN TiposMovimiento tm ON mh.TipoMovimientoId = tm.TipoMovimientoId
                    INNER JOIN Materiales mat ON mh.MaterialId = mat.MaterialId
                    INNER JOIN Usuarios u ON mh.UsuarioId = u.UsuarioId
                    WHERE mh.OficinaId = ?
                    ORDER BY mh.FechaMovimiento DESC
                """, (oficina_id,))
                
                for row in cursor.fetchall():
                    if row[0]:  # Solo si hay fecha
                        movimiento = {
                            'fecha': row[0],
                            'accion': row[1] or 'Movimiento',
                            'cantidad': row[2] or 0,
                            'usuario_nombre': row[3] or 'Usuario',
                            'observaciones': row[4] or '',
                            'material_nombre': row[5] or 'Material'
                        }
                        movimientos.append(movimiento)
                        
            except Exception as mov_error2:
                print(f"Ã¢Å¡Â Ã¯Â¸Â Error obteniendo movimientos regulares: {mov_error2}")
        
        conn.close()
        
        # Calcular totales
        total_materiales = len(materiales)
        valor_total_inventario = sum(m.get('valor_total', 0) for m in materiales)
        total_movimientos = len(movimientos)
        
        # Ordenar movimientos por fecha (mÃƒÂ¡s reciente primero)
        movimientos.sort(key=lambda x: x.get('fecha', datetime.min), reverse=True)
        
        # Exportar segÃƒÂºn formato
        if formato.lower() == 'excel':
            return _exportar_oficina_excel(oficina, materiales, movimientos,
                                          total_materiales, valor_total_inventario, 
                                          total_movimientos, incluir_totales)
        elif formato.lower() == 'pdf':
            return _exportar_oficina_pdf(oficina, materiales, movimientos,
                                        total_materiales, valor_total_inventario,
                                        total_movimientos, incluir_totales)
        elif formato.lower() == 'csv':
            return _exportar_oficina_csv(oficina, materiales, movimientos,
                                        total_materiales, valor_total_inventario,
                                        total_movimientos, incluir_totales)
        else:
            flash('Formato de exportaciÃƒÂ³n no vÃƒÂ¡lido', 'danger')
            return redirect('/reportes')
            
    except Exception as e:
        print(f"Ã¢ÂÅ’ Error exportando inventario de oficina: {e}")
        import traceback
        traceback.print_exc()
        flash('Error al exportar el inventario de la oficina', 'danger')
        return redirect('/reportes')

def _exportar_oficina_excel(oficina, materiales, movimientos, total_materiales, 
                           valor_total_inventario, total_movimientos, incluir_totales):
    """Exporta a Excel el inventario de una oficina"""
    try:
        import pandas as pd
        from io import BytesIO
        
        # Crear DataFrames
        data_frames = []
        sheet_names = []
        
        # Hoja 1: InformaciÃƒÂ³n de la oficina
        oficina_info = {
            'Campo': ['Nombre Oficina', 'UbicaciÃƒÂ³n', 'RegiÃƒÂ³n', 'Estado', 'ID Oficina', 
                     'Total Materiales', 'Valor Total Inventario', 'Total Movimientos',
                     'Fecha ExportaciÃƒÂ³n'],
            'Valor': [oficina['nombre'], oficina['ubicacion'], oficina['region'], 
                     oficina['estado'], oficina['id'], total_materiales, 
                     f"${valor_total_inventario:,.2f}", total_movimientos,
                     datetime.now().strftime('%Y-%m-%d %H:%M:%S')]
        }
        df_oficina = pd.DataFrame(oficina_info)
        data_frames.append(df_oficina)
        sheet_names.append('InformaciÃƒÂ³n Oficina')
        
        # Hoja 2: Materiales del inventario
        if materiales:
            materiales_data = []
            for mat in materiales:
                fecha_creacion = mat['fecha_creacion']
                if hasattr(fecha_creacion, 'strftime'):
                    fecha_str = fecha_creacion.strftime('%Y-%m-%d')
                else:
                    fecha_str = str(fecha_creacion) if fecha_creacion else 'N/A'
                
                materiales_data.append({
                    'ID': mat['id'],
                    'Nombre': mat['nombre'],
                    'DescripciÃƒÂ³n': mat['descripcion'],
                    'CategorÃƒÂ­a': mat['categoria'],
                    'Valor Unitario': f"${mat['valor_unitario']:,.2f}",
                    'Cantidad': mat['cantidad'],
                    'Valor Total': f"${mat['valor_total']:,.2f}",
                    'Stock MÃƒÂ­nimo': mat['stock_minimo'],
                    'Estado': 'Activo' if mat['activo'] else 'Inactivo',
                    'Responsable': mat['usuario_creador'],
                    'Fecha CreaciÃƒÂ³n': fecha_str
                })
            
            df_materiales = pd.DataFrame(materiales_data)
            data_frames.append(df_materiales)
            sheet_names.append('Materiales Inventario')
        
        # Hoja 3: Historial de movimientos
        if movimientos:
            movimientos_data = []
            for mov in movimientos:
                fecha = mov['fecha']
                if hasattr(fecha, 'strftime'):
                    fecha_str = fecha.strftime('%Y-%m-%d %H:%M')
                else:
                    fecha_str = str(fecha) if fecha else 'N/A'
                
                movimientos_data.append({
                    'Fecha': fecha_str,
                    'AcciÃƒÂ³n': mov['accion'],
                    'Material': mov['material_nombre'],
                    'Cantidad': mov['cantidad'],
                    'Usuario': mov['usuario_nombre'],
                    'Observaciones': mov['observaciones']
                })
            
            df_movimientos = pd.DataFrame(movimientos_data)
            data_frames.append(df_movimientos)
            sheet_names.append('Historial Movimientos')
        
        # Crear archivo Excel
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            for i, df in enumerate(data_frames):
                df.to_excel(writer, sheet_name=sheet_names[i], index=False)
                
                # Ajustar ancho de columnas
                worksheet = writer.sheets[sheet_names[i]]
                for column in worksheet.columns:
                    max_length = 0
                    column_letter = column[0].column_letter
                    for cell in column:
                        try:
                            if len(str(cell.value)) > max_length:
                                max_length = len(str(cell.value))
                        except:
                            pass
                    adjusted_width = min(max_length + 2, 50)
                    worksheet.column_dimensions[column_letter].width = adjusted_width
        
        output.seek(0)
        
        # Nombre del archivo seguro
        nombre_oficina_safe = "".join(c for c in oficina['nombre'] if c.isalnum() or c in (' ', '_')).rstrip()
        nombre_oficina_safe = nombre_oficina_safe.replace(' ', '_').replace('/', '_')[:50]
        fecha = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'inventario_{nombre_oficina_safe}_{fecha}.xlsx'
        
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=filename
        )
        
    except Exception as e:
        print(f"Ã¢ÂÅ’ Error generando Excel de oficina: {e}")
        flash('Error al generar el archivo Excel', 'danger')
        return redirect('/reportes')

def _exportar_oficina_pdf(oficina, materiales, solicitudes, movimientos, total_materiales,
                         valor_total_inventario, total_solicitudes, total_movimientos, incluir_totales):
    """Exporta a PDF el inventario de una oficina"""
    try:
        # Por ahora, redirigir a Excel hasta que implementemos PDF
        flash('La exportaciÃƒÂ³n a PDF estarÃƒÂ¡ disponible prÃƒÂ³ximamente. Usando Excel por ahora.', 'info')
        
        # Crear parÃƒÂ¡metros para redirecciÃƒÂ³n a Excel
        from urllib.parse import urlencode
        params = {
            'materiales': '1' if materiales else '0',
            'solicitudes': '1' if solicitudes else '0',
            'movimientos': '1' if movimientos else '0',
            'totales': '1' if incluir_totales else '0'
        }
        
        oficina_id_val = oficina["id"]
        return redirect(f"/reportes/oficinas/{oficina_id_val}/inventario/excel?" + urlencode(params))
        
    except Exception as e:
        print(f"Ã¢ÂÅ’ Error generando PDF de oficina: {e}")
        flash('Error al generar el PDF', 'danger')
        return redirect('/reportes')

def _exportar_oficina_csv(oficina, materiales, solicitudes, movimientos, total_materiales,
                         valor_total_inventario, total_solicitudes, total_movimientos, incluir_totales):
    """Exporta a CSV el inventario de una oficina"""
    try:
        import pandas as pd
        from io import StringIO
        
        # Crear contenido CSV
        output = StringIO()
        
        # Encabezado con informaciÃƒÂ³n de la oficina
        output.write(f"Inventario Corporativo - {oficina['nombre']}\n")
        output.write(f"UbicaciÃƒÂ³n: {oficina['ubicacion']}\n")
        output.write(f"Director: {oficina['director']}\n")
        output.write(f"Fecha ExportaciÃƒÂ³n: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        output.write(f"Total Materiales: {total_materiales}\n")
        output.write(f"Valor Total Inventario: ${valor_total_inventario:,.2f}\n")
        output.write(f"Total Solicitudes: {total_solicitudes}\n")
        output.write(f"Total Movimientos: {total_movimientos}\n")
        output.write("\n")
        
        # SecciÃƒÂ³n de materiales
        if materiales:
            output.write("=== MATERIALES DEL INVENTARIO ===\n")
            df_materiales = pd.DataFrame(materiales)
            df_materiales = df_materiales[['nombre', 'cantidad', 'valor_unitario', 'valor_total']]
            df_materiales.columns = ['Material', 'Cantidad', 'Valor_Unitario', 'Valor_Total']
            df_materiales.to_csv(output, index=False)
            output.write("\n")
        
        # SecciÃƒÂ³n de movimientos
        if movimientos:
            output.write("=== HISTORIAL DE MOVIMIENTOS ===\n")
            df_movimientos = pd.DataFrame(movimientos)
            df_movimientos = df_movimientos[['fecha', 'accion', 'material_nombre', 'cantidad', 'usuario_nombre']]
            df_movimientos.columns = ['Fecha', 'AcciÃƒÂ³n', 'Material', 'Cantidad', 'Usuario']
            df_movimientos.to_csv(output, index=False)
        
        # Convertir a bytes
        output_str = output.getvalue()
        output_bytes = BytesIO(output_str.encode('utf-8'))
        output_bytes.seek(0)
        
        # Nombre del archivo
        nombre_oficina_safe = oficina['nombre'].replace(' ', '_').replace('/', '_')
        fecha = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'inventario_{nombre_oficina_safe}_{fecha}.csv'
        
        return send_file(
            output_bytes,
            mimetype='text/csv',
            as_attachment=True,
            download_name=filename
        )
        
    except Exception as e:
        print(f"Ã¢ÂÅ’ Error generando CSV de oficina: {e}")
        flash('Error al generar el archivo CSV', 'danger')
        return redirect('/reportes')

# ============================================================================
# FUNCIÃƒâ€œN ADICIONAL PARA DEPURAR DATOS DE OFICINA
# ============================================================================

@reportes_bp.route('/debug/oficina/<int:oficina_id>')
def debug_oficina_data(oficina_id):
    """Endpoint para depurar datos de una oficina especÃƒÂ­fica"""
    if not _require_login():
        return redirect('/login')
    
    try:
        from database import get_database_connection
        
        conn = get_database_connection()
        cursor = conn.cursor()
        
        # Obtener informaciÃƒÂ³n bÃƒÂ¡sica de la oficina
        cursor.execute("""
            SELECT OficinaId, NombreOficina, Ubicacion, Region, Estado 
            FROM Oficinas 
            WHERE OficinaId = ?
        """, (oficina_id,))
        
        oficina = cursor.fetchone()
        
        # Obtener materiales de esta oficina
        cursor.execute("""
            SELECT COUNT(*) as total_materiales, 
                   SUM(CantidadDisponible) as total_stock,
                   SUM(CantidadDisponible * ValorUnitario) as valor_total
            FROM Materiales 
            WHERE OficinaCreadoraId = ? AND Activo = 1
        """, (oficina_id,))
        
        materiales_stats = cursor.fetchone()
        
        # Obtener algunos materiales como muestra
        cursor.execute("""
            SELECT TOP 5 MaterialId, NombreElemento, CantidadDisponible, ValorUnitario
            FROM Materiales 
            WHERE OficinaCreadoraId = ? AND Activo = 1
        """, (oficina_id,))
        
        materiales_sample = cursor.fetchall()
        
        conn.close()
        
        # Preparar respuesta JSON para depuraciÃƒÂ³n
        debug_info = {
            'oficina': {
                'id': oficina[0] if oficina else None,
                'nombre': oficina[1] if oficina else None,
                'ubicacion': oficina[2] if oficina else None,
                'region': oficina[3] if oficina else None,
                'estado': oficina[4] if oficina else None
            },
            'materiales_stats': {
                'total_materiales': materiales_stats[0] if materiales_stats else 0,
                'total_stock': materiales_stats[1] if materiales_stats else 0,
                'valor_total': materiales_stats[2] if materiales_stats else 0
            },
            'materiales_sample': [
                {
                    'id': row[0],
                    'nombre': row[1],
                    'cantidad': row[2],
                    'valor_unitario': row[3]
                } for row in materiales_sample
            ]
        }
        
        return jsonify(debug_info)
        
    except Exception as e:
        return jsonify({'error': str(e)})

@reportes_bp.route('/material/<int:material_id>/historial')
def material_historial(material_id):
    """Obtiene el historial completo de un material"""
    if not _require_login():
        return redirect('/login')
    
    if not can_access('materiales', 'view'):
        flash('No tiene permisos para ver historial de materiales', 'warning')
        return redirect('/reportes')
    
    try:
        from database import get_database_connection
        
        conn = get_database_connection()
        cursor = conn.cursor()
        
        # Primero obtener informaciÃƒÂ³n bÃƒÂ¡sica del material
        cursor.execute("""
            SELECT m.MaterialId, m.NombreElemento, m.Descripcion, m.Categoria,
                   m.ValorUnitario, m.CantidadDisponible, m.StockMinimo,
                   o.NombreOficina as Ubicacion, m.Asignable
            FROM Materiales m
            LEFT JOIN Oficinas o ON m.OficinaCreadoraId = o.OficinaId
            WHERE m.MaterialId = ?
        """, (material_id,))
        
        material_data = cursor.fetchone()
        if not material_data:
            return jsonify({'error': 'Material no encontrado'})
        
        material = {
            'id': material_data[0],
            'nombre': material_data[1],
            'descripcion': material_data[2],
            'categoria': material_data[3],
            'valor_unitario': float(material_data[4] or 0),
            'cantidad': material_data[5],
            'stock_minimo': material_data[6],
            'ubicacion': material_data[7],
            'asignable': bool(material_data[8]) if material_data[8] is not None else False
        }
        
        # Buscar historial de movimientos para este material
        historial = []
        
        # Buscar en tabla de solicitudes
        cursor.execute("""
            SELECT sm.FechaSolicitud as Fecha, 'Solicitud' as Accion,
                   sm.CantidadSolicitada as Cantidad, 
                   o.NombreOficina as Oficina,
                   sm.UsuarioSolicitante as Usuario,
                   sm.Observacion as Observaciones
            FROM SolicitudesMaterial sm
            INNER JOIN Oficinas o ON sm.OficinaSolicitanteId = o.OficinaId
            WHERE sm.MaterialId = ?
            ORDER BY sm.FechaSolicitud DESC
        """, (material_id,))
        
        for row in cursor.fetchall():
            historial.append({
                'fecha': row[0],
                'accion': row[1],
                'cantidad': row[2],
                'oficina': row[3],
                'usuario': row[4],
                'observaciones': row[5]
            })
        
        # Buscar en tabla de prÃƒÂ©stamos
        cursor.execute("""
            SELECT pe.FechaPrestamo as Fecha, 'PrÃƒÂ©stamo' as Accion,
                   pe.CantidadPrestada as Cantidad,
                   o.NombreOficina as Oficina,
                   u.NombreUsuario as Usuario,
                   pe.Observaciones
            FROM PrestamosElementos pe
            INNER JOIN Oficinas o ON pe.OficinaId = o.OficinaId
            INNER JOIN Usuarios u ON pe.UsuarioSolicitanteId = u.UsuarioId
            WHERE pe.ElementoId = ? AND pe.Activo = 1
            ORDER BY pe.FechaPrestamo DESC
        """, (material_id,))
        
        for row in cursor.fetchall():
            historial.append({
                'fecha': row[0],
                'accion': row[1],
                'cantidad': row[2],
                'oficina': row[3],
                'usuario': row[4],
                'observaciones': row[5]
            })
        
        conn.close()
        
        # Ordenar historial por fecha
        historial_ordenado = sorted(historial, key=lambda x: x['fecha'], reverse=True)
        
        return jsonify({
            'material': material,
            'historial': historial_ordenado[:50]  # Limitar a 50 registros
        })
        
    except Exception as e:
        print(f"Ã¢ÂÅ’ Error obteniendo historial del material: {e}")
        return jsonify({'error': str(e)})

# ============================================================================
# API PARA DETALLE DE PRÃƒâ€°STAMOS - FUNCIÃƒâ€œN CORREGIDA
# ============================================================================

@reportes_bp.route('/api/prestamos/<int:prestamo_id>/detalle')
def api_prestamo_detalle(prestamo_id):
    """API para obtener detalle de un prÃƒÂ©stamo especÃƒÂ­fico - VERSIÃƒâ€œN CORREGIDA"""
    if not _require_login():
        return jsonify({'success': False, 'message': 'No autenticado'}), 401
    
    try:
        from database import get_database_connection
        
        conn = get_database_connection()
        cursor = conn.cursor()
        
        # Obtener informaciÃƒÂ³n detallada del prÃƒÂ©stamo - CONSULTA CORREGIDA
        cursor.execute("""
            SELECT 
                pe.PrestamoId,
                pe.ElementoId,
                ep.NombreElemento as MaterialNombre,
                pe.UsuarioSolicitanteId,
                u.NombreUsuario as SolicitanteNombre,
                pe.OficinaId,
                o.NombreOficina as OficinaNombre,
                pe.CantidadPrestada,
                pe.FechaPrestamo,
                pe.FechaDevolucionPrevista,
                pe.FechaDevolucionReal,
                pe.Estado,
                pe.Evento,
                pe.Observaciones,
                pe.UsuarioPrestador,
                pe.Activo,
                pe.UsuarioDevolucion,
                pe.UsuarioAprobador,
                pe.FechaAprobacion,
                pe.UsuarioRechazador,
                pe.FechaRechazo,
                DATEDIFF(day, pe.FechaPrestamo, GETDATE()) as DiasTranscurridos,
                CASE 
                    WHEN pe.Estado = 'PRESTADO' AND pe.FechaDevolucionPrevista < GETDATE() THEN 1
                    ELSE 0 
                END as Vencido,
                CASE 
                    WHEN pe.Estado = 'PRESTADO' 
                         AND pe.FechaDevolucionPrevista BETWEEN GETDATE() AND DATEADD(day, 7, GETDATE()) 
                    THEN 1
                    ELSE 0 
                END as PorVencer
            FROM PrestamosElementos pe
            INNER JOIN ElementosPublicitarios ep ON pe.ElementoId = ep.ElementoId
            INNER JOIN Usuarios u ON pe.UsuarioSolicitanteId = u.UsuarioId
            INNER JOIN Oficinas o ON pe.OficinaId = o.OficinaId
            WHERE pe.PrestamoId = ?
            AND pe.Activo = 1
        """, (prestamo_id,))
        
        prestamo_data = cursor.fetchone()
        
        if not prestamo_data:
            conn.close()
            return jsonify({'success': False, 'message': 'PrÃƒÂ©stamo no encontrado o inactivo'}), 404
        
        # Convertir a diccionario
        column_names = [column[0] for column in cursor.description]
        prestamo = dict(zip(column_names, prestamo_data))
        
        # Obtener historial de movimientos
        cursor.execute("""
            SELECT 
                FechaCambio as Fecha,
                EstadoNuevo as Accion,
                UsuarioCambio as Usuario,
                Observaciones
            FROM PrestamosHistorialEstados 
            WHERE PrestamoId = ?
            ORDER BY FechaCambio DESC
        """, (prestamo_id,))
        
        historial = []
        for row in cursor.fetchall():
            historial.append({
                'fecha': row[0].strftime('%Y-%m-%d %H:%M:%S') if row[0] else None,
                'accion': row[1],
                'usuario': row[2],
                'observaciones': row[3] or ''
            })
        
        prestamo['historial'] = historial
        
        # Convertir fechas a formato string para JSON
        date_fields = ['FechaPrestamo', 'FechaDevolucionPrevista', 'FechaDevolucionReal', 
                      'FechaAprobacion', 'FechaRechazo']
        for field in date_fields:
            if prestamo.get(field):
                prestamo[field] = prestamo[field].strftime('%Y-%m-%d %H:%M:%S')
        
        conn.close()
        
        return jsonify({
            'success': True,
            'prestamo': prestamo
        })
        
    except Exception as e:
        print(f"Ã¢ÂÅ’ Error obteniendo detalle del prÃƒÂ©stamo: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'Error interno del servidor: {str(e)}'
        }), 500

# ============================================================================
# API PARA REGISTRAR DEVOLUCIÃƒâ€œN DE PRÃƒâ€°STAMO
# ============================================================================

@reportes_bp.route('/api/prestamos/<int:prestamo_id>/devolver', methods=['POST'])
def api_prestamo_devolver(prestamo_id):
    """API para registrar devoluciÃƒÂ³n de un prÃƒÂ©stamo"""
    if not _require_login():
        return jsonify({'success': False, 'message': 'No autenticado'}), 401
    
    # Verificar permisos
    if not can_access('prestamos', 'return'):
        return jsonify({'success': False, 'message': 'No tiene permisos para registrar devoluciones'}), 403
    
    try:
        from database import get_database_connection
        
        conn = get_database_connection()
        cursor = conn.cursor()
        
        # Verificar que el prÃƒÂ©stamo existe y estÃƒÂ¡ activo
        cursor.execute("""
            SELECT Estado, ElementoId, CantidadPrestada 
            FROM PrestamosElementos 
            WHERE PrestamoId = ? AND Activo = 1
        """, (prestamo_id,))
        
        prestamo = cursor.fetchone()
        if not prestamo:
            conn.close()
            return jsonify({'success': False, 'message': 'PrÃƒÂ©stamo no encontrado o inactivo'}), 404
        
        estado, elemento_id, cantidad = prestamo
        
        if estado != 'PRESTADO':
            conn.close()
            return jsonify({'success': False, 'message': 'El prÃƒÂ©stamo no estÃƒÂ¡ en estado PRESTADO'}), 400
        
        # Obtener usuario actual
        usuario_nombre = session.get('nombre_usuario', 'Sistema')
        
        # Registrar devoluciÃƒÂ³n
        cursor.execute("""
            UPDATE PrestamosElementos 
            SET Estado = 'DEVUELTO',
                FechaDevolucionReal = GETDATE(),
                UsuarioDevolucion = ?,
                FechaActualizacion = GETDATE(),
                UsuarioActualizacion = ?
            WHERE PrestamoId = ?
        """, (usuario_nombre, usuario_nombre, prestamo_id))
        
        # Registrar en historial de estados
        cursor.execute("""
            INSERT INTO PrestamosHistorialEstados 
            (PrestamoId, EstadoAnterior, EstadoNuevo, UsuarioCambio, FechaCambio, Observaciones, TipoAccion)
            VALUES (?, ?, ?, ?, GETDATE(), 'DevoluciÃƒÂ³n registrada', 'DEVOLUCION')
        """, (prestamo_id, 'PRESTADO', 'DEVUELTO', usuario_nombre))
        
        # Actualizar stock del elemento
        cursor.execute("""
            UPDATE ElementosPublicitarios 
            SET CantidadDisponible = CantidadDisponible + ?
            WHERE ElementoId = ?
        """, (cantidad, elemento_id))
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'DevoluciÃƒÂ³n registrada exitosamente'
        })
        
    except Exception as e:
        print(f"Ã¢ÂÅ’ Error registrando devoluciÃƒÂ³n del prÃƒÂ©stamo: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'Error al registrar la devoluciÃƒÂ³n: {str(e)}'
        }), 500