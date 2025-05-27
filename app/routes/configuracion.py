from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from app import db
from app.models.config_telegram import ConfiguracionTelegram
from app.utils.roles import rol_requerido

config_bp = Blueprint('configuracion', __name__, url_prefix='/config')

@config_bp.route('/telegram', methods=['GET', 'POST'])
@login_required
@rol_requerido('administrador')
def configurar_telegram():
    import requests
    from app.models.config_telegram import ConfiguracionTelegram

    config = ConfiguracionTelegram.query.first()
    if not config:
        config = ConfiguracionTelegram(activo=False, token='', chat_id='')
        db.session.add(config)
        db.session.commit()

    if request.method == 'POST':
        nuevo_token = request.form.get('token', '').strip()
        nuevo_chat_id = request.form.get('chat_id', '').strip()
        activo = 'activo' in request.form

        # Intento de mensaje de prueba
        url = f"https://api.telegram.org/bot{nuevo_token}/sendMessage"
        payload = {
            "chat_id": nuevo_chat_id,
            "text": "✅ Prueba de conexión exitosa desde la app Incolpan.",
            "parse_mode": "Markdown"
        }

        try:
            response = requests.post(url, data=payload)
            response.raise_for_status()  # Error si el token/chat_id es inválido

            # Guardar solo si fue exitoso
            config.activo = activo
            config.token = nuevo_token
            config.chat_id = nuevo_chat_id
            db.session.commit()

            flash("✅ Configuración de Telegram actualizada correctamente.", "success")
            return redirect(url_for('configuracion.configurar_telegram'))

        except Exception as e:
            flash("❌ Error al conectar con Telegram: Verifica el token y el chat ID.", "danger")

    return render_template('config/telegram.html', config=config)
