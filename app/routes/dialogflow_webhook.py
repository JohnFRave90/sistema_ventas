# app/routes/dialogflow_webhook.py

from flask import Blueprint, request, jsonify
from app.models.pedidos import BDPedido
from app.models.pedido_item import BDPedidoItem
from app.models.vendedor import Vendedor
from datetime import datetime

dialogflow_bp = Blueprint("dialogflow", __name__)

@dialogflow_bp.route("/webhook", methods=["POST"])
def webhook():
    try:
        req = request.get_json()
        intent = req.get("queryResult", {}).get("intent", {}).get("displayName", "")
        
        if intent == "RevisarPedido":
            numero_pedido = req["queryResult"]["parameters"].get("numero_pedido")
            if not numero_pedido:
                return jsonify({"fulfillmentText": "Por favor dime qué número de pedido quieres revisar."})

            consecutivo = f"PD-{int(numero_pedido):05d}"

            # Buscar el pedido
            pedido = BDPedido.query.filter_by(consecutivo=consecutivo).first()
            if not pedido:
                return jsonify({"fulfillmentText": f"No encontré ningún pedido con número {numero_pedido}."})

            # Buscar el nombre del vendedor por codigo_vendedor (no id)
            vendedor = Vendedor.query.filter_by(codigo_vendedor=pedido.codigo_vendedor).first()
            nombre_vendedor = vendedor.nombre if vendedor else f"con código {pedido.codigo_vendedor}"

            # Calcular total de items
            items = BDPedidoItem.query.filter_by(pedido_id=pedido.id).all()
            valor_total = sum(item.subtotal for item in items)

            # Formatear fecha
            fecha_formateada = pedido.fecha.strftime('%d de %B de %Y')

            # Preparar respuesta
            respuesta = {
                "fulfillmentText": f"El pedido {consecutivo} es del vendedor {nombre_vendedor}, hecho el {fecha_formateada}, y tiene un valor total de {valor_total:,.0f} pesos."
            }

            print("➡️ Respuesta enviada a Dialogflow:", respuesta)
            return jsonify(respuesta)

        # Intent no manejado
        return jsonify({"fulfillmentText": "No entendí tu solicitud."})

    except Exception as e:
        print("❌ Error en webhook:", e)
        return jsonify({"fulfillmentText": f"Ocurrió un error al procesar la solicitud: {str(e)}"})
