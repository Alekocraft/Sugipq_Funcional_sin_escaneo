import logging
logger = logging.getLogger(__name__)
from database import get_database_connection

class OficinaModel:
    # ---------- Helper interno ----------
    @staticmethod
    def _row_a_dict(row):
        # row: (OficinaId, NombreOficina, DirectorOficina, Ubicacion, EsPrincipal, Activo, FechaCreacion, Email)
        return {
            'id': row[0],
            'nombre': row[1],
            'director': row[2] or 'No asignado',
            'ubicacion': row[3] or 'No especificada',
            'es_principal': bool(row[4]) if row[4] is not None else False,
            'activo': bool(row[5]) if row[5] is not None else True,
            'fecha_creacion': row[6],
            'email': row[7] or ''
        }

    # ---------- Métodos existentes con normalización consistente ----------
    @staticmethod
    def obtener_todas():
        conn = get_database_connection()
        if conn is None:
            logger.info("❌ No se pudo establecer conexión a la base de datos")
            return []
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT OficinaId, NombreOficina, DirectorOficina, Ubicacion, 
                       EsPrincipal, Activo, FechaCreacion, Email
                FROM Oficinas
                ORDER BY NombreOficina
            """)
            return [OficinaModel._row_a_dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.info("❌ Error al obtener oficinas: [error](%s)", type(e).__name__)
            return []
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def obtener_por_id(oficina_id):
        conn = get_database_connection()
        if conn is None:
            logger.info("❌ No se pudo establecer conexión a la base de datos")
            return None
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT OficinaId, NombreOficina, DirectorOficina, Ubicacion, 
                       EsPrincipal, Activo, FechaCreacion, Email
                FROM Oficinas
                WHERE OficinaId = ?
            """, (oficina_id,))
            row = cursor.fetchone()
            return OficinaModel._row_a_dict(row) if row else None
        except Exception as e:
            logger.info("❌ Error al obtener oficina por ID: [error](%s)", type(e).__name__)
            return None
        finally:
            cursor.close()
            conn.close()

    # ---------- Compatibilidad: SOLO ID (como antes) ----------
    @staticmethod
    def obtener_id_por_nombre(nombre, incluir_inactivas=False):
        """
        Mantiene el contrato anterior: devuelve {'id': ...} o None.
        Por defecto no incluye inactivas (comportamiento seguro).
        """
        conn = get_database_connection()
        if conn is None:
            logger.info("❌ No se pudo establecer conexión a la base de datos")
            return None
        cursor = conn.cursor()
        try:
            sql = "SELECT OficinaId FROM Oficinas WHERE NombreOficina = ?"
            params = [nombre]
            if not incluir_inactivas:
                sql += " AND Activo = 1"
            cursor.execute(sql, tuple(params))
            row = cursor.fetchone()
            return {'id': row[0]} if row else None
        except Exception as e:
            logger.info("❌ Error al obtener id por nombre: [error](%s)", type(e).__name__)
            return None
        finally:
            cursor.close()
            conn.close()

    # ---------- Versión detallada (nuevo contrato) ----------
    @staticmethod
    def obtener_por_nombre(nombre, incluir_inactivas=False):
        """
        Devuelve dict completo normalizado o None.
        """
        conn = get_database_connection()
        if conn is None:
            logger.info("❌ No se pudo establecer conexión a la base de datos")
            return None
        cursor = conn.cursor()
        try:
            sql = """
                SELECT OficinaId, NombreOficina, DirectorOficina, Ubicacion, 
                       EsPrincipal, Activo, FechaCreacion, Email
                FROM Oficinas 
                WHERE NombreOficina = ?
            """
            params = [nombre]
            if not incluir_inactivas:
                sql += " AND Activo = 1"
            cursor.execute(sql, tuple(params))
            row = cursor.fetchone()
            return OficinaModel._row_a_dict(row) if row else None
        except Exception as e:
            logger.info("❌ Error obteniendo oficina por nombre: [error](%s)", type(e).__name__)
            return None
        finally:
            cursor.close()
            conn.close()

    # ---------- Oficina principal ----------
    @staticmethod
    def obtener_oficina_principal(incluir_inactivas=False):
        """
        Devuelve la oficina principal. Por defecto requiere activa.
        """
        conn = get_database_connection()
        if conn is None:
            logger.info("❌ No se pudo establecer conexión a la base de datos")
            return None
        cursor = conn.cursor()
        try:
            sql = """
                SELECT OficinaId, NombreOficina, DirectorOficina, Ubicacion, 
                       EsPrincipal, Activo, FechaCreacion, Email
                FROM Oficinas 
                WHERE EsPrincipal = 1
            """
            if not incluir_inactivas:
                sql += " AND Activo = 1"
            cursor.execute(sql)
            row = cursor.fetchone()
            return OficinaModel._row_a_dict(row) if row else None
        except Exception as e:
            logger.info("❌ Error obteniendo oficina principal: [error](%s)", type(e).__name__)
            return None
        finally:
            cursor.close()
            conn.close()