# app/routes/dialogflow_webhook.py

from flask import Blueprint, request, jsonify
from app.models import BDPedido, Vendedor  # Ajusta los nombres según tus modelos
from datetime import datetime

dialogflow_bp = Blueprint('dialogflow', __name__)

@dialogflow_bp.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json()

    intent = data['queryResult']['intent']['displayName']

    if intent == 'RevisarPedido':
        numero = data['queryResult']['parameters'].get('numero_pedido')

        if not numero:
            return jsonify({"fulfillmentText": "No me dijiste el número del pedido."})

        # Convertir número a código tipo PD-00018
        codigo = f"PD-{int(numero):05d}"

        pedido = BDPedido.query.filter_by(codigo=codigo).first()

        if not pedido:
            return jsonify({"fulfillmentText": f"No encontré el pedido número {numero}."})

        vendedor = Vendedor.query.get(pedido.codigo_vendedor)

        texto = (
            f"El pedido {pedido.codigo} es del vendedor {vendedor.nombre}, "
            f"hecho el {pedido.fecha.strftime('%d de %B de %Y')} "
            f"por un valor total de {pedido.total_venta} pesos."
        )

        return jsonify({"fulfillmentText": texto})

    return jsonify({"fulfillmentText": "No entendí tu solicitud."})

