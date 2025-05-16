# app/models/liquidacion.py

from app import db
from datetime import datetime

class BD_LIQUIDACION(db.Model):
    __tablename__ = 'bd_liquidaciones'
    id = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(10), unique=True, nullable=False)  # LQ-XXXX
    fecha = db.Column(db.Date, nullable=False)
    codigo_vendedor = db.Column(db.String(10), nullable=False)
    codigo_venta = db.Column(db.Integer, nullable=False)  # VT-000X
    valor_venta = db.Column(db.Float, nullable=False)
    valor_comision = db.Column(db.Float, nullable=False)
    descuento_cambios = db.Column(db.Float, default=0)
    valor_a_pagar = db.Column(db.Float, nullable=False)
    pago_banco = db.Column(db.Float, default=0)
    pago_efectivo = db.Column(db.Float, default=0)
    pago_otros = db.Column(db.Float, default=0)
    comentarios = db.Column(db.Text)
    usuario_creador = db.Column(db.String(50), nullable=False)
    fecha_creacion = db.Column(db.DateTime, default=datetime.now)
    usuario_modificador = db.Column(db.String(50))
    fecha_modificacion = db.Column(db.DateTime)
