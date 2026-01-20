# models/novedades_model.py
"""
Modelo para gestión de novedades de solicitudes.
"""
from database import get_database_connection
import logging

logger = logging.getLogger(__name__)


class NovedadModel:
    """Modelo para operaciones CRUD de novedades"""
    
    @staticmethod
    def obtener_todas(filtro_estado=None):
        """
        Obtiene todas las novedades con información relacionada
        
        Args:
            filtro_estado: Filtrar por estado de novedad (opcional)
            
        Returns:
            list: Lista de novedades
        """
        conn = get_database_connection()
        if conn is None:
            return []
        
        cursor = conn.cursor()
        try:
            sql = """
                SELECT 
                    ns.NovedadId,
                    ns.SolicitudId,
                    ns.TipoNovedad,
                    ns.Descripcion,
                    ns.CantidadAfectada,
                    ns.EstadoNovedad,
                    ns.UsuarioRegistra,
                    ns.FechaRegistro,
                    ns.UsuarioResuelve,
                    ns.FechaResolucion,
                    ns.ObservacionesResolucion,
                    ns.RutaImagen,
                    sm.UsuarioSolicitante,
                    m.NombreElemento as MaterialNombre,
                    o.NombreOficina as OficinaNombre
                FROM NovedadesSolicitudes ns
                INNER JOIN SolicitudesMaterial sm ON ns.SolicitudId = sm.SolicitudId
                INNER JOIN Materiales m ON sm.MaterialId = m.MaterialId
                INNER JOIN Oficinas o ON sm.OficinaSolicitanteId = o.OficinaId
            """
            
            params = []
            if filtro_estado:
                sql += " WHERE ns.EstadoNovedad = ?"
                params.append(filtro_estado)
            
            sql += " ORDER BY ns.FechaRegistro DESC"
            
            cursor.execute(sql, params)
            
            novedades = []
            for row in cursor.fetchall():
                novedades.append({
                    'novedad_id': row[0],
                    'id': row[0],  # Alias para compatibilidad
                    'solicitud_id': row[1],
                    'tipo_novedad': row[2],
                    'tipo': row[2],  # Alias
                    'descripcion': row[3],
                    'cantidad_afectada': row[4] or 0,
                    'estado_novedad': row[5],
                    'estado': row[5],  # Alias
                    'usuario_registra': row[6],
                    'fecha_registro': row[7],
                    'usuario_resuelve': row[8],
                    'fecha_resolucion': row[9],
                    'observaciones_resolucion': row[10],
                    'ruta_imagen': row[11],
                    'usuario_solicitante': row[12],
                    'material_nombre': row[13],
                    'oficina_nombre': row[14]
                })
            
            return novedades
            
        except Exception as e:
            logger.error("Error obteniendo novedades: [error](%s)", type(e).__name__)
            return []
        finally:
            cursor.close()
            conn.close()
    
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
                    ns.TipoNovedad,
                    ns.Descripcion,
                    ns.CantidadAfectada,
                    ns.EstadoNovedad,
                    ns.UsuarioRegistra,
                    ns.FechaRegistro,
                    ns.UsuarioResuelve,
                    ns.FechaResolucion,
                    ns.ObservacionesResolucion,
                    ns.RutaImagen,
                    sm.UsuarioSolicitante,
                    m.NombreElemento as MaterialNombre,
                    o.NombreOficina as OficinaNombre
                FROM NovedadesSolicitudes ns
                INNER JOIN SolicitudesMaterial sm ON ns.SolicitudId = sm.SolicitudId
                INNER JOIN Materiales m ON sm.MaterialId = m.MaterialId
                INNER JOIN Oficinas o ON sm.OficinaSolicitanteId = o.OficinaId
                WHERE ns.NovedadId = ?
            """, (novedad_id,))
            
            row = cursor.fetchone()
            if row:
                return {
                    'novedad_id': row[0],
                    'id': row[0],
                    'solicitud_id': row[1],
                    'tipo_novedad': row[2],
                    'tipo': row[2],
                    'descripcion': row[3],
                    'cantidad_afectada': row[4] or 0,
                    'estado_novedad': row[5],
                    'estado': row[5],
                    'usuario_registra': row[6],
                    'fecha_registro': row[7],
                    'usuario_resuelve': row[8],
                    'fecha_resolucion': row[9],
                    'observaciones_resolucion': row[10],
                    'ruta_imagen': row[11],
                    'usuario_solicitante': row[12],
                    'material_nombre': row[13],
                    'oficina_nombre': row[14]
                }
            return None
            
        except Exception as e:
            logger.error("Error obteniendo novedad {novedad_id}: [error](%s)", type(e).__name__)
            return None
        finally:
            cursor.close()
            conn.close()
    
    @staticmethod
    def crear(solicitud_id, tipo_novedad, descripcion, usuario_reporta, cantidad_afectada=None, ruta_imagen=None):
        """
        Crea una nueva novedad
        
        Args:
            solicitud_id: ID de la solicitud
            tipo_novedad: Tipo de novedad
            descripcion: Descripción de la novedad
            usuario_reporta: Usuario que registra
            cantidad_afectada: Cantidad afectada (opcional)
            ruta_imagen: Ruta de la imagen adjunta (opcional)
            
        Returns:
            bool: True si se creó correctamente
        """
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
            logger.info(f"Novedad creada para solicitud {solicitud_id}. Imagen: {ruta_imagen}")
            return cursor.rowcount > 0
            
        except Exception as e:
            conn.rollback()
            logger.error("Error creando novedad: [error](%s)", type(e).__name__)
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
            logger.info(f"Novedad {novedad_id} actualizada a estado {nuevo_estado}")
            return cursor.rowcount > 0
            
        except Exception as e:
            conn.rollback()
            logger.error("Error actualizando novedad: [error](%s)", type(e).__name__)
            return False
        finally:
            cursor.close()
            conn.close()
    
    @staticmethod
    def obtener_estadisticas():
        """Obtiene estadísticas de novedades"""
        conn = get_database_connection()
        if conn is None:
            return {"total": 0, "pendientes": 0, "resueltas": 0, "aceptadas": 0, "rechazadas": 0}
        
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN EstadoNovedad = 'registrada' THEN 1 ELSE 0 END) as pendientes,
                    SUM(CASE WHEN EstadoNovedad IN ('resuelta', 'aceptada', 'rechazada') THEN 1 ELSE 0 END) as resueltas,
                    SUM(CASE WHEN EstadoNovedad = 'aceptada' THEN 1 ELSE 0 END) as aceptadas,
                    SUM(CASE WHEN EstadoNovedad = 'rechazada' THEN 1 ELSE 0 END) as rechazadas
                FROM NovedadesSolicitudes
            """)
            
            row = cursor.fetchone()
            if row:
                return {
                    "total": row[0] or 0,
                    "pendientes": row[1] or 0,
                    "resueltas": row[2] or 0,
                    "aceptadas": row[3] or 0,
                    "rechazadas": row[4] or 0
                }
            return {"total": 0, "pendientes": 0, "resueltas": 0, "aceptadas": 0, "rechazadas": 0}
            
        except Exception as e:
            logger.error("Error obteniendo estadísticas: [error](%s)", type(e).__name__)
            return {"total": 0, "pendientes": 0, "resueltas": 0, "aceptadas": 0, "rechazadas": 0}
        finally:
            cursor.close()
            conn.close()
    
    @staticmethod
    def obtener_por_solicitud(solicitud_id):
        """Obtiene todas las novedades de una solicitud específica"""
        conn = get_database_connection()
        if conn is None:
            return []
        
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT 
                    ns.NovedadId,
                    ns.SolicitudId,
                    ns.TipoNovedad,
                    ns.Descripcion,
                    ns.CantidadAfectada,
                    ns.EstadoNovedad,
                    ns.UsuarioRegistra,
                    ns.FechaRegistro,
                    ns.UsuarioResuelve,
                    ns.FechaResolucion,
                    ns.ObservacionesResolucion,
                    ns.RutaImagen
                FROM NovedadesSolicitudes ns
                WHERE ns.SolicitudId = ?
                ORDER BY ns.FechaRegistro DESC
            """, (solicitud_id,))
            
            novedades = []
            for row in cursor.fetchall():
                novedades.append({
                    'novedad_id': row[0],
                    'id': row[0],
                    'solicitud_id': row[1],
                    'tipo_novedad': row[2],
                    'tipo': row[2],
                    'descripcion': row[3],
                    'cantidad_afectada': row[4] or 0,
                    'estado_novedad': row[5],
                    'estado': row[5],
                    'usuario_registra': row[6],
                    'fecha_registro': row[7],
                    'usuario_resuelve': row[8],
                    'fecha_resolucion': row[9],
                    'observaciones_resolucion': row[10],
                    'ruta_imagen': row[11]
                })
            
            return novedades
            
        except Exception as e:
            logger.error("Error obteniendo novedades de solicitud {solicitud_id}: [error](%s)", type(e).__name__)
            return []
        finally:
            cursor.close()
            conn.close()
    
    @staticmethod
    def obtener_novedades_pendientes():
        """Obtiene todas las novedades en estado 'registrada' (pendientes)"""
        return NovedadModel.obtener_todas(filtro_estado='registrada')
    
    @staticmethod
    def obtener_tipos_disponibles():
        """Retorna los tipos de novedad disponibles"""
        return [
            {'id': 'danado', 'nombre': 'Material Dañado'},
            {'id': 'faltante', 'nombre': 'Material Faltante'},
            {'id': 'exceso', 'nombre': 'Exceso de Material'},
            {'id': 'equivocado', 'nombre': 'Material Equivocado'},
            {'id': 'defectuoso', 'nombre': 'Material Defectuoso'},
            {'id': 'otro', 'nombre': 'Otro'}
        ]
