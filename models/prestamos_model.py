# models/prestamos_model.py
import logging
logger = logging.getLogger(__name__)
from database import get_database_connection

class PrestamosModel:
    
    @staticmethod
    def obtener_todos():
        conn = get_database_connection()
        if not conn:
            return []
        try:
            cursor = conn.cursor()
            query = """
                SELECT 
                    pm.PrestamoId as id,
                    m.NombreElemento as material,
                    u.NombreUsuario as usuario_solicitante,
                    o.NombreOficina as oficina,
                    pm.CantidadPrestada as cantidad,
                    pm.FechaPrestamo,
                    pm.FechaDevolucionPrevista,
                    pm.FechaDevolucionReal,
                    pm.Estado,
                    pm.Evento,
                    pm.Observaciones,
                    pm.UsuarioPrestador
                FROM PrestamosMaterial pm
                INNER JOIN Materiales m ON pm.MaterialId = m.MaterialId
                INNER JOIN Usuarios u ON pm.UsuarioSolicitanteId = u.UsuarioId
                INNER JOIN Oficinas o ON pm.OficinaId = o.OficinaId
                WHERE pm.Activo = 1
                ORDER BY pm.FechaPrestamo DESC
            """
            cursor.execute(query)
            columns = [column[0] for column in cursor.description]
            prestamos = [dict(zip(columns, row)) for row in cursor.fetchall()]
            return prestamos
        except Exception as e:
            logger.info("Error obteniendo prestamos: [error](%s)", type(e).__name__)
            return []
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
    
    @staticmethod
    def crear(material_id, usuario_solicitante_id, oficina_id, cantidad_prestada,
              fecha_devolucion_prevista, evento, observaciones, usuario_prestador):
        conn = get_database_connection()
        if not conn:
            return None
        try:
            cursor = conn.cursor()
            query = """
                INSERT INTO PrestamosMaterial (
                    MaterialId, UsuarioSolicitanteId, OficinaId, CantidadPrestada,
                    FechaDevolucionPrevista, Evento, Observaciones, UsuarioPrestador,
                    Activo, FechaPrestamo, Estado
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, GETDATE(), 'PENDIENTE')
            """
            cursor.execute(query, (
                material_id, usuario_solicitante_id, oficina_id, cantidad_prestada,
                fecha_devolucion_prevista, evento, observaciones, usuario_prestador
            ))
            conn.commit()
            return cursor.lastrowid
        except Exception as e:
            logger.info("Error creando prestamo: [error](%s)", type(e).__name__)
            conn.rollback()
            return None
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
    
    @staticmethod
    def registrar_devolucion(prestamo_id, observaciones=None):
        """
        Registra la devolucion de un prestamo
        Solo puede devolver prestamos APROBADOS o APROBADO_PARCIAL
        """
        conn = get_database_connection()
        if not conn:
            return False
        try:
            cursor = conn.cursor()
            
            # Verificar estado actual
            cursor.execute("""
                SELECT Estado FROM PrestamosMaterial 
                WHERE PrestamoId = ? AND Activo = 1
            """, (prestamo_id,))
            
            row = cursor.fetchone()
            if not row:
                return False
            
            estado_actual = row[0]
            if estado_actual not in ['APROBADO', 'APROBADO_PARCIAL']:
                logger.info(f"No se puede devolver prestamo en estado: {estado_actual}")
                return False
            
            # Registrar devolucion
            query = """
                UPDATE PrestamosMaterial 
                SET Estado = 'DEVUELTO', 
                    FechaDevolucionReal = GETDATE(),
                    Observaciones = ISNULL(Observaciones, '') + ' ' + ISNULL(?, '')
                WHERE PrestamoId = ? AND Activo = 1
            """
            cursor.execute(query, (observaciones or 'Devuelto', prestamo_id))
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            logger.info("Error registrando devolucion: [error](%s)", type(e).__name__)
            conn.rollback()
            return False
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
    
    @staticmethod
    def obtener_usuarios():
        conn = get_database_connection()
        if not conn:
            return []
        try:
            cursor = conn.cursor()
            query = """
                SELECT UsuarioId as id, NombreUsuario as nombre 
                FROM Usuarios 
                WHERE Activo = 1
                ORDER BY NombreUsuario
            """
            cursor.execute(query)
            return [{'id': row[0], 'nombre': row[1]} for row in cursor.fetchall()]
        except Exception as e:
            logger.info("Error obteniendo usuarios: [error](%s)", type(e).__name__)
            return []
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    @staticmethod
    def aprobar(prestamo_id, usuario_aprobador, observaciones=None):
        """Aprueba un prestamo completamente"""
        conn = get_database_connection()
        if not conn:
            return False
        try:
            cursor = conn.cursor()
            
            # Verificar estado actual
            cursor.execute("""
                SELECT Estado FROM PrestamosMaterial 
                WHERE PrestamoId = ? AND Activo = 1
            """, (prestamo_id,))
            
            row = cursor.fetchone()
            if not row or row[0] != 'PENDIENTE':
                return False
            
            # Aprobar
            query = """
                UPDATE PrestamosMaterial 
                SET Estado = 'APROBADO',
                    UsuarioAprobador = ?,
                    FechaAprobacion = GETDATE(),
                    Observaciones = ISNULL(Observaciones, '') + ' Aprobado: ' + ISNULL(?, '')
                WHERE PrestamoId = ? AND Activo = 1
            """
            cursor.execute(query, (usuario_aprobador, observaciones or 'Aprobado', prestamo_id))
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            logger.info("Error aprobando prestamo: [error](%s)", type(e).__name__)
            if conn:
                conn.rollback()
            return False
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    @staticmethod
    def rechazar(prestamo_id, usuario_rechazador, motivo):
        """Rechaza un prestamo"""
        conn = get_database_connection()
        if not conn:
            return False
        try:
            cursor = conn.cursor()
            
            # Verificar estado actual
            cursor.execute("""
                SELECT Estado FROM PrestamosMaterial 
                WHERE PrestamoId = ? AND Activo = 1
            """, (prestamo_id,))
            
            row = cursor.fetchone()
            if not row or row[0] != 'PENDIENTE':
                return False
            
            # Rechazar
            query = """
                UPDATE PrestamosMaterial 
                SET Estado = 'RECHAZADO',
                    UsuarioRechazador = ?,
                    FechaRechazo = GETDATE(),
                    Observaciones = ISNULL(Observaciones, '') + ' Rechazado: ' + ?
                WHERE PrestamoId = ? AND Activo = 1
            """
            cursor.execute(query, (usuario_rechazador, motivo, prestamo_id))
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            logger.info("Error rechazando prestamo: [error](%s)", type(e).__name__)
            if conn:
                conn.rollback()
            return False
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    @staticmethod
    def aprobar_parcial(prestamo_id, usuario_aprobador, cantidad_aprobada, observaciones=None):
        """Aprueba un prestamo parcialmente"""
        conn = get_database_connection()
        if not conn:
            return False
        try:
            cursor = conn.cursor()
            
            # Verificar estado y cantidad
            cursor.execute("""
                SELECT Estado, CantidadPrestada FROM PrestamosMaterial 
                WHERE PrestamoId = ? AND Activo = 1
            """, (prestamo_id,))
            
            row = cursor.fetchone()
            if not row or row[0] != 'PENDIENTE':
                return False
            
            cantidad_solicitada = row[1]
            if cantidad_aprobada >= cantidad_solicitada or cantidad_aprobada <= 0:
                return False
            
            # Aprobar parcialmente
            query = """
                UPDATE PrestamosMaterial 
                SET Estado = 'APROBADO_PARCIAL',
                    CantidadPrestada = ?,
                    UsuarioAprobador = ?,
                    FechaAprobacion = GETDATE(),
                    Observaciones = ISNULL(Observaciones, '') + ' Aprobado parcial: ' + 
                                   CAST(? AS VARCHAR) + ' de ' + CAST(? AS VARCHAR) + ' unidades'
                WHERE PrestamoId = ? AND Activo = 1
            """
            cursor.execute(query, (
                cantidad_aprobada, 
                usuario_aprobador, 
                cantidad_aprobada, 
                cantidad_solicitada, 
                prestamo_id
            ))
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            logger.info("Error aprobando parcialmente prestamo: [error](%s)", type(e).__name__)
            if conn:
                conn.rollback()
            return False
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()