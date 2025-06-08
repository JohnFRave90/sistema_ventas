# app/routes/dialogflow_webhook.py

from flask import Blueprint, request, jsonify
from app import db
from app.models.pedidos import BDPedido
from app.models.vendedor import Vendedor

# Crear blueprint para el webhook
dialogflow_bp = Blueprint('dialogflow', __name__)

@dialogflow_bp.route('/webhook', methods=['POST'])
def webhook():
    try:
        data = request.get_json()
        intent = data['queryResult']['intent']['displayName']
        parameters = data['queryResult'].get('parameters', {})

        if intent == 'RevisarPedido':
            numero = parameters.get('numero_pedido')

            if isinstance(numero, dict):
                numero = numero.get('amount')  # Manejo si viene como {amount: 18}

            if not numero:
                return jsonify({"fulfillmentText": "No entendí el número del pedido que quieres revisar."})

            # Generar código tipo PD-00018
            codigo_pedido = f"PD-{int(numero):05d}"

            # Buscar el pedido por el campo correcto: consecutivo
            pedido = BDPedido.query.filter_by(consecutivo=codigo_pedido).first()

            if not pedido:
                return jsonify({"fulfillmentText": f"No encontré el pedido con código {codigo_pedido}."})

            # Obtener el nombre del vendedor
            vendedor = Vendedor.query.get(pedido.codigo_vendedor)
            nombre_vendedor = vendedor.nombre if vendedor else "no identificado"

            fecha_formateada = pedido.fecha.strftime('%d de %B de %Y')
            valor_total = f"{pedido.total_venta:,.0f}".replace(",", ".")

            texto = (
                f"El pedido {pedido.consecutivo} es del vendedor {nombre_vendedor}, "
                f"hecho el {fecha_formateada}, y tiene un valor total de {valor_total} pesos."
            )

            return jsonify({"fulfillmentText": texto})

        # Otro intent no manejado
        return jsonify({"fulfillmentText": "No entendí tu intención."})

    except Exception as e:
        return jsonify({"fulfillmentText": f"Ocurrió un error al procesar la solicitud: {str(e)}"})
