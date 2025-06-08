# app/routes/dialogflow_webhook.py

from flask import Blueprint, request, jsonify
from app.models import db, BDPedido, Vendedor  # Asegúrate que estos importen correctamente tus modelos
from datetime import datetime

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
                numero = numero.get('amount')  # Manejar si viene como {amount: 18}

            if not numero:
                return jsonify({"fulfillmentText": "No entendí el número del pedido que quieres revisar."})

            codigo_pedido = f"PD-{int(numero):05d}"

            pedido = BDPedido.query.filter_by(codigo=codigo_pedido).first()

            if not pedido:
                return jsonify({"fulfillmentText": f"No encontré el pedido con código {codigo_pedido}."})

            vendedor = Vendedor.query.get(pedido.codigo_vendedor)
            nombre_vendedor = vendedor.nombre if vendedor else "no identificado"

            fecha_formateada = pedido.fecha.strftime('%d de %B de %Y')
            valor_total = f"{pedido.total_venta:,.0f}".replace(",", ".")

            texto = (
                f"El pedido {pedido.codigo} es del vendedor {nombre_vendedor}, "
                f"hecho el {fecha_formateada}, y tiene un valor total de {valor_total} pesos."
            )

            return jsonify({"fulfillmentText": texto})

        return jsonify({"fulfillmentText": "No entendí tu intención."})

    except Exception as e:
        return jsonify({"fulfillmentText": f"Ocurrió un error al procesar la solicitud: {str(e)}"})

    try:
        data = request.get_json()
        intent = data['queryResult']['intent']['displayName']
        parameters = data['queryResult'].get('parameters', {})

        # Intento: RevisarPedido
        if intent == 'RevisarPedido':
            numero = parameters.get('numero_pedido')
            if isinstance(numero, dict):
                numero = numero.get('amount')  # Dialogflow puede devolver { "amount": 18 }

            if not numero:
                return jsonify({"fulfillmentText": "No entendí el número del pedido que quieres revisar."})

            # Generar código tipo PD-00018
            codigo_pedido = f"PD-{int(numero):05d}"

            # Buscar el pedido por código
            pedido = BDPedido.query.filter_by(codigo=codigo_pedido).first()

            if not pedido:
                return jsonify({"fulfillmentText": f"No encontré el pedido con código {codigo_pedido}."})

            # Obtener información del vendedor
            vendedor = Vendedor.query.get(pedido.codigo_vendedor)
            nombre_vendedor = vendedor.nombre if vendedor else "no identificado"

            fecha_formateada = pedido.fecha.strftime('%d de %B de %Y')
            valor_total = f"{pedido.total_venta:,.0f}".replace(",", ".")

            texto = (
                f"El pedido {pedido.codigo} es del vendedor {nombre_vendedor}, "
                f"hecho el {fecha_formateada}, y tiene un valor total de {valor_total} pesos."
            )

            return jsonify({"fulfillmentText": texto})

        return jsonify({"fulfillmentText": "No entendí tu intención."})

    except Exception as e:
        return jsonify({"fulfillmentText": f"Ocurrió un error al procesar la solicitud: {str(e)}"})
