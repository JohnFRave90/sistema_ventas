from app import db

class ConfiguracionTelegram(db.Model):
    __tablename__ = 'config_telegram'
    id = db.Column(db.Integer, primary_key=True)
    activo = db.Column(db.Boolean, default=True)
    token = db.Column(db.String(255), nullable=False)
    chat_id = db.Column(db.String(100), nullable=False)
