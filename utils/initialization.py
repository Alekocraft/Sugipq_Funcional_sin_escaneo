import os
import logging
from datetime import datetime
import pyodbc
from database import get_database_connection
from models.oficinas_model import OficinaModel

logger = logging.getLogger(__name__)

def inicializar_oficina_principal():
    """Verifica y crea la oficina COQ principal si no existe"""
    conn = None
    cursor = None
    
    try:
        logger.info("Verificando existencia de la oficina COQ...")
        
        # Usar el modelo para verificar existencia (método correcto)
        oficina_principal = OficinaModel.obtener_por_nombre("COQ")

        if not oficina_principal:
            logger.info("Creando oficina COQ...")
            conn = get_database_connection()
            
            if conn is None:
                logger.error("No se pudo obtener conexión a la base de datos")
                return False
                
            cursor = conn.cursor()

            # VERIFICAR SI REALMENTE NO EXISTE
            cursor.execute("SELECT OficinaId FROM Oficinas WHERE NombreOficina = 'COQ'")
            if cursor.fetchone():
                logger.info("Oficina COQ ya existe (verificado por query directa)")
                # Cerrar recursos y retornar
                if cursor:
                    cursor.close()
                if conn:
                    conn.close()
                return True
            
            # Insertar la oficina
            cursor.execute("""
                INSERT INTO Oficinas (
                    NombreOficina, 
                    DirectorOficina, 
                    Ubicacion, 
                    EsPrincipal, 
                    Activo, 
                    FechaCreacion,
                    Email
                ) 
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                "COQ",
                "Director General",
                "Ubicación Principal",
                1,  # EsPrincipal
                1,  # Activo
                datetime.now(),
                "coq@empresa.com"
            ))

            conn.commit()
            logger.info("Oficina COQ creada exitosamente")

            # Verificar la creación usando el modelo
            oficina_verificada = OficinaModel.obtener_por_nombre("COQ")
            if oficina_verificada:
                logger.info(f"Oficina COQ verificada - ID: {oficina_verificada.get('id', 'N/A')}")
            else:
                logger.warning("No se pudo verificar la creación de la oficina COQ")
                
        else:
            # La oficina ya existe según el modelo
            logger.info(f"Oficina COQ ya existe - ID: {oficina_principal.get('id', 'N/A')}")
            
        return True
        
    except pyodbc.IntegrityError as e:
        error_str = 'Error interno'
        if any(keyword in error_str for keyword in ['UQ_Oficinas_Nombre', '2627', 'duplicate key']):
            logger.info("Oficina COQ ya existe (evitado duplicado por constraint)")
            return True
        else:
            logger.error("Error de integridad en base de datos: [error](%s)", type(e).__name__)
            return False
            
    except pyodbc.Error as e:
        logger.error("Error de base de datos: [error](%s)", type(e).__name__)
        return False
        
    except Exception as e:
        logger.error("Error inicializando oficina principal: [error](%s)", type(e).__name__)
        return False
        
    finally:
        # Asegurarse de cerrar recursos en cualquier caso
        if cursor:
            try:
                cursor.close()
            except:
                pass  # Ignorar errores al cerrar cursor
        
        if conn:
            try:
                conn.close()
            except:
                pass  # Ignorar errores al cerrar conexión

# El resto del archivo se mantiene igual...
def inicializar_directorios():
    """Crea los directorios necesarios para el funcionamiento de la aplicación"""
    from config.config import Config
    
    directorios = [
        Config.UPLOAD_FOLDER,
        os.path.join(Config.UPLOAD_FOLDER, 'productos'),
        os.path.join(Config.UPLOAD_FOLDER, 'documentos'),
        os.path.join(Config.UPLOAD_FOLDER, 'perfiles'),
        os.path.join(Config.UPLOAD_FOLDER, 'temp')
    ]
    
    for directorio in directorios:
        try:
            os.makedirs(directorio, exist_ok=True)
            logger.debug(f"Directorio verificado/creado: {directorio}")
        except Exception as e:
            logger.error("Error creando directorio {directorio}: [error](%s)", type(e).__name__)

def verificar_configuracion():
    """Valida la configuración básica del sistema"""
    from config.config import Config
    
    logger.info("Verificando configuración del sistema...")
    
    directorios_requeridos = [Config.TEMPLATE_FOLDER, Config.STATIC_FOLDER]
    for folder in directorios_requeridos:
        if not os.path.exists(folder):
            logger.error(f"Directorio requerido no encontrado: {folder}")
        else:
            logger.debug(f"Directorio encontrado: {folder}")
    
    if Config.SECRET_KEY == 'dev-secret-key-change-in-production':
        logger.warning("Usando SECRET_KEY por defecto - Cambiar en producción")
    
    logger.info("Verificación de configuración completada")

def inicializar_roles_permisos():
    """Verifica la configuración de roles y permisos del sistema"""
    try:
        from config.config import Config
        roles_configurados = list(Config.ROLES.keys())
        logger.info(f"Roles configurados en el sistema: {len(roles_configurados)} roles")
        logger.debug(f"Roles: {', '.join(roles_configurados)}")
        
    except Exception as e:
        logger.error("Error verificando configuración de roles: [error](%s)", type(e).__name__)

def inicializar_todo():
    """Ejecuta todas las rutinas de inicialización del sistema"""
    logger.info("Iniciando proceso de inicialización del sistema...")
    
    verificar_configuracion()
    inicializar_directorios()
    
    # Inicializar oficina principal - continuar incluso si falla
    try:
        if inicializar_oficina_principal():
            logger.info("Oficina COQ inicializada correctamente")
        else:
            logger.warning("Inicialización de oficina tuvo problemas")
    except Exception as e:
        logger.error("Error en inicialización de oficina: [error](%s)", type(e).__name__)
        # Continuar con otras inicializaciones
    
    inicializar_roles_permisos()
    
    logger.info("Proceso de inicialización completado")

# Para compatibilidad con imports existentes
if __name__ == "__main__":
    inicializar_todo()