from flask import Blueprint, jsonify, session
from models.materiales_model import MaterialModel
from utils.filters import verificar_acceso_oficina
import logging
from utils.helpers import sanitizar_log_text

logger = logging.getLogger(__name__)

api_bp = Blueprint('api', __name__)

@api_bp.route('/material/<int:material_id>')
def api_material(material_id):
    if 'usuario_id' not in session:
        return jsonify({'error': 'No autorizado'}), 401
    try:
        material = MaterialModel.obtener_por_id(material_id)
        if material and verificar_acceso_oficina(material.get('oficina_id')):
            return jsonify(material)
        else:
            return jsonify({'error': 'Material no encontrado o sin permisos'}), 404
    except Exception as e:
        logger.error("❌ Error API material: %s", sanitizar_log_text('Error interno'))
        return jsonify({'error': 'Error interno del servidor'}), 500

@api_bp.route('/material/<int:material_id>/stock', methods=['GET'])
def api_material_stock(material_id):
    if 'usuario_id' not in session:
        return jsonify({'error': 'No autorizado'}), 401
    try:
        material = MaterialModel.obtener_por_id(material_id)
        if material and verificar_acceso_oficina(material.get('oficina_id')):
            return jsonify({
                'stock': material.get('cantidad', 0),
                'valor_unitario': material.get('valor_unitario', 0)
            })
        else:
            return jsonify({'error': 'Material no encontrado o sin permisos'}), 404
    except Exception as e:
        logger.error("❌ Error API stock: %s", sanitizar_log_text('Error interno'))
        return jsonify({'error': 'Error interno del servidor'}), 500

@api_bp.route('/oficina/<int:oficina_id>/materiales')
def api_oficina_materiales(oficina_id):
    if 'usuario_id' not in session:
        return jsonify({'error': 'No autorizado'}), 401
    try:
        if not verificar_acceso_oficina(oficina_id):
            return jsonify({'error': 'No tiene permisos para acceder a esta oficina'}), 403

        materiales = MaterialModel.obtener_todos() or []
        materiales_oficina = [mat for mat in materiales if mat.get('oficina_id') == oficina_id]
        return jsonify(materiales_oficina)
    except Exception as e:
        logger.error("❌ Error API oficina materiales: %s", sanitizar_log_text('Error interno'))
        return jsonify({'error': 'Error interno del servidor'}), 500