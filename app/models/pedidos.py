# app/models/pedidos.py

from app import db

class BDPedido(db.Model):
    __tablename__ = 'bd_pedidos'

    id               = db.Column(db.Integer, primary_key=True)
    consecutivo      = db.Column(db.String(20), unique=True, nullable=False)
    codigo_vendedor  = db.Column(db.String(25), db.ForeignKey('vendedores.codigo_vendedor'), nullable=False) # CORREGIDO Y AÑADIDO FK
    fecha            = db.Column(db.Date, nullable=False)
    comentarios      = db.Column(db.Text)
    usado            = db.Column(db.Boolean, default=False)

    items            = db.relationship(
                          'BDPedidoItem',
                          back_populates='pedido',
                          cascade='all, delete-orphan'
                       )
