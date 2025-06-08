# app/routes/dialogflow_webhook.py

from flask import Blueprint, request, jsonify
from app.models import db, BDPedido, Vendedor  # Asegúrate que estos importen correctamente tus modelos
from datetime import datetime

# Crear blueprint para el webhook
dialogflow_bp = Blueprint('dialogflow', __name__)

@dialogflow_bp.route('/webhook', methods=['POST'])
def webhook():
    try:
        return jsonify({"fulfillmentText": "El webhook está funcionando correctamente."})
    except Exception as e:
        return jsonify({"fulfillmentText": f"Error: {str(e)}"})
