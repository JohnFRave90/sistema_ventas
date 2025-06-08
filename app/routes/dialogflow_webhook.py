from flask import Blueprint, request, jsonify
from app.extensions import db  # Asegúrate de importar desde donde defines SQLAlchemy
from app.models.pedidos import BDPedido
from app.models.pedido_item import BDPedidoItem
from app.models.vendedor import Vendedor
from datetime import datetime

dialogflow_bp = Blueprint("dialogflow", __name__)

@dialogflow_bp.route("/webhook", methods=["POST"])
def webhook():
    try:
        req = request.get_json()
        print("📥 Petición recibida:", req)

        intent = req.get("queryResult", {}).get("intent", {}).get("displayName", "")
        
        if intent == "RevisarPedido":
            numero = req.get("queryResult", {}).get("parameters", {}).get("numero_pedido")

            if not numero:
                return jsonify({
                    "fulfillmentText": "Por favor, dime qué número de pedido quieres revisar.",
                    "fulfillmentMessages": [
                        {
                            "text": {
                                "text": ["Por favor, dime qué número de pedido quieres revisar."]
                            }
                        }
                    ]
                })

            consecutivo = f"PD-{int(numero):05d}"

            # Buscar el pedido
            pedido = BDPedido.query.filter_by(consecutivo=consecutivo).first()
            if not pedido:
                mensaje = f"No encontré el pedido número {numero}."
                return jsonify({
                    "fulfillmentText": mensaje,
                    "fulfillmentMessages": [
                        {"text": {"text": [mensaje]}}
                    ]
                })

            # Obtener vendedor
            vendedor = Vendedor.query.filter_by(codigo_vendedor=pedido.codigo_vendedor).first()
            nombre_vendedor = vendedor.nombre if vendedor else f"con código {pedido.codigo_vendedor}"

            # Sumar subtotales
            items = BDPedidoItem.query.filter_by(pedido_id=pedido.id).all()
            total = sum([item.subtotal for item in items])

            # Fecha formateada
            fecha_formateada = pedido.fecha.strftime('%d de %B de %Y')
            valor_total = f"{total:,.0f}".replace(",", ".")

            mensaje = (
                f"El pedido {consecutivo} es del vendedor {nombre_vendedor}, "
                f"hecho el {fecha_formateada}, y tiene un valor total de {valor_total} pesos."
            )

            respuesta = {
                "fulfillmentText": mensaje,
                "fulfillmentMessages": [
                    {"text": {"text": [mensaje]}}
                ]
            }

            print("✅ Respuesta enviada a Dialogflow:", respuesta)
            return jsonify(respuesta)

        # Si el intent no está manejado
        return jsonify({
            "fulfillmentText": "No entendí tu solicitud.",
            "fulfillmentMessages": [
                {"text": {"text": ["No entendí tu solicitud."]}}
            ]
        })

    except Exception as e:
        print("❌ Error en webhook:", str(e))
        mensaje = f"Ocurrió un error al procesar tu solicitud: {str(e)}"
        return jsonify({
            "fulfillmentText": mensaje,
            "fulfillmentMessages": [
                {"text": {"text": [mensaje]}}
            ]
        })
