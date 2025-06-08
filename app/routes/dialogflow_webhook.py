from flask import Blueprint, request, jsonify
from app import db
from app.models.pedidos import BDPedido
from app.models.pedido_item import BDPedidoItem
from app.models.vendedor import Vendedor
from datetime import datetime

dialogflow_bp = Blueprint("dialogflow", __name__)

@dialogflow_bp.route("/webhook", methods=["POST"])
def webhook():
    try:
        # Leer el JSON recibido desde Dialogflow
        req = request.get_json()
        print("📥 JSON recibido:", req)

        # Detectar nombre del intent
        intent = req.get("queryResult", {}).get("intent", {}).get("displayName", "")
        print("🎯 Intent detectado:", intent)

        if intent == "RevisarPedido":
            numero = req.get("queryResult", {}).get("parameters", {}).get("numero_pedido")
            print("🔢 número_pedido recibido:", numero)

            if not numero:
                mensaje = "Por favor, dime qué número de pedido quieres revisar."
                print("⚠️ Falta número de pedido")
                return jsonify({
                    "fulfillmentText": mensaje,
                    "fulfillmentMessages": [
                        {"text": {"text": [mensaje]}}
                    ]
                })

            consecutivo = f"PD-{int(numero):05d}"
            print("🔍 Buscando pedido con consecutivo:", consecutivo)

            pedido = BDPedido.query.filter_by(consecutivo=consecutivo).first()
            if not pedido:
                mensaje = f"No encontré el pedido número {numero}."
                print("❌ Pedido no encontrado:", consecutivo)
                return jsonify({
                    "fulfillmentText": mensaje,
                    "fulfillmentMessages": [
                        {"text": {"text": [mensaje]}}
                    ]
                })

            vendedor = Vendedor.query.filter_by(codigo_vendedor=pedido.codigo_vendedor).first()
            nombre_vendedor = vendedor.nombre if vendedor else f"con código {pedido.codigo_vendedor}"
            print("🧾 Vendedor encontrado:", nombre_vendedor)

            items = BDPedidoItem.query.filter_by(pedido_id=pedido.id).all()
            total = sum([item.subtotal for item in items])
            print("💰 Total calculado:", total)

            fecha_formateada = pedido.fecha.strftime('%d de %B de %Y')
            valor_total = f"{total:,.0f}".replace(",", ".")

            mensaje = (
                f"El pedido {consecutivo} es del vendedor {nombre_vendedor}, "
                f"hecho el {fecha_formateada}, y tiene un valor total de {valor_total} pesos."
            )

            print("✅ Respuesta generada:", mensaje)

            return jsonify({
                "fulfillmentText": mensaje,
                "fulfillmentMessages": [
                    {"text": {"text": [mensaje]}}
                ]
            })

        print("❓ Intent no manejado:", intent)
        return jsonify({
            "fulfillmentText": "No entendí tu solicitud.",
            "fulfillmentMessages": [
                {"text": {"text": ["No entendí tu solicitud."]}}
            ]
        })

    except Exception as e:
        print("❌ Error en webhook:", str(e))
        return jsonify({
            "fulfillmentText": f"Ocurrió un error al procesar tu solicitud: {str(e)}",
            "fulfillmentMessages": [
                {"text": {"text": [f"Ocurrió un error al procesar tu solicitud: {str(e)}"]}}
            ]
        })
