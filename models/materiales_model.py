import logging
logger = logging.getLogger(__name__)
from database import get_database_connection

class MaterialModel:
    @staticmethod
    def obtener_todos(oficina_id=None):
        """Obtiene todos los materiales, opcionalmente filtrados por oficina"""
        conn = get_database_connection()
        if conn is None:
            return []
        cursor = conn.cursor()
        try:
            # CONSULTA BASE MEJORADA PARA INCLUIR NOMBRE DE OFICINA
            sql = """
                SELECT 
                    m.MaterialId, 
                    m.NombreElemento, 
                    m.ValorUnitario, 
                    m.CantidadDisponible,
                    ISNULL(m.ValorTotal, 0) as ValorTotal,
                    m.OficinaCreadoraId, 
                    m.Activo, 
                    m.FechaCreacion,
                    m.UsuarioCreador, 
                    m.RutaImagen,
                    m.CantidadMinima,
                    o.NombreOficina  -- 🆕 AÑADIDO: Nombre de la oficina
                FROM Materiales m
                LEFT JOIN Oficinas o ON m.OficinaCreadoraId = o.OficinaId
                WHERE m.Activo = 1
            """
        
            # FILTRO OPCIONAL POR OFICINA
            params = ()
            if oficina_id:
                sql += " AND m.OficinaCreadoraId = ?"
                params = (oficina_id,)

            sql += " ORDER BY m.MaterialId DESC"
            cursor.execute(sql, params)

            materiales = []
            for row in cursor.fetchall():
                material = {
                    'id': row[0],
                    'nombre': row[1],
                    'valor_unitario': float(row[2]) if row[2] else 0.0,
                    'cantidad': row[3] if row[3] else 0,
                    'valor_total': float(row[4]) if row[4] else 0.0,
                    'oficina_id': row[5],
                    'activo': row[6],
                    'fecha_creacion': row[7],
                    'usuario_creador': row[8],
                    'ruta_imagen': row[9],
                    'cantidad_minima': row[10] if row[10] is not None else 0,
                    'oficina_nombre': row[11] if row[11] else f"Oficina {row[5]}"  # 🆕 Nombre de oficina
                }
                materiales.append(material)
            return materiales
        except Exception as e:
            logger.info("Error en MaterialModel.obtener_todos: [error](%s)", type(e).__name__)
            return []
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def obtener_por_id(material_id):
        conn = get_database_connection()
        if conn is None:
            return None
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT 
                    MaterialId, 
                    NombreElemento, 
                    ValorUnitario, 
                    CantidadDisponible, 
                    ISNULL(ValorTotal, 0) as ValorTotal,
                    OficinaCreadoraId, 
                    Activo, 
                    FechaCreacion,
                    UsuarioCreador, 
                    RutaImagen,
                    CantidadMinima
                FROM Materiales
                WHERE MaterialId = ? AND Activo = 1
            """, (material_id,))
            row = cursor.fetchone()
            if row:
                ruta_imagen = row[9]
                if ruta_imagen and isinstance(ruta_imagen, bytes):
                    try:
                        ruta_imagen = ruta_imagen.decode('utf-8')
                    except:
                        ruta_imagen = ""
                return {
                    'id': row[0],
                    'nombre': row[1],
                    'valor_unitario': float(row[2]) if row[2] else 0.0,
                    'cantidad': row[3] if row[3] else 0,
                    'valor_total': float(row[4]) if row[4] else 0.0,
                    'oficina_id': row[5],
                    'activo': bool(row[6]) if row[6] is not None else True,
                    'fecha_creacion': row[7],
                    'usuario_creador': row[8],
                    'ruta_imagen': ruta_imagen if ruta_imagen and ruta_imagen != 'None' else None,
                    'cantidad_minima': row[10] if row[10] is not None else 0
                }
            return None
        except Exception as e:
            logger.info("Error al obtener material por ID: [error](%s)", type(e).__name__)
            return None
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def crear(nombre, valor_unitario, cantidad, oficina_id, usuario_creador="Sistema", ruta_imagen=None, cantidad_minima=None):
        conn = get_database_connection()
        if conn is None:
            logger.info("ERROR: No hay conexion a la BD")
            return None
        cursor = conn.cursor()
        try:
            if not nombre or nombre.strip() == '':
                logger.info("Nombre vacio")
                return None
            if valor_unitario <= 0:
                logger.info("Valor unitario invalido")
                return None
            if cantidad < 0:
                logger.info("Cantidad invalida")
                return None
        
            ruta_imagen_final = str(ruta_imagen).strip() if ruta_imagen else None
        
            cursor.execute("SELECT COUNT(*) FROM Oficinas WHERE OficinaId = ?", (oficina_id,))
            oficina_exists = cursor.fetchone()[0]
            if oficina_exists == 0:
                logger.info("La oficina no existe")
                return None
        
            # Asegurar que cantidad_minima tenga un valor por defecto si es None
            if cantidad_minima is None:
                cantidad_minima = 0
                
            sql = """
                INSERT INTO Materiales (
                    NombreElemento, 
                    ValorUnitario, 
                    CantidadDisponible, 
                    OficinaCreadoraId, 
                    Activo, 
                    FechaCreacion, 
                    UsuarioCreador, 
                    RutaImagen,
                    CantidadMinima
                ) 
                VALUES (?, ?, ?, ?, 1, GETDATE(), ?, ?, ?)
            """
            params = (
                str(nombre), 
                float(valor_unitario), 
                int(cantidad), 
                int(oficina_id), 
                str(usuario_creador), 
                ruta_imagen_final,
                int(cantidad_minima)
            )
            
            cursor.execute(sql, params)
            conn.commit()
            
            cursor.execute("SELECT MAX(MaterialId) FROM Materiales")
            max_row = cursor.fetchone()
            if max_row and max_row[0] is not None:
                material_id = int(max_row[0])
                return material_id
            else:
                logger.info("No se pudo obtener el ID del material creado")
                return None
        except Exception as e:
            logger.info("ERROR CRITICO en MaterialModel.crear: [error](%s)", type(e).__name__)
            import traceback
            logger.info(traceback.format_exc())
            conn.rollback()
            return None
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def actualizar(material_id, nombre, valor_unitario, cantidad, oficina_id, ruta_imagen=None, cantidad_minima=None):
        conn = get_database_connection()
        if conn is None:
            logger.info("No se pudo establecer conexion a la base de datos")
            return False
        cursor = conn.cursor()
        try:
            if valor_unitario <= 0:
                return False
            
            # Asegurar que cantidad_minima tenga un valor por defecto si es None
            if cantidad_minima is None:
                cantidad_minima = 0
                
            if ruta_imagen is None:
                cursor.execute("""
                    UPDATE Materiales 
                    SET NombreElemento = ?, ValorUnitario = ?, CantidadDisponible = ?, 
                        OficinaCreadoraId = ?, CantidadMinima = ?
                    WHERE MaterialId = ?
                """, (nombre, valor_unitario, cantidad, oficina_id, cantidad_minima, material_id))
            else:
                cursor.execute("""
                    UPDATE Materiales 
                    SET NombreElemento = ?, ValorUnitario = ?, CantidadDisponible = ?, 
                        OficinaCreadoraId = ?, RutaImagen = ?, CantidadMinima = ?
                    WHERE MaterialId = ?
                """, (nombre, valor_unitario, cantidad, oficina_id, ruta_imagen, cantidad_minima, material_id))
                
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            logger.info("Error al actualizar material: [error](%s)", type(e).__name__)
            conn.rollback()
            return False
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def actualizar_imagen(material_id, ruta_imagen):
        """Actualiza solo la imagen de un material"""
        conn = get_database_connection()
        if conn is None:
            logger.info("No se pudo establecer conexion a la base de datos")
            return False
        cursor = conn.cursor()
        try:
            cursor.execute("""
                UPDATE Materiales 
                SET RutaImagen = ?
                WHERE MaterialId = ?
            """, (ruta_imagen, material_id))
            affected = cursor.rowcount
            conn.commit()
            return affected > 0
        except Exception as e:
            logger.info("Error al actualizar imagen: [error](%s)", type(e).__name__)
            conn.rollback()
            return False
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def eliminar(material_id):
        conn = get_database_connection()
        if conn is None:
            logger.info("No se pudo establecer conexion a la base de datos")
            return False
        cursor = conn.cursor()
        try:
            cursor.execute("UPDATE Materiales SET Activo = 0 WHERE MaterialId = ?", (material_id,))
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            logger.info("Error al eliminar material: [error](%s)", type(e).__name__)
            conn.rollback()
            return False
        finally:
            cursor.close()
            conn.close()


