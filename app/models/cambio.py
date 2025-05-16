# app/models/cambio.py

from app import db
from datetime import datetime

class BD_CAMBIO(db.Model):
    __tablename__ = 'bd_cambios'
    id = db.Column(db.Integer, primary_key=True)
    fecha = db.Column(db.Date, nullable=False)
    codigo_vendedor = db.Column(db.String(10), nullable=False)
    valor_cambio = db.Column(db.Float, nullable=False)
    comentarios = db.Column(db.Text)
    usuario_creador = db.Column(db.String(50), nullable=False)
    fecha_creacion = db.Column(db.DateTime, default=datetime.now)


