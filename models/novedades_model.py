# models/novedades_model.py
from database import get_database_connection
from datetime import datetime

class NovedadModel:
    
    @staticmethod
    def obtener_todas(filtro_estado=None):
        """Obtiene todas las novedades, opcionalmente filtradas por estado"""
        conn = get_database_connection()
        if conn is None:
            print("❌ No se pudo conectar a la base de datos")
            return []
        
        cursor = conn.cursor()
        try:
            # Consulta con manejo de errores para tablas que pueden no existir
            sql = """
                SELECT 
                    ns.NovedadId,
                    ns.SolicitudId,
                    COALESCE(sm.MaterialId, 0) as MaterialId,
                    ns.TipoNovedad,
                    ns.Descripcion,
                    COALESCE(ns.EstadoNovedad, 'pendiente') as Estado,
                    ns.FechaRegistro as FechaReporte,
                    COALESCE(ns.UsuarioRegistra, 'Sistema') as UsuarioReporta,
                    ns.FechaResolucion,
                    ns.UsuarioResuelve,
                    COALESCE(ns.ObservacionesResolucion, '') as ComentarioResolucion,
                    COALESCE(m.NombreElemento, 'No especificado') as MaterialNombre,
                    COALESCE(sm.CantidadSolicitada, 0) as CantidadSolicitada,
                    COALESCE(sm.CantidadEntregada, 0) as CantidadEntregada,
                    COALESCE(o.NombreOficina, 'No especificada') as NombreOficina,
                    o.OficinaId,
                    COALESCE(ns.Prioridad, 'media') as Prioridad
                FROM NovedadesSolicitudes ns
                LEFT JOIN SolicitudesMaterial sm ON ns.SolicitudId = sm.SolicitudId
                LEFT JOIN Materiales m ON sm.MaterialId = m.MaterialId
                LEFT JOIN Oficinas o ON sm.OficinaSolicitanteId = o.OficinaId
            """
            
            params = []
            if filtro_estado:
                sql += " WHERE ns.EstadoNovedad = ?"
                params.append(filtro_estado)
            
            sql += " ORDER BY ns.FechaRegistro DESC"
            
            cursor.execute(sql, params)
            
            novedades = []
            for row in cursor.fetchall():
                # Manejar fecha de forma segura
                fecha_reporte = row[6]
                if fecha_reporte:
                    if isinstance(fecha_reporte, str):
                        try:
                            fecha_reporte = datetime.strptime(fecha_reporte, '%Y-%m-%d %H:%M:%S')
                        except:
                            pass
                
                novedades.append({
                    "id": row[0],
                    "solicitud_id": row[1],
                    "material_id": row[2] if row[2] is not None else 0,
                    "tipo": row[3] or "General",
                    "tipo_novedad": row[3] or "General",
                    "descripcion": row[4] or "",
                    "estado": row[5] or "pendiente",
                    "fecha_reporte": fecha_reporte,
                    "usuario_registra": row[7] or "Sistema",
                    "usuario_reporta": row[7] or "Sistema",
                    "fecha_resolucion": row[8],
                    "usuario_resuelve": row[9],
                    "comentario_resolucion": row[10] or "",
                    "material_nombre": row[11] or "No especificado",
                    "cantidad_solicitada": row[12] or 0,
                    "cantidad_entregada": row[13] or 0,
                    "oficina_nombre": row[14] or "No especificada",
                    "oficina_id": row[15],
                    "prioridad": row[16] if len(row) > 16 else "media"
                })
            
            print(f"✅ Novedades obtenidas: {len(novedades)}")
            return novedades
            
        except Exception as e:
            print(f"❌ Error obteniendo novedades: {e}")
            import traceback
            traceback.print_exc()
            
            # Intentar consulta alternativa más simple
            try:
                cursor.execute("""
                    SELECT 
                        NovedadId, SolicitudId, TipoNovedad, Descripcion, 
                        EstadoNovedad, FechaRegistro, UsuarioRegistra,
                        FechaResolucion, UsuarioResuelve, ObservacionesResolucion
                    FROM NovedadesSolicitudes
                    ORDER BY FechaRegistro DESC
                """)
                
                novedades = []
                for row in cursor.fetchall():
                    novedades.append({
                        "id": row[0],
                        "solicitud_id": row[1],
                        "material_id": 0,
                        "tipo": row[2] or "General",
                        "tipo_novedad": row[2] or "General",
                        "descripcion": row[3] or "",
                        "estado": row[4] or "pendiente",
                        "fecha_reporte": row[5],
                        "usuario_registra": row[6] or "Sistema",
                        "usuario_reporta": row[6] or "Sistema",
                        "fecha_resolucion": row[7],
                        "usuario_resuelve": row[8],
                        "comentario_resolucion": row[9] or "",
                        "material_nombre": "No especificado",
                        "cantidad_solicitada": 0,
                        "cantidad_entregada": 0,
                        "oficina_nombre": "No especificada",
                        "oficina_id": None,
                        "prioridad": "media"
                    })
                
                print(f"⚠️ Novedades obtenidas (consulta alternativa): {len(novedades)}")
                return novedades
                
            except Exception as e2:
                print(f"❌ Error en consulta alternativa: {e2}")
                return []
        finally:
            try:
                cursor.close()
                conn.close()
            except:
                pass
    
    @staticmethod
    def obtener_por_id(novedad_id):
        """Obtiene una novedad por su ID"""
        conn = get_database_connection()
        if conn is None:
            return None
        
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT 
                    ns.NovedadId,
                    ns.SolicitudId,
                    COALESCE(sm.MaterialId, 0) as MaterialId,
                    ns.TipoNovedad,
                    ns.Descripcion,
                    COALESCE(ns.EstadoNovedad, 'pendiente') as Estado,
                    ns.FechaRegistro as FechaReporte,
                    COALESCE(ns.UsuarioRegistra, 'Sistema') as UsuarioReporta,
                    ns.FechaResolucion,
                    ns.UsuarioResuelve,
                    COALESCE(ns.ObservacionesResolucion, '') as ComentarioResolucion,
                    COALESCE(m.NombreElemento, 'No especificado') as MaterialNombre,
                    COALESCE(sm.CantidadSolicitada, 0),
                    COALESCE(sm.CantidadEntregada, 0),
                    COALESCE(o.NombreOficina, 'No especificada'),
                    o.OficinaId
                FROM NovedadesSolicitudes ns
                LEFT JOIN SolicitudesMaterial sm ON ns.SolicitudId = sm.SolicitudId
                LEFT JOIN Materiales m ON sm.MaterialId = m.MaterialId
                LEFT JOIN Oficinas o ON sm.OficinaSolicitanteId = o.OficinaId
                WHERE ns.NovedadId = ?
            """, (novedad_id,))
            
            row = cursor.fetchone()
            if row:
                return {
                    "id": row[0],
                    "solicitud_id": row[1],
                    "material_id": row[2] if row[2] is not None else 0,
                    "tipo": row[3] or "General",
                    "tipo_novedad": row[3] or "General",
                    "descripcion": row[4] or "",
                    "estado": row[5] or "pendiente",
                    "fecha_reporte": row[6],
                    "usuario_registra": row[7] or "Sistema",
                    "usuario_reporta": row[7] or "Sistema",
                    "fecha_resolucion": row[8],
                    "usuario_resuelve": row[9],
                    "comentario_resolucion": row[10] or "",
                    "material_nombre": row[11] or "No especificado",
                    "cantidad_solicitada": row[12] or 0,
                    "cantidad_entregada": row[13] or 0,
                    "oficina_nombre": row[14] or "No especificada",
                    "oficina_id": row[15]
                }
            return None
            
        except Exception as e:
            print(f"❌ Error obteniendo novedad por ID: {e}")
            import traceback
            traceback.print_exc()
            return None
        finally:
            try:
                cursor.close()
                conn.close()
            except:
                pass
    
    @staticmethod
    def crear(solicitud_id, tipo_novedad, descripcion, usuario_reporta, cantidad_afectada=None, ruta_imagen=None):
        """Crea una nueva novedad"""
        conn = get_database_connection()
        if conn is None:
            return None
    
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO NovedadesSolicitudes (
                    SolicitudId, TipoNovedad, Descripcion, CantidadAfectada,
                    EstadoNovedad, UsuarioRegistra, FechaRegistro, RutaImagen
                )
                VALUES (?, ?, ?, ?, 'registrada', ?, GETDATE(), ?)
            """, (solicitud_id, tipo_novedad, descripcion, cantidad_afectada, usuario_reporta, ruta_imagen))
        
            conn.commit()
            print(f"✅ Novedad creada para solicitud {solicitud_id}. Imagen: {ruta_imagen}")
            return cursor.rowcount > 0
        
        except Exception as e:
            conn.rollback()
            print(f"❌ Error creando novedad: {e}")
            import traceback
            traceback.print_exc()
            return None
        finally:
            cursor.close()
            conn.close()
    
    @staticmethod
    def actualizar_estado(novedad_id, nuevo_estado, usuario_resuelve, comentario=""):
        """Actualiza el estado de una novedad"""
        conn = get_database_connection()
        if conn is None:
            return False
        
        cursor = conn.cursor()
        try:
            cursor.execute("""
                UPDATE NovedadesSolicitudes 
                SET EstadoNovedad = ?,
                    FechaResolucion = GETDATE(),
                    UsuarioResuelve = ?,
                    ObservacionesResolucion = ?
                WHERE NovedadId = ?
            """, (nuevo_estado, usuario_resuelve, comentario, novedad_id))
            
            conn.commit()
            return cursor.rowcount > 0
            
        except Exception as e:
            try:
                conn.rollback()
            except:
                pass
            print(f"❌ Error actualizando novedad: {e}")
            import traceback
            traceback.print_exc()
            return False
        finally:
            try:
                cursor.close()
                conn.close()
            except:
                pass
    
    @staticmethod
    def obtener_estadisticas():
        """Obtiene estadísticas de novedades"""
        conn = get_database_connection()
        if conn is None:
            return {"total": 0, "pendientes": 0, "resueltas": 0, "en_proceso": 0}
        
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN EstadoNovedad IN ('pendiente', 'registrada') THEN 1 ELSE 0 END) as pendientes,
                    SUM(CASE WHEN EstadoNovedad IN ('resuelto', 'resuelta') THEN 1 ELSE 0 END) as resueltas,
                    SUM(CASE WHEN EstadoNovedad = 'en_proceso' THEN 1 ELSE 0 END) as en_proceso
                FROM NovedadesSolicitudes
            """)
            
            row = cursor.fetchone()
            if row:
                return {
                    "total": row[0] or 0,
                    "pendientes": row[1] or 0,
                    "resueltas": row[2] or 0,
                    "en_proceso": row[3] or 0
                }
            return {"total": 0, "pendientes": 0, "resueltas": 0, "en_proceso": 0}
            
        except Exception as e:
            print(f"❌ Error obteniendo estadísticas de novedades: {e}")
            import traceback
            traceback.print_exc()
            return {"total": 0, "pendientes": 0, "resueltas": 0, "en_proceso": 0}
        finally:
            try:
                cursor.close()
                conn.close()
            except:
                pass
    
    @staticmethod
    def obtener_por_solicitud(solicitud_id):
        """Obtiene las novedades asociadas a una solicitud"""
        conn = get_database_connection()
        if conn is None:
            return []
        
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT 
                    ns.NovedadId,
                    ns.TipoNovedad,
                    ns.Descripcion,
                    COALESCE(ns.EstadoNovedad, 'pendiente') as Estado,
                    ns.FechaRegistro as FechaReporte,
                    COALESCE(ns.UsuarioRegistra, 'Sistema') as UsuarioReporta,
                    ns.FechaResolucion,
                    ns.UsuarioResuelve,
                    COALESCE(ns.ObservacionesResolucion, '') as ComentarioResolucion,
                    COALESCE(m.NombreElemento, 'No especificado') as MaterialNombre,
                    ns.CantidadAfectada,
                    ns.RutaImagen as NovedadImagen,
                    m.RutaImagen as MaterialImagen
                FROM NovedadesSolicitudes ns
                LEFT JOIN SolicitudesMaterial sm ON ns.SolicitudId = sm.SolicitudId
                LEFT JOIN Materiales m ON sm.MaterialId = m.MaterialId
                WHERE ns.SolicitudId = ?
                ORDER BY ns.FechaRegistro DESC
            """, (solicitud_id,))
            
            novedades = []
            for row in cursor.fetchall():
                novedades.append({
                    "id": row[0],
                    "novedad_id": row[0],
                    "tipo": row[1] or "General",
                    "tipo_novedad": row[1] or "General",
                    "descripcion": row[2] or "",
                    "estado": row[3] or "pendiente",
                    "fecha_reporte": row[4],
                    "fecha_registro": row[4],
                    "usuario_registra": row[5] or "Sistema",
                    "usuario_reporta": row[5] or "Sistema",
                    "fecha_resolucion": row[6],
                    "usuario_resuelve": row[7],
                    "comentario_resolucion": row[8] or "",
                    "material_nombre": row[9] or "No especificado",
                    "cantidad_afectada": row[10] or 0,
                    "novedad_imagen": row[11],
                    "material_imagen": row[12]
                })
            
            return novedades
            
        except Exception as e:
            print(f"❌ Error obteniendo novedades por solicitud: {e}")
            import traceback
            traceback.print_exc()
            return []
        finally:
            try:
                cursor.close()
                conn.close()
            except:
                pass
    
    @staticmethod
    def obtener_tipos_disponibles():
        """Obtiene los tipos de novedad únicos que existen"""
        conn = get_database_connection()
        if conn is None:
            return ['Daño', 'Faltante', 'Error en cantidad', 'Otro']
        
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT DISTINCT TipoNovedad 
                FROM NovedadesSolicitudes 
                WHERE TipoNovedad IS NOT NULL AND TipoNovedad != ''
                ORDER BY TipoNovedad
            """)
            
            tipos = [row[0] for row in cursor.fetchall() if row[0]]
            
            # Si no hay tipos, retornar lista por defecto
            if not tipos:
                tipos = ['Daño', 'Faltante', 'Error en cantidad', 'Otro']
            
            return tipos
            
        except Exception as e:
            print(f"❌ Error obteniendo tipos de novedad: {e}")
            return ['Daño', 'Faltante', 'Error en cantidad', 'Otro']
        finally:
            try:
                cursor.close()
                conn.close()
            except:
                pass