# app/routes/dialogflow_webhook.py

from flask import Blueprint, request, jsonify
from app import db
from app.models.pedidos import BDPedido
from app.models.pedido_item import BDPedidoItem
from app.models.vendedor import Vendedor

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
                numero = numero.get('amount')

            if not numero:
                return jsonify({"fulfillmentText": "No entendí el número del pedido que quieres revisar."})

            codigo_pedido = f"PD-{int(numero):05d}"
            pedido = BDPedido.query.filter_by(consecutivo=codigo_pedido).first()

            if not pedido:
                return jsonify({"fulfillmentText": f"No encontré el pedido con código {codigo_pedido}."})
            try:
                # Obtener el vendedor por codigo_vendedor (NO por id)
                vendedor = Vendedor.query.filter_by(codigo_vendedor=pedido.codigo_vendedor).first()
                nombre_vendedor = vendedor.nombre if vendedor else f"con código {pedido.codigo_vendedor}"
            except Exception:
                nombre_vendedor = f"con código {pedido.codigo_vendedor}"

            fecha_formateada = pedido.fecha.strftime('%d de %B de %Y')

            # 🔢 Calcular total sumando los subtotales de los items
            total = sum([float(item.subtotal) for item in pedido.items])
            valor_total = f"{total:,.0f}".replace(",", ".")

            texto = (
                f"El pedido {pedido.consecutivo} es del vendedor {nombre_vendedor}, "
                f"hecho el {fecha_formateada}, y tiene un valor total de {valor_total} pesos."
            )

            return jsonify({"fulfillmentText": texto})

        return jsonify({"fulfillmentText": "No entendí tu intención."})

    except Exception as e:
        return jsonify({"fulfillmentText": f"Ocurrió un error al procesar la solicitud: {str(e)}"})
