-- ============================================================================
-- SCRIPT SQL PARA AGREGAR SOPORTE DE USUARIOS AD EN ASIGNACIONES
-- Sistema de Inventario Corporativo - Qualitas Colombia
-- Ejecutar este script en SQL Server Management Studio
-- ============================================================================

-- ============================================================================
-- 1. AGREGAR COLUMNAS A TABLA Asignaciones
-- ============================================================================

-- Columna para almacenar el nombre del usuario AD
IF NOT EXISTS (
    SELECT * FROM sys.columns 
    WHERE object_id = OBJECT_ID('Asignaciones') 
    AND name = 'UsuarioADNombre'
)
BEGIN
    ALTER TABLE Asignaciones 
    ADD UsuarioADNombre NVARCHAR(255) NULL;
    PRINT 'Columna UsuarioADNombre agregada a Asignaciones';
END
ELSE
BEGIN
    PRINT 'Columna UsuarioADNombre ya existe en Asignaciones';
END
GO

-- Columna para almacenar el email del usuario AD
IF NOT EXISTS (
    SELECT * FROM sys.columns 
    WHERE object_id = OBJECT_ID('Asignaciones') 
    AND name = 'UsuarioADEmail'
)
BEGIN
    ALTER TABLE Asignaciones 
    ADD UsuarioADEmail NVARCHAR(255) NULL;
    PRINT 'Columna UsuarioADEmail agregada a Asignaciones';
END
ELSE
BEGIN
    PRINT 'Columna UsuarioADEmail ya existe en Asignaciones';
END
GO

-- ============================================================================
-- 2. AGREGAR COLUMNAS A TABLA AsignacionesCorporativasHistorial
-- ============================================================================

-- Columna para almacenar el nombre del usuario asignado en el historial
IF NOT EXISTS (
    SELECT * FROM sys.columns 
    WHERE object_id = OBJECT_ID('AsignacionesCorporativasHistorial') 
    AND name = 'UsuarioAsignadoNombre'
)
BEGIN
    ALTER TABLE AsignacionesCorporativasHistorial 
    ADD UsuarioAsignadoNombre NVARCHAR(255) NULL;
    PRINT 'Columna UsuarioAsignadoNombre agregada a AsignacionesCorporativasHistorial';
END
ELSE
BEGIN
    PRINT 'Columna UsuarioAsignadoNombre ya existe en AsignacionesCorporativasHistorial';
END
GO

-- Columna para almacenar el email del usuario asignado en el historial
IF NOT EXISTS (
    SELECT * FROM sys.columns 
    WHERE object_id = OBJECT_ID('AsignacionesCorporativasHistorial') 
    AND name = 'UsuarioAsignadoEmail'
)
BEGIN
    ALTER TABLE AsignacionesCorporativasHistorial 
    ADD UsuarioAsignadoEmail NVARCHAR(255) NULL;
    PRINT 'Columna UsuarioAsignadoEmail agregada a AsignacionesCorporativasHistorial';
END
ELSE
BEGIN
    PRINT 'Columna UsuarioAsignadoEmail ya existe en AsignacionesCorporativasHistorial';
END
GO

-- ============================================================================
-- 3. AGREGAR COLUMNA UsuarioAD A TABLA Usuarios (SI NO EXISTE)
-- ============================================================================

IF NOT EXISTS (
    SELECT * FROM sys.columns 
    WHERE object_id = OBJECT_ID('Usuarios') 
    AND name = 'UsuarioAD'
)
BEGIN
    ALTER TABLE Usuarios 
    ADD UsuarioAD NVARCHAR(100) NULL;
    PRINT 'Columna UsuarioAD agregada a Usuarios';
END
ELSE
BEGIN
    PRINT 'Columna UsuarioAD ya existe en Usuarios';
END
GO

-- ============================================================================
-- 4. CREAR ÍNDICES PARA MEJOR RENDIMIENTO
-- ============================================================================

-- Índice en UsuarioAD de tabla Usuarios
IF NOT EXISTS (
    SELECT * FROM sys.indexes 
    WHERE name = 'IX_Usuarios_UsuarioAD' 
    AND object_id = OBJECT_ID('Usuarios')
)
BEGIN
    CREATE NONCLUSTERED INDEX IX_Usuarios_UsuarioAD 
    ON Usuarios(UsuarioAD);
    PRINT 'Índice IX_Usuarios_UsuarioAD creado';
END
GO

-- Índice en UsuarioADNombre de tabla Asignaciones
IF NOT EXISTS (
    SELECT * FROM sys.indexes 
    WHERE name = 'IX_Asignaciones_UsuarioADNombre' 
    AND object_id = OBJECT_ID('Asignaciones')
)
BEGIN
    CREATE NONCLUSTERED INDEX IX_Asignaciones_UsuarioADNombre 
    ON Asignaciones(UsuarioADNombre);
    PRINT 'Índice IX_Asignaciones_UsuarioADNombre creado';
END
GO

-- ============================================================================
-- 5. VISTA PARA CONSULTAR ASIGNACIONES CON INFORMACIÓN DE USUARIO AD
-- ============================================================================

IF EXISTS (SELECT * FROM sys.views WHERE name = 'vw_AsignacionesConUsuarioAD')
BEGIN
    DROP VIEW vw_AsignacionesConUsuarioAD;
END
GO

CREATE VIEW vw_AsignacionesConUsuarioAD AS
SELECT 
    a.AsignacionId,
    a.ProductoId,
    p.CodigoUnico AS ProductoCodigo,
    p.NombreProducto,
    c.NombreCategoria AS Categoria,
    a.OficinaId,
    o.NombreOficina,
    a.UsuarioAsignadoId,
    u.NombreCompleto AS UsuarioSistemaNombre,
    a.UsuarioADNombre,
    a.UsuarioADEmail,
    COALESCE(a.UsuarioADNombre, u.NombreCompleto, 'N/A') AS NombreAsignadoFinal,
    COALESCE(a.UsuarioADEmail, u.Email, '') AS EmailAsignadoFinal,
    a.FechaAsignacion,
    a.Estado,
    a.UsuarioAsignador,
    a.Activo
FROM Asignaciones a
INNER JOIN ProductosCorporativos p ON a.ProductoId = p.ProductoId
INNER JOIN CategoriasProductos c ON p.CategoriaId = c.CategoriaId
INNER JOIN Oficinas o ON a.OficinaId = o.OficinaId
LEFT JOIN Usuarios u ON a.UsuarioAsignadoId = u.UsuarioId
WHERE a.Activo = 1;
GO

PRINT 'Vista vw_AsignacionesConUsuarioAD creada';
GO

-- ============================================================================
-- 6. PROCEDIMIENTO ALMACENADO PARA BUSCAR ASIGNACIONES POR USUARIO
-- ============================================================================

IF EXISTS (SELECT * FROM sys.procedures WHERE name = 'sp_BuscarAsignacionesPorUsuarioAD')
BEGIN
    DROP PROCEDURE sp_BuscarAsignacionesPorUsuarioAD;
END
GO

CREATE PROCEDURE sp_BuscarAsignacionesPorUsuarioAD
    @NombreUsuario NVARCHAR(255)
AS
BEGIN
    SET NOCOUNT ON;
    
    SELECT 
        a.AsignacionId,
        p.CodigoUnico,
        p.NombreProducto,
        c.NombreCategoria AS Categoria,
        o.NombreOficina,
        a.UsuarioADNombre,
        a.UsuarioADEmail,
        a.FechaAsignacion,
        a.Estado,
        a.UsuarioAsignador
    FROM Asignaciones a
    INNER JOIN ProductosCorporativos p ON a.ProductoId = p.ProductoId
    INNER JOIN CategoriasProductos c ON p.CategoriaId = c.CategoriaId
    INNER JOIN Oficinas o ON a.OficinaId = o.OficinaId
    WHERE a.Activo = 1
    AND (
        a.UsuarioADNombre LIKE '%' + @NombreUsuario + '%'
        OR a.UsuarioADEmail LIKE '%' + @NombreUsuario + '%'
    )
    ORDER BY a.FechaAsignacion DESC;
END
GO

PRINT 'Procedimiento sp_BuscarAsignacionesPorUsuarioAD creado';
GO

-- ============================================================================
-- 7. PROCEDIMIENTO PARA REPORTE DE ASIGNACIONES POR USUARIO
-- ============================================================================

IF EXISTS (SELECT * FROM sys.procedures WHERE name = 'sp_ReporteAsignacionesPorUsuario')
BEGIN
    DROP PROCEDURE sp_ReporteAsignacionesPorUsuario;
END
GO

CREATE PROCEDURE sp_ReporteAsignacionesPorUsuario
    @FechaInicio DATE = NULL,
    @FechaFin DATE = NULL
AS
BEGIN
    SET NOCOUNT ON;
    
    -- Si no se especifican fechas, usar los últimos 30 días
    IF @FechaInicio IS NULL SET @FechaInicio = DATEADD(DAY, -30, GETDATE());
    IF @FechaFin IS NULL SET @FechaFin = GETDATE();
    
    SELECT 
        COALESCE(a.UsuarioADNombre, u.NombreCompleto, 'Sin asignar') AS UsuarioAsignado,
        COALESCE(a.UsuarioADEmail, u.Email, '') AS EmailUsuario,
        COUNT(DISTINCT a.AsignacionId) AS TotalAsignaciones,
        COUNT(DISTINCT a.ProductoId) AS ProductosDistintos,
        COUNT(DISTINCT a.OficinaId) AS OficinasDistintas
    FROM Asignaciones a
    LEFT JOIN Usuarios u ON a.UsuarioAsignadoId = u.UsuarioId
    WHERE a.Activo = 1
    AND a.FechaAsignacion BETWEEN @FechaInicio AND @FechaFin
    GROUP BY 
        COALESCE(a.UsuarioADNombre, u.NombreCompleto, 'Sin asignar'),
        COALESCE(a.UsuarioADEmail, u.Email, '')
    ORDER BY TotalAsignaciones DESC;
END
GO

PRINT 'Procedimiento sp_ReporteAsignacionesPorUsuario creado';
GO

-- ============================================================================
-- 8. TABLA DE LOG DE NOTIFICACIONES (OPCIONAL)
-- ============================================================================

IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'NotificacionesAsignacionLog')
BEGIN
    CREATE TABLE NotificacionesAsignacionLog (
        LogId INT IDENTITY(1,1) PRIMARY KEY,
        AsignacionId INT NULL,
        ProductoId INT NOT NULL,
        DestinatarioEmail NVARCHAR(255) NOT NULL,
        DestinatarioNombre NVARCHAR(255) NULL,
        FechaEnvio DATETIME DEFAULT GETDATE(),
        Estado NVARCHAR(50) DEFAULT 'ENVIADO', -- ENVIADO, FALLIDO, PENDIENTE
        MensajeError NVARCHAR(MAX) NULL,
        UsuarioEnviador NVARCHAR(100) NULL
    );
    
    PRINT 'Tabla NotificacionesAsignacionLog creada';
    
    -- Índices
    CREATE NONCLUSTERED INDEX IX_NotificacionesLog_Fecha 
    ON NotificacionesAsignacionLog(FechaEnvio);
    
    CREATE NONCLUSTERED INDEX IX_NotificacionesLog_Destinatario 
    ON NotificacionesAsignacionLog(DestinatarioEmail);
END
ELSE
BEGIN
    PRINT 'Tabla NotificacionesAsignacionLog ya existe';
END
GO

-- ============================================================================
-- 9. VERIFICACIÓN FINAL
-- ============================================================================

PRINT '';
PRINT '============================================';
PRINT 'VERIFICACIÓN DE CAMBIOS APLICADOS';
PRINT '============================================';

-- Verificar columnas en Asignaciones
SELECT 
    'Asignaciones' AS Tabla,
    COLUMN_NAME AS Columna,
    DATA_TYPE AS TipoDato,
    CHARACTER_MAXIMUM_LENGTH AS Longitud
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_NAME = 'Asignaciones'
AND COLUMN_NAME IN ('UsuarioADNombre', 'UsuarioADEmail');

-- Verificar columnas en AsignacionesCorporativasHistorial
SELECT 
    'AsignacionesCorporativasHistorial' AS Tabla,
    COLUMN_NAME AS Columna,
    DATA_TYPE AS TipoDato,
    CHARACTER_MAXIMUM_LENGTH AS Longitud
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_NAME = 'AsignacionesCorporativasHistorial'
AND COLUMN_NAME IN ('UsuarioAsignadoNombre', 'UsuarioAsignadoEmail');

-- Verificar columna en Usuarios
SELECT 
    'Usuarios' AS Tabla,
    COLUMN_NAME AS Columna,
    DATA_TYPE AS TipoDato,
    CHARACTER_MAXIMUM_LENGTH AS Longitud
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_NAME = 'Usuarios'
AND COLUMN_NAME = 'UsuarioAD';

PRINT '';
PRINT '============================================';
PRINT 'SCRIPT COMPLETADO EXITOSAMENTE';
PRINT '============================================';
