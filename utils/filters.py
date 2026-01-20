# utils/filters.py - CORREGIDO
from flask import session
import logging
logger = logging.getLogger(__name__)

def filtrar_por_oficina_usuario(datos, campo_oficina_id='oficina_id'):
    """
    Filtra datos según la oficina del usuario actual.
    """
    if 'usuario_id' not in session:
        logger.info("🔍 DEBUG filtrar_por_oficina_usuario: Usuario no autenticado")

        return []
    
    # Importar aquí para evitar dependencia circular
    from utils.permissions import get_office_filter, PermissionManager
    
    # Usar el sistema de permisos actualizado
    office_filter = get_office_filter()
    
    # Si office_filter es None, significa acceso total
    if office_filter is None:
        logger.info("🔍 DEBUG filtrar_por_oficina_usuario: Usuario con acceso total")

        return datos
    
    # Para roles que filtran por oficina específica
    if office_filter == 'own':
        # Filtrar por oficina_id de sesión
        oficina_id_usuario = session.get('oficina_id')
        
        if not oficina_id_usuario:
            logger.info("🔍 DEBUG filtrar_por_oficina_usuario: No hay ID de oficina en sesión")

            return []
        
        logger.info(f"🔍 DEBUG filtrar_por_oficina_usuario: Oficina ID usuario: {oficina_id_usuario}")

        logger.info(f"🔍 DEBUG filtrar_por_oficina_usuario: Total datos a filtrar: {len(datos)}")

        datos_filtrados = []
        for i, item in enumerate(datos):
            item_oficina_id = str(item.get(campo_oficina_id, ''))
            usuario_oficina_id = str(oficina_id_usuario)
            
            if item_oficina_id == usuario_oficina_id:
                datos_filtrados.append(item)
                logger.info(f"🔍 DEBUG filtrar_por_oficina_usuario: Item {i} coincide - Oficina: {item_oficina_id}")

            else:
                logger.info(f"🔍 DEBUG filtrar_por_oficina_usuario: Item {i} NO coincide - Item Oficina: {item_oficina_id}, Usuario Oficina: {usuario_oficina_id}")

        logger.info(f"🔍 DEBUG filtrar_por_oficina_usuario: Filtrados {len(datos_filtrados)} de {len(datos)} items")

        return datos_filtrados
    else:
        # Si office_filter es un string específico (ej: 'COQ', 'CALI', etc.)
        # Aquí necesitarías lógica adicional para filtrar por nombre de oficina
        # Por ahora, devolvemos todos los datos ya que el filtro no es por ID numérico
        logger.info(f"🔍 DEBUG filtrar_por_oficina_usuario: Filtro de oficina por nombre: {office_filter}")

        return datos

def verificar_acceso_oficina(oficina_id):
    """
    Verifica si el usuario actual tiene acceso a una oficina específica.
    """
    if 'usuario_id' not in session:
        return False
    
    # Importar aquí para evitar dependencia circular
    from utils.permissions import get_office_filter
    
    office_filter = get_office_filter()
    
    # Si office_filter es None, tiene acceso total
    if office_filter is None:
        return True
    
    # Si office_filter es 'own', verifica si es su oficina
    if office_filter == 'own':
        oficina_id_usuario = session.get('oficina_id')
        return str(oficina_id) == str(oficina_id_usuario)
    
    # Para otros casos (filtro por nombre de oficina), necesitarías más lógica
    # Por ahora, devolvemos False ya que no hay forma directa de comparar
    return False