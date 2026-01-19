# models/inventario_corporativo_model.py.
from database import get_database_connection


def generar_codigo_unico():
    conn = get_database_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM ProductosCorporativos")
    total = cursor.fetchone()[0] + 1
    conn.close()
    return f"QInven-{total:04d}"


class InventarioCorporativoModel:
    # ================== UTILIDADES ==================
    @staticmethod
    def generar_codigo_unico():
        """
        Proxy estÃ¡tico para generar cÃ³digos Ãºnicos desde el modelo.
        Permite usar InventarioCorporativoModel.generar_codigo_unico()
        manteniendo tambiÃ©n la funciÃ³n de mÃ³dulo.
        """
        return generar_codigo_unico()

    # ================== LISTADO / LECTURA ==================
    @staticmethod
    def obtener_todos():
        conn = get_database_connection()
        if not conn:
            return []
        cursor = None
        try:
            cursor = conn.cursor()
            query = """
                SELECT 
                    p.ProductoId           AS id,
                    p.CodigoUnico          AS codigo_unico,
                    p.NombreProducto       AS nombre,
                    p.Descripcion          AS descripcion,
                    c.NombreCategoria      AS categoria,
                    pr.NombreProveedor     AS proveedor,
                    p.ValorUnitario        AS valor_unitario,
                    p.CantidadDisponible   AS cantidad,
                    p.CantidadMinima       AS cantidad_minima,
                    p.Ubicacion            AS ubicacion,
                    p.EsAsignable          AS es_asignable,
                    p.RutaImagen           AS ruta_imagen,
                    p.FechaCreacion        AS fecha_creacion,
                    p.UsuarioCreador       AS usuario_creador
                FROM ProductosCorporativos p
                INNER JOIN CategoriasProductos c ON p.CategoriaId = c.CategoriaId
                INNER JOIN Proveedores pr        ON p.ProveedorId = pr.ProveedorId
                WHERE p.Activo = 1
                ORDER BY p.NombreProducto
            """
            cursor.execute(query)
            cols = [c[0] for c in cursor.description]
            return [dict(zip(cols, r)) for r in cursor.fetchall()]
        except Exception as e:
            print(f"Error obteniendo productos corporativos: {e}")
            return []
        finally:
            if cursor: cursor.close()
            if conn: conn.close()

    @staticmethod
    def obtener_todos_con_oficina():
        """Obtener todos los productos con informaciÃ³n de oficina asignada"""
        conn = get_database_connection()
        if not conn:
            return []
        cursor = None
        try:
            cursor = conn.cursor()
            query = """
                SELECT 
                    p.ProductoId           AS id,
                    p.CodigoUnico          AS codigo_unico,
                    p.NombreProducto       AS nombre,
                    p.Descripcion          AS descripcion,
                    c.NombreCategoria      AS categoria,
                    pr.NombreProveedor     AS proveedor,
                    p.ValorUnitario        AS valor_unitario,
                    p.CantidadDisponible   AS cantidad,
                    p.CantidadMinima       AS cantidad_minima,
                    p.Ubicacion            AS ubicacion,
                    p.EsAsignable          AS es_asignable,
                    p.RutaImagen           AS ruta_imagen,
                    p.FechaCreacion        AS fecha_creacion,
                    p.UsuarioCreador       AS usuario_creador,
                    COALESCE(o.NombreOficina, 'Sede Principal') AS oficina
                FROM ProductosCorporativos p
                INNER JOIN CategoriasProductos c ON p.CategoriaId = c.CategoriaId
                INNER JOIN Proveedores pr        ON p.ProveedorId = pr.ProveedorId
                LEFT JOIN Asignaciones a ON p.ProductoId = a.ProductoId AND a.Activo = 1
                LEFT JOIN Oficinas o ON a.OficinaId = o.OficinaId
                WHERE p.Activo = 1
                ORDER BY p.NombreProducto
            """
            cursor.execute(query)
            cols = [c[0] for c in cursor.description]
            return [dict(zip(cols, r)) for r in cursor.fetchall()]
        except Exception as e:
            print(f"Error obteniendo productos corporativos con oficina: {e}")
            return []
        finally:
            if cursor: cursor.close()
            if conn: conn.close()

    @staticmethod
    def obtener_por_oficina(oficina_id):
        """Obtiene productos corporativos filtrados por oficina"""
        conn = get_database_connection()
        if not conn:
            return []
        cursor = None
        try:
            cursor = conn.cursor()
            query = """
                SELECT DISTINCT
                    p.ProductoId           AS id,
                    p.CodigoUnico          AS codigo_unico,
                    p.NombreProducto       AS nombre,
                    p.Descripcion          AS descripcion,
                    c.NombreCategoria      AS categoria,
                    pr.NombreProveedor     AS proveedor,
                    p.ValorUnitario        AS valor_unitario,
                    p.CantidadDisponible   AS cantidad,
                    p.CantidadMinima       AS cantidad_minima,
                    p.Ubicacion            AS ubicacion,
                    p.EsAsignable          AS es_asignable,
                    p.RutaImagen           AS ruta_imagen,
                    p.FechaCreacion        AS fecha_creacion,
                    p.UsuarioCreador       AS usuario_creador
                FROM ProductosCorporativos p
                INNER JOIN CategoriasProductos c ON p.CategoriaId = c.CategoriaId
                INNER JOIN Proveedores pr        ON p.ProveedorId = pr.ProveedorId
                LEFT JOIN Asignaciones a ON p.ProductoId = a.ProductoId AND a.Activo = 1
                WHERE p.Activo = 1 AND (a.OficinaId = ? OR p.OficinaCreadoraId = ?)
                ORDER BY p.NombreProducto
            """
            cursor.execute(query, (oficina_id, oficina_id))
            cols = [c[0] for c in cursor.description]
            return [dict(zip(cols, r)) for r in cursor.fetchall()]
        except Exception as e:
            print(f"Error obteniendo productos corporativos por oficina: {e}")
            return []
        finally:
            if cursor: cursor.close()
            if conn: conn.close()

    @staticmethod
    def obtener_por_id(producto_id):
        conn = get_database_connection()
        if not conn:
            return None
        cursor = None
        try:
            cursor = conn.cursor()
            query = """
                SELECT 
                    p.ProductoId           AS id,
                    p.CodigoUnico          AS codigo_unico,
                    p.NombreProducto       AS nombre,
                    p.Descripcion          AS descripcion,
                    p.CategoriaId          AS categoria_id,
                    c.NombreCategoria      AS categoria,
                    p.ProveedorId          AS proveedor_id,
                    pr.NombreProveedor     AS proveedor,
                    p.ValorUnitario        AS valor_unitario,
                    p.CantidadDisponible   AS cantidad,
                    p.CantidadMinima       AS cantidad_minima,
                    p.Ubicacion            AS ubicacion,
                    p.EsAsignable          AS es_asignable,
                    p.RutaImagen           AS ruta_imagen,
                    p.FechaCreacion        AS fecha_creacion,
                    p.UsuarioCreador       AS usuario_creador
                FROM ProductosCorporativos p
                INNER JOIN CategoriasProductos c ON p.CategoriaId = c.CategoriaId
                INNER JOIN Proveedores pr        ON p.ProveedorId = pr.ProveedorId
                WHERE p.ProductoId = ? AND p.Activo = 1
            """
            cursor.execute(query, (producto_id,))
            row = cursor.fetchone()
            if not row:
                return None
            cols = [c[0] for c in cursor.description]
            return dict(zip(cols, row))
        except Exception as e:
            print(f"Error obteniendo producto corporativo: {e}")
            return None
        finally:
            if cursor: cursor.close()
            if conn: conn.close()

    # ================== CREAR / ACTUALIZAR / ELIMINAR ==================
    @staticmethod
    def crear(codigo_unico, nombre, descripcion, categoria_id, proveedor_id,
              valor_unitario, cantidad, cantidad_minima, ubicacion,
              es_asignable, usuario_creador, ruta_imagen):
        """
        Inserta y retorna ProductoId (SQL Server: OUTPUT INSERTED.ProductoId)
        """
        conn = get_database_connection()
        if not conn:
            return None
        cursor = None
        try:
            cursor = conn.cursor()
            sql = """
                INSERT INTO ProductosCorporativos
                    (CodigoUnico, NombreProducto, Descripcion, CategoriaId, ProveedorId,
                     ValorUnitario, CantidadDisponible, CantidadMinima, Ubicacion,
                     EsAsignable, Activo, FechaCreacion, UsuarioCreador, RutaImagen)
                OUTPUT INSERTED.ProductoId
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, GETDATE(), ?, ?)
            """
            cursor.execute(sql, (
                codigo_unico, nombre, descripcion, int(categoria_id), int(proveedor_id),
                float(valor_unitario), int(cantidad), int(cantidad_minima or 0),
                ubicacion, int(es_asignable), usuario_creador, ruta_imagen
            ))
            new_id = cursor.fetchone()[0]
            conn.commit()
            return new_id
        except Exception as e:
            print(f"Error creando producto corporativo: {e}")
            try:
                if conn: conn.rollback()
            except:
                pass
            return None
        finally:
            if cursor: cursor.close()
            if conn: conn.close()

    @staticmethod
    def actualizar(producto_id, codigo_unico, nombre, descripcion, categoria_id,
                   proveedor_id, valor_unitario, cantidad, cantidad_minima,
                   ubicacion, es_asignable, ruta_imagen=None):
        """Actualizar producto incluyendo cantidad y ruta_imagen"""
        conn = get_database_connection()
        if not conn:
            return False
        cursor = None
        try:
            cursor = conn.cursor()

            if ruta_imagen:
                sql = """
                    UPDATE ProductosCorporativos 
                    SET CodigoUnico = ?, NombreProducto = ?, Descripcion = ?, 
                        CategoriaId = ?, ProveedorId = ?, ValorUnitario = ?,
                        CantidadDisponible = ?, CantidadMinima = ?, Ubicacion = ?, 
                        EsAsignable = ?, RutaImagen = ?
                    WHERE ProductoId = ? AND Activo = 1
                """
                params = (
                    codigo_unico, nombre, descripcion, int(categoria_id), int(proveedor_id),
                    float(valor_unitario), int(cantidad), int(cantidad_minima or 0),
                    ubicacion, int(es_asignable), ruta_imagen, int(producto_id)
                )
            else:
                sql = """
                    UPDATE ProductosCorporativos 
                    SET CodigoUnico = ?, NombreProducto = ?, Descripcion = ?, 
                        CategoriaId = ?, ProveedorId = ?, ValorUnitario = ?,
                        CantidadDisponible = ?, CantidadMinima = ?, Ubicacion = ?, 
                        EsAsignable = ?
                    WHERE ProductoId = ? AND Activo = 1
                """
                params = (
                    codigo_unico, nombre, descripcion, int(categoria_id), int(proveedor_id),
                    float(valor_unitario), int(cantidad), int(cantidad_minima or 0),
                    ubicacion, int(es_asignable), int(producto_id)
                )

            cursor.execute(sql, params)
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            print(f"Error actualizando producto corporativo: {e}")
            try:
                if conn: conn.rollback()
            except:
                pass
            return False
        finally:
            if cursor: cursor.close()
            if conn: conn.close()

    @staticmethod
    def eliminar(producto_id, usuario_accion):
        """Soft delete (Activo = 0) + deja traza minima en historial."""
        conn = get_database_connection()
        if not conn:
            return False
        cursor = None
        try:
            cursor = conn.cursor()
            # Traza en nueva tabla
            cursor.execute("""
                INSERT INTO AsignacionesCorporativasHistorial
                    (ProductoId, Accion, Cantidad, OficinaId, UsuarioAccion, Fecha)
                VALUES (?, 'BAJA_PRODUCTO', 0, NULL, ?, GETDATE())
            """, (int(producto_id), usuario_accion))
            # Baja logica
            cursor.execute(
                "UPDATE ProductosCorporativos SET Activo = 0 WHERE ProductoId = ?",
                (int(producto_id),)
            )
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            print(f"Error eliminando producto corporativo: {e}")
            try:
                if conn: conn.rollback()
            except:
                pass
            return False
        finally:
            if cursor: cursor.close()
            if conn: conn.close()

    # ================== CATALOGOS ==================
    @staticmethod
    def obtener_categorias():
        """
        Retorna todas las categorÃ­as activas desde la tabla CategoriasProductos,
        incluso si todavÃ­a no tienen productos asociados.
        """
        conn = get_database_connection()
        if not conn:
            return []
        cursor = None
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    c.CategoriaId AS id,
                    c.NombreCategoria AS nombre
                FROM CategoriasProductos c
                WHERE c.Activo = 1
                ORDER BY c.NombreCategoria
            """)
            return [{'id': r[0], 'nombre': r[1]} for r in cursor.fetchall()]
        except Exception as e:
            print(f"âŒ Error obteniendo categorÃ­as activas: {e}")
            return []
        finally:
            if cursor: cursor.close()
            if conn: conn.close()

    @staticmethod
    def obtener_proveedores():
        conn = get_database_connection()
        if not conn:
            return []
        cursor = None
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT p.ProveedorId AS id, p.NombreProveedor AS nombre
                FROM Proveedores p
                WHERE p.Activo = 1
                ORDER BY p.NombreProveedor
            """)
            return [{'id': r[0], 'nombre': r[1]} for r in cursor.fetchall()]
        except Exception as e:
            print(f"Error obtener_proveedores: {e}")
            return []
        finally:
            if cursor: cursor.close()
            if conn: conn.close()

    @staticmethod
    def obtener_oficinas():
        """
        Oficinas para asignacion.
        """
        conn = get_database_connection()
        if not conn:
            return []
        cursor = None
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT o.OficinaId AS id, o.NombreOficina AS nombre
                FROM Oficinas o
                WHERE o.Activo = 1
                ORDER BY o.NombreOficina
            """)
            return [{'id': r[0], 'nombre': r[1]} for r in cursor.fetchall()]
        except Exception as e:
            print(f"Error obtener_oficinas: {e}")
            return []
        finally:
            if cursor: cursor.close()
            if conn: conn.close()

    # ================== ASIGNACIONES / TRAZABILIDAD ==================
    @staticmethod
    def asignar_a_oficina(producto_id, oficina_id, cantidad, usuario_accion):
        """
        Resta stock de ProductosCorporativos.CantidadDisponible y crea registro
        en Asignaciones + guarda traza en AsignacionesCorporativasHistorial.
        """
        conn = get_database_connection()
        if not conn:
            return False
        cursor = None
        try:
            cursor = conn.cursor()

            # 1. PRIMERO: Obtener un UsuarioId vÃ¡lido
            cursor.execute(
                "SELECT TOP 1 UsuarioId FROM Usuarios WHERE Activo = 1 ORDER BY UsuarioId"
            )
            usuario_row = cursor.fetchone()
            if not usuario_row:
                print("Error: No hay usuarios activos en la base de datos")
                return False
            usuario_asignado_id = usuario_row[0]

            # 2. Verificar stock
            cursor.execute(
                "SELECT CantidadDisponible FROM ProductosCorporativos "
                "WHERE ProductoId = ? AND Activo = 1",
                (int(producto_id),)
            )
            row = cursor.fetchone()
            if not row:
                return False
            stock = int(row[0])
            cant = int(cantidad)

            # âœ… CORRECCIÃ“N: condiciÃ³n correcta
            if cant <= 0 or cant > stock:
                return False

            # 3. Descontar stock
            cursor.execute("""
                UPDATE ProductosCorporativos
                SET CantidadDisponible = CantidadDisponible - ?
                WHERE ProductoId = ?
            """, (cant, int(producto_id)))

            # 4. Crear registro en tabla Asignaciones (CON USUARIO VÃLIDO)
            cursor.execute("""
                INSERT INTO Asignaciones 
                (ProductoId, OficinaId, UsuarioAsignadoId, FechaAsignacion, Estado, UsuarioAsignador, Activo)
                VALUES (?, ?, ?, GETDATE(), 'ASIGNADO', ?, 1)
            """, (int(producto_id), int(oficina_id), usuario_asignado_id, usuario_accion))

            # 5. Trazabilidad en tabla AsignacionesCorporativasHistorial
            cursor.execute("""
                INSERT INTO AsignacionesCorporativasHistorial
                    (ProductoId, OficinaId, Accion, Cantidad, UsuarioAccion, Fecha)
                VALUES (?, ?, 'ASIGNAR', ?, ?, GETDATE())
            """, (int(producto_id), int(oficina_id), cant, usuario_accion))

            conn.commit()
            return True
        except Exception as e:
            print(f"Error asignar_a_oficina: {e}")
            try:
                if conn: conn.rollback()
            except:
                pass
            return False
        finally:
            if cursor: cursor.close()
            if conn: conn.close()

    @staticmethod
    def historial_asignaciones(producto_id):
        """Obtener historial de asignaciones para un producto especÃ­fico"""
        conn = get_database_connection()
        if not conn:
            return []
        cursor = None
        try:
            cursor = conn.cursor()
            # âœ… CORRECCIÃ“N: Agregados los campos UsuarioAsignadoNombre y UsuarioAsignadoEmail
            cursor.execute("""
                SELECT 
                    h.HistorialId,
                    h.ProductoId,
                    h.OficinaId,
                    o.NombreOficina AS oficina,
                    h.Accion,
                    h.Cantidad,
                    h.UsuarioAccion,
                    h.Fecha,
                    h.UsuarioAsignadoNombre,
                    h.UsuarioAsignadoEmail
                FROM AsignacionesCorporativasHistorial h
                LEFT JOIN Oficinas o ON o.OficinaId = h.OficinaId
                WHERE h.ProductoId = ?
                ORDER BY h.Fecha DESC
            """, (int(producto_id),))
            cols = [c[0] for c in cursor.description]
            return [dict(zip(cols, r)) for r in cursor.fetchall()]
        except Exception as e:
            print(f"Error historial_asignaciones: {e}")
            return []
        finally:
            if cursor: cursor.close()
            if conn: conn.close()

    # ================== REPORTES ==================
    @staticmethod
    def reporte_stock_por_categoria():
        conn = get_database_connection()
        if not conn:
            return []
        cursor = None
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    c.NombreCategoria AS categoria,
                    SUM(p.CantidadDisponible) AS total_stock
                FROM ProductosCorporativos p
                INNER JOIN CategoriasProductos c ON p.CategoriaId = c.CategoriaId
                WHERE p.Activo = 1
                GROUP BY c.NombreCategoria
                ORDER BY c.NombreCategoria
            """)
            return [
                {'categoria': r[0], 'total_stock': int(r[1] or 0)}
                for r in cursor.fetchall()
            ]
        except Exception as e:
            print(f"Error reporte_stock_por_categoria: {e}")
            return []
        finally:
            if cursor: cursor.close()
            if conn: conn.close()

    @staticmethod
    def reporte_valor_inventario():
        conn = get_database_connection()
        if not conn:
            return {'valor_total': 0}
        cursor = None
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT SUM(p.ValorUnitario * p.CantidadDisponible) AS valor_total
                FROM ProductosCorporativos p
                WHERE p.Activo = 1
            """)
            row = cursor.fetchone()
            return {'valor_total': float(row[0] or 0.0)}
        except Exception as e:
            print(f"Error reporte_valor_inventario: {e}")
            return {'valor_total': 0}
        finally:
            if cursor: cursor.close()
            if conn: conn.close()

    @staticmethod
    def reporte_asignaciones_por_oficina():
        conn = get_database_connection()
        if not conn:
            return []
        cursor = None
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    o.NombreOficina AS oficina,
                    COUNT(a.AsignacionId) AS cantidad_asignaciones
                FROM Asignaciones a
                INNER JOIN Oficinas o ON o.OficinaId = a.OficinaId
                WHERE a.Activo = 1
                GROUP BY o.NombreOficina
                ORDER BY o.NombreOficina
            """)
            return [
                {
                    'oficina': r[0],
                    'cantidad_asignaciones': int(r[1] or 0)
                }
                for r in cursor.fetchall()
            ]
        except Exception as e:
            print(f"Error reporte_asignaciones_por_oficina: {e}")
            return []
        finally:
            if cursor: cursor.close()
            if conn: conn.close()

    # ================== REPORTES AVANZADOS ==================
    @staticmethod
    def reporte_productos_por_oficina():
        """Reporte de productos agrupados por oficina"""
        conn = get_database_connection()
        if not conn:
            return []
        cursor = None
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    COALESCE(o.NombreOficina, 'Sede Principal') AS oficina,
                    COUNT(p.ProductoId) AS total_productos,
                    SUM(p.CantidadDisponible) AS total_stock,
                    SUM(p.ValorUnitario * p.CantidadDisponible) AS valor_total
                FROM ProductosCorporativos p
                LEFT JOIN Asignaciones a ON p.ProductoId = a.ProductoId AND a.Activo = 1
                LEFT JOIN Oficinas o ON a.OficinaId = o.OficinaId
                WHERE p.Activo = 1
                GROUP BY COALESCE(o.NombreOficina, 'Sede Principal')
                ORDER BY valor_total DESC
            """)
            cols = [c[0] for c in cursor.description]
            return [dict(zip(cols, r)) for r in cursor.fetchall()]
        except Exception as e:
            print(f"Error reporte_productos_por_oficina: {e}")
            return []
        finally:
            if cursor: cursor.close()
            if conn: conn.close()

    @staticmethod
    def reporte_stock_bajo():
        """Productos con stock bajo o crÃ­tico"""
        conn = get_database_connection()
        if not conn:
            return []
        cursor = None
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    p.ProductoId,
                    p.CodigoUnico,
                    p.NombreProducto,
                    c.NombreCategoria AS categoria,
                    p.CantidadDisponible,
                    p.CantidadMinima,
                    p.ValorUnitario,
                    (p.ValorUnitario * p.CantidadDisponible) AS valor_total,
                    CASE 
                        WHEN p.CantidadDisponible = 0 THEN 'CrÃ­tico'
                        WHEN p.CantidadDisponible <= p.CantidadMinima THEN 'Bajo'
                        ELSE 'Normal'
                    END AS estado_stock
                FROM ProductosCorporativos p
                INNER JOIN CategoriasProductos c ON p.CategoriaId = c.CategoriaId
                WHERE p.Activo = 1 
                AND (p.CantidadDisponible = 0 OR p.CantidadDisponible <= p.CantidadMinima)
                ORDER BY p.CantidadDisponible ASC
            """)
            cols = [c[0] for c in cursor.description]
            return [dict(zip(cols, r)) for r in cursor.fetchall()]
        except Exception as e:
            print(f"Error reporte_stock_bajo: {e}")
            return []
        finally:
            if cursor: cursor.close()
            if conn: conn.close()

    @staticmethod
    def reporte_movimientos_recientes(limite=50):
        """Movimientos recientes del inventario"""
        conn = get_database_connection()
        if not conn:
            return []
        cursor = None
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT TOP (?) 
                    h.HistorialId,
                    p.NombreProducto,
                    o.NombreOficina AS oficina,
                    h.Accion,
                    h.Cantidad,
                    h.UsuarioAccion,
                    h.Fecha
                FROM AsignacionesCorporativasHistorial h
                INNER JOIN ProductosCorporativos p ON h.ProductoId = p.ProductoId
                LEFT JOIN Oficinas o ON h.OficinaId = o.OficinaId
                ORDER BY h.Fecha DESC
            """, (limite,))
            cols = [c[0] for c in cursor.description]
            return [dict(zip(cols, r)) for r in cursor.fetchall()]
        except Exception as e:
            print(f"Error reporte_movimientos_recientes: {e}")
            return []
        finally:
            if cursor: cursor.close()
            if conn: conn.close()

    @staticmethod
    def obtener_estadisticas_generales():
        """EstadÃ­sticas generales del inventario"""
        conn = get_database_connection()
        if not conn:
            return {}
        cursor = None
        try:
            cursor = conn.cursor()

            # Total productos
            cursor.execute(
                "SELECT COUNT(*) FROM ProductosCorporativos WHERE Activo = 1"
            )
            total_productos = cursor.fetchone()[0]

            # Valor total inventario
            cursor.execute("""
                SELECT SUM(ValorUnitario * CantidadDisponible)
                FROM ProductosCorporativos
                WHERE Activo = 1
            """)
            valor_total = cursor.fetchone()[0] or 0

            # Productos con stock bajo
            cursor.execute("""
                SELECT COUNT(*) 
                FROM ProductosCorporativos 
                WHERE Activo = 1 
                AND (CantidadDisponible = 0 OR CantidadDisponible <= CantidadMinima)
            """)
            stock_bajo = cursor.fetchone()[0]

            # Productos asignables
            cursor.execute("""
                SELECT COUNT(*)
                FROM ProductosCorporativos
                WHERE Activo = 1 AND EsAsignable = 1
            """)
            asignables = cursor.fetchone()[0]

            # Total categorÃ­as
            cursor.execute("""
                SELECT COUNT(DISTINCT CategoriaId)
                FROM ProductosCorporativos
                WHERE Activo = 1
            """)
            total_categorias = cursor.fetchone()[0]

            return {
                'total_productos': total_productos,
                'valor_total': float(valor_total),
                'stock_bajo': stock_bajo,
                'asignables': asignables,
                'total_categorias': total_categorias
            }
        except Exception as e:
            print(f"Error obtener_estadisticas_generales: {e}")
            return {}
        finally:
            if cursor: cursor.close()
            if conn: conn.close()

    # ================== VISTAS POR TIPO DE OFICINA ==================

    @staticmethod
    def obtener_por_sede_principal():
        """Obtiene productos de la sede principal (no asignados a oficinas)"""
        conn = get_database_connection()
        if not conn:
            return []
        cursor = None
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    p.ProductoId           AS id,
                    p.CodigoUnico          AS codigo_unico,
                    p.NombreProducto       AS nombre,
                    p.Descripcion          AS descripcion,
                    c.NombreCategoria      AS categoria,
                    pr.NombreProveedor     AS proveedor,
                    p.ValorUnitario        AS valor_unitario,
                    p.CantidadDisponible   AS cantidad,
                    p.CantidadMinima       AS cantidad_minima,
                    p.Ubicacion            AS ubicacion,
                    p.EsAsignable          AS es_asignable,
                    p.RutaImagen           AS ruta_imagen,
                    p.FechaCreacion        AS fecha_creacion,
                    p.UsuarioCreador       AS usuario_creador,
                    'Sede Principal'       AS oficina
                FROM ProductosCorporativos p
                INNER JOIN CategoriasProductos c ON p.CategoriaId = c.CategoriaId
                INNER JOIN Proveedores pr        ON p.ProveedorId = pr.ProveedorId
                WHERE p.Activo = 1
                AND NOT EXISTS (
                    SELECT 1 FROM Asignaciones a 
                    WHERE a.ProductoId = p.ProductoId AND a.Activo = 1
                )
                ORDER BY p.NombreProducto
            """)
            cols = [c[0] for c in cursor.description]
            return [dict(zip(cols, r)) for r in cursor.fetchall()]
        except Exception as e:
            print(f"Error obteniendo sede principal: {e}")
            return []
        finally:
            if cursor: cursor.close()
            if conn: conn.close()

    @staticmethod
    def obtener_por_oficinas_servicio():
        """Obtiene productos de oficinas de servicio (asignados a oficinas)"""
        conn = get_database_connection()
        if not conn:
            return []
        cursor = None
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT DISTINCT
                    p.ProductoId           AS id,
                    p.CodigoUnico          AS codigo_unico,
                    p.NombreProducto       AS nombre,
                    p.Descripcion          AS descripcion,
                    c.NombreCategoria      AS categoria,
                    pr.NombreProveedor     AS proveedor,
                    p.ValorUnitario        AS valor_unitario,
                    p.CantidadDisponible   AS cantidad,
                    p.CantidadMinima       AS cantidad_minima,
                    p.Ubicacion            AS ubicacion,
                    p.EsAsignable          AS es_asignable,
                    p.RutaImagen           AS ruta_imagen,
                    p.FechaCreacion        AS fecha_creacion,
                    p.UsuarioCreador       AS usuario_creador,
                    o.NombreOficina        AS oficina
                FROM ProductosCorporativos p
                INNER JOIN CategoriasProductos c ON p.CategoriaId = c.CategoriaId
                INNER JOIN Proveedores pr        ON p.ProveedorId = pr.ProveedorId
                INNER JOIN Asignaciones a        ON p.ProductoId = a.ProductoId AND a.Activo = 1
                INNER JOIN Oficinas o            ON a.OficinaId = o.OficinaId
                WHERE p.Activo = 1
                ORDER BY o.NombreOficina, p.NombreProducto
            """)
            cols = [c[0] for c in cursor.description]
            return [dict(zip(cols, r)) for r in cursor.fetchall()]
        except Exception as e:
            print(f"Error obteniendo oficinas servicio: {e}")
            return []
        finally:
            if cursor: cursor.close()
            if conn: conn.close()