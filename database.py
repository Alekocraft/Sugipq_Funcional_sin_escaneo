#utils/database.py

import pyodbc
import logging

# Configuración de logging
logger = logging.getLogger(__name__)

class Database:
    """
    Clase para manejar la conexión a la base de datos SQL Server
    Utiliza autenticación integrada de Windows (Trusted_Connection)
    """
    def __init__(self):
        
        self.server = 'localhost\\SQLEXPRESS'   
       
        
        self.database = 'SistemaGestionInventariost'
        self.driver = '{ODBC Driver 17 for SQL Server}'
    
    def get_connection(self):
        """
        Establece una conexión con la base de datos
        
        Returns:
            pyodbc.Connection: Objeto de conexión a la base de datos
            None: Si la conexión falla
        """
        try:
            conn_str = f"""
                DRIVER={self.driver};
                SERVER={self.server};
                DATABASE={self.database};
                Trusted_Connection=yes;
            """
            conn = pyodbc.connect(conn_str)
            logger.info(f"Conexión a la base de datos establecida exitosamente - Servidor: {self.server}")
            return conn
        except pyodbc.InterfaceError as e:
            logger.error(f"Error de interfaz ODBC al conectar a la base de datos: {e}")
            return None
        except pyodbc.OperationalError as e:
            logger.error(f"Error operacional al conectar a la base de datos: {e}")
            
            # Mensaje de diagnóstico adicional
            if "Named Pipes" in str(e) or "Server is not found" in str(e):
                logger.error(f"""
                    DIAGNÓSTICO DE ERROR:
                    1. Verifica que el servicio 'SQL Server (SQLEXPRESS)' esté en estado 'Running'
                    2. Asegúrate que 'SQL Server Browser' esté iniciado (debería decir 'Running')
                    3. Instancia configurada: {self.server}
                    4. Base de datos: {self.database}
                    
                    SOLUCIONES RÁPIDAS:
                    - Iniciar servicio 'SQL Server Browser' desde services.msc
                    - Probar con '.\\SQLEXPRESS' en lugar de 'localhost\\SQLEXPRESS'
                    - Verificar en SSMS que la base de datos existe en la instancia SQLEXPRESS
                """)
            return None
        except Exception as e:
            logger.error(f"Error inesperado al conectar a la base de datos: {e}", exc_info=True)
            return None

# Instancia global de la base de datos para uso en toda la aplicación
db = Database()

def get_database_connection():
    """
    Proporciona una conexión a la base de datos
    Mantiene compatibilidad con imports existentes en la aplicación
    
    Returns:
        pyodbc.Connection: Conexión a la base de datos configurada
    """
    return db.get_connection()