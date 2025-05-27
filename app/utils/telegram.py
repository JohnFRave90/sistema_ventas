from app import db
from app.models.config_telegram import ConfiguracionTelegram
import requests

def enviar_telegram(mensaje):
    config = ConfiguracionTelegram.query.first()
    if not config or not config.activo:
        return  # Notificaciones desactivadas

    try:
        url = f"https://api.telegram.org/bot{config.token}/sendMessage"
        payload = {
            "chat_id": config.chat_id,
            "text": mensaje,
            "parse_mode": "Markdown"
        }
        requests.post(url, data=payload)
    except Exception as e:
        print(f"[TELEGRAM] Error al enviar: {e}")
