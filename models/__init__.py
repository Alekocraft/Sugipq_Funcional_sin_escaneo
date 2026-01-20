# models/__init__.py

from .materiales_model import MaterialModel
from .oficinas_model import OficinaModel
from .solicitudes_model import SolicitudModel
from .usuarios_model import UsuarioModel
from .novedades_model import NovedadModel
from .inventario_corporativo_model import InventarioCorporativoModel
import logging
logger = logging.getLogger(__name__)

__all__ = [
    "MaterialModel",
    "OficinaModel",
    "SolicitudModel",
    "UsuarioModel",
    "NovedadModel",
    "InventarioCorporativoModel",
]
