# models/novedades_model.py
"""
Modelo para gestión de novedades de solicitudes.
Maneja todas las operaciones CRUD relacionadas con novedades.
"""

from database import get_database_connection
import logging

logger = logging.getLogger(__name__)


class NovedadModel:
    """Modelo para operaciones con novedades de solicitudes"""
    
    @staticmethod
    def obtener_todas(filtro_estado=None):
        """
        Obtiene todas las novedades, opcionalmente filtradas por estado.
        
        Args:
            filtro_estado: Estado para filtrar ('registrada', 'aceptada', 'rechazada')
        
        Returns:
            Lista de diccionarios con información de novedades
        """
        conn = get_database_connection()
        if conn is None:
            logger.error("No se pudo conectar a la base de datos")
            return []
        
        cursor = conn.cursor()
        try:
            sql = """
                SELECT 
                    ns.NovedadId,
                    ns.SolicitudId,
                    COALESCE(sm.MaterialId, 0) as MaterialId,
                    ns.TipoNovedad,
                    ns.Descripcion,
                    ns.EstadoNovedad as Estado,
                    ns.FechaRegistro as FechaReporte,
                    ns.UsuarioRegistra as UsuarioReporta,
                    ns.FechaResolucion,
                    ns.UsuarioResuelve,
                    ns.ObservacionesResolucion as ComentarioResolucion,
                    COALESCE(m.NombreElemento, 'No especificado') as MaterialNombre,
                    COALESCE(sm.CantidadSolicitada, 0) as CantidadSolicitada,
                    COALESCE(sm.CantidadEntregada, 0) as CantidadEntregada,
                    COALESCE(o.NombreOficina, 'No especificada') as NombreOficina,
                    o.OficinaId,
                    ns.CantidadAfectada,
                    ns.RutaImagen
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
                novedades.append({
                    "id": row[0],
                    "novedad_id": row[0],  # Alias para compatibilidad
                    "solicitud_id": row[1],
                    "material_id": row[2],
                    "tipo_novedad": row[3],
                    "descripcion": row[4],
                    "estado": row[5],
                    "fecha_reporte": row[6],
                    "fecha_registro": row[6],  # Alias
                    "usuario_reporta": row[7],
                    "usuario_registra": row[7],  # Alias
                    "fecha_resolucion": row[8],
                    "usuario_resuelve": row[9],
                    "comentario_resolucion": row[10],
                    "observaciones_resolucion": row[10],  # Alias
                    "material_nombre": row[11],
                    "cantidad_solicitada": row[12],
                    "cantidad_entregada": row[13],
                    "oficina_nombre": row[14],
                    "oficina_id": row[15],
                    "cantidad_afectada": row[16] or 0,
                    "ruta_imagen": row[17]
                })
            
            logger.info(f"Se obtuvieron {len(novedades)} novedades")
            return novedades
            
        except Exception as e:
            logger.error(f"Error obteniendo novedades: {e}")
            import traceback
            traceback.print_exc()
            return []
        finally:
            cursor.close()
            conn.close()
    
    @staticmethod
    def obtener_por_id(novedad_id):
        """
        Obtiene una novedad por su ID.
        
        Args:
            novedad_id: ID de la novedad
        
        Returns:
            Diccionario con información de la novedad o None
        """
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
                    ns.EstadoNovedad as Estado,
                    ns.FechaRegistro as FechaReporte,
                    ns.UsuarioRegistra as UsuarioReporta,
                    ns.FechaResolucion,
                    ns.UsuarioResuelve,
                    ns.ObservacionesResolucion as ComentarioResolucion,
                    COALESCE(m.NombreElemento, 'No especificado') as MaterialNombre,
                    COALESCE(sm.CantidadSolicitada, 0) as CantidadSolicitada,
                    COALESCE(sm.CantidadEntregada, 0) as CantidadEntregada,
                    COALESCE(o.NombreOficina, 'No especificada') as NombreOficina,
                    o.OficinaId,
                    ns.CantidadAfectada,
                    ns.RutaImagen
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
                    "novedad_id": row[0],
                    "solicitud_id": row[1],
                    "material_id": row[2],
                    "tipo_novedad": row[3],
                    "descripcion": row[4],
                    "estado": row[5],
                    "fecha_reporte": row[6],
                    "fecha_registro": row[6],
                    "usuario_reporta": row[7],
                    "usuario_registra": row[7],
                    "fecha_resolucion": row[8],
                    "usuario_resuelve": row[9],
                    "comentario_resolucion": row[10],
                    "observaciones_resolucion": row[10],
                    "material_nombre": row[11],
                    "cantidad_solicitada": row[12],
                    "cantidad_entregada": row[13],
                    "oficina_nombre": row[14],
                    "oficina_id": row[15],
                    "cantidad_afectada": row[16] or 0,
                    "ruta_imagen": row[17]
                }
            return None
            
        except Exception as e:
            logger.error(f"Error obteniendo novedad por ID: {e}")
            import traceback
            traceback.print_exc()
            return None
        finally:
            cursor.close()
            conn.close()
    
    @staticmethod
    def crear(solicitud_id, tipo_novedad, descripcion, usuario_registra, 
              cantidad_afectada=None, ruta_imagen=None):
        """
        Crea una nueva novedad.
        
        Args:
            solicitud_id: ID de la solicitud relacionada
            tipo_novedad: Tipo de novedad (daño, pérdida, etc.)
            descripcion: Descripción detallada
            usuario_registra: Usuario que registra la novedad
            cantidad_afectada: Cantidad de material afectada
            ruta_imagen: Ruta de imagen de evidencia (opcional)
        
        Returns:
            True si se creó exitosamente, None si hubo error
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
            """, (solicitud_id, tipo_novedad, descripcion, cantidad_afectada, 
                  usuario_registra, ruta_imagen))
            
            conn.commit()
            logger.info(f"Novedad creada para solicitud {solicitud_id}")
            return cursor.rowcount > 0
            
        except Exception as e:
            conn.rollback()
            logger.error(f"Error creando novedad: {e}")
            import traceback
            traceback.print_exc()
            return None
        finally:
            cursor.close()
            conn.close()
    
    @staticmethod
    def actualizar_estado(novedad_id, estado, usuario_resuelve, observaciones_resolucion=""):
        """
        Actualiza el estado de una novedad.
        
        Args:
            novedad_id: ID de la novedad
            estado: Nuevo estado ('aceptada', 'rechazada')
            usuario_resuelve: Usuario que resuelve la novedad
            observaciones_resolucion: Observaciones de la resolución
        
        Returns:
            True si se actualizó exitosamente, False si hubo error
        """
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
            """, (estado, usuario_resuelve, observaciones_resolucion, novedad_id))
            
            conn.commit()
            logger.info(f"Novedad {novedad_id} actualizada a estado {estado}")
            return cursor.rowcount > 0
            
        except Exception as e:
            conn.rollback()
            logger.error(f"Error actualizando novedad: {e}")
            import traceback
            traceback.print_exc()
            return False
        finally:
            cursor.close()
            conn.close()
    
    @staticmethod
    def obtener_estadisticas():
        """
        Obtiene estadísticas de novedades.
        
        Returns:
            Diccionario con total, pendientes y resueltas
        """
        conn = get_database_connection()
        if conn is None:
            return {"total": 0, "pendientes": 0, "resueltas": 0, "aceptadas": 0, "rechazadas": 0}
        
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN EstadoNovedad = 'registrada' THEN 1 ELSE 0 END) as pendientes,
                    SUM(CASE WHEN EstadoNovedad IN ('aceptada', 'rechazada') THEN 1 ELSE 0 END) as resueltas,
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
            logger.error(f"Error obteniendo estadísticas de novedades: {e}")
            import traceback
            traceback.print_exc()
            return {"total": 0, "pendientes": 0, "resueltas": 0, "aceptadas": 0, "rechazadas": 0}
        finally:
            cursor.close()
            conn.close()
    
    @staticmethod
    def obtener_por_solicitud(solicitud_id):
        """
        Obtiene las novedades asociadas a una solicitud.
        
        Args:
            solicitud_id: ID de la solicitud
        
        Returns:
            Lista de novedades de la solicitud
        """
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
                    ns.EstadoNovedad as Estado,
                    ns.FechaRegistro as FechaReporte,
                    ns.UsuarioRegistra as UsuarioReporta,
                    ns.FechaResolucion,
                    ns.UsuarioResuelve,
                    ns.ObservacionesResolucion as ComentarioResolucion,
                    COALESCE(m.NombreElemento, 'No especificado') as MaterialNombre,
                    ns.CantidadAfectada,
                    ns.RutaImagen
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
                    "tipo_novedad": row[1],
                    "descripcion": row[2],
                    "estado": row[3],
                    "fecha_reporte": row[4],
                    "fecha_registro": row[4],
                    "usuario_reporta": row[5],
                    "usuario_registra": row[5],
                    "fecha_resolucion": row[6],
                    "usuario_resuelve": row[7],
                    "comentario_resolucion": row[8],
                    "observaciones_resolucion": row[8],
                    "material_nombre": row[9],
                    "cantidad_afectada": row[10] or 0,
                    "ruta_imagen": row[11]
                })
            
            return novedades
            
        except Exception as e:
            logger.error(f"Error obteniendo novedades por solicitud: {e}")
            import traceback
            traceback.print_exc()
            return []
        finally:
            cursor.close()
            conn.close()
    
    @staticmethod
    def obtener_novedades_pendientes():
        """
        Obtiene todas las novedades en estado pendiente (registrada).
        
        Returns:
            Lista de novedades pendientes
        """
        return NovedadModel.obtener_todas(filtro_estado='registrada')
    
    @staticmethod
    def obtener_tipos_disponibles():
        """
        Obtiene los tipos de novedad únicos que existen.
        
        Returns:
            Lista de tipos de novedad
        """
        conn = get_database_connection()
        if conn is None:
            return []
        
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT DISTINCT TipoNovedad 
                FROM NovedadesSolicitudes 
                WHERE TipoNovedad IS NOT NULL
                ORDER BY TipoNovedad
            """)
            
            tipos = [row[0] for row in cursor.fetchall()]
            return tipos
            
        except Exception as e:
            logger.error(f"Error obteniendo tipos de novedad: {e}")
            return []
        finally:
            cursor.close()
            conn.close()
    
    @staticmethod
    def eliminar(novedad_id):
        """
        Elimina una novedad (solo para administradores).
        
        Args:
            novedad_id: ID de la novedad a eliminar
        
        Returns:
            True si se eliminó exitosamente, False si hubo error
        """
        conn = get_database_connection()
        if conn is None:
            return False
        
        cursor = conn.cursor()
        try:
            cursor.execute("DELETE FROM NovedadesSolicitudes WHERE NovedadId = ?", (novedad_id,))
            conn.commit()
            logger.info(f"Novedad {novedad_id} eliminada")
            return cursor.rowcount > 0
            
        except Exception as e:
            conn.rollback()
            logger.error(f"Error eliminando novedad: {e}")
            return False
        finally:
            cursor.close()
            conn.close()
