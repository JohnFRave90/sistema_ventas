from app import db

class BDPedidoItem(db.Model):
    __tablename__ = 'BD_PEDIDO_ITEMS'

    id           = db.Column(db.Integer, primary_key=True)
    pedido_id    = db.Column(
                       db.Integer,
                       db.ForeignKey('bd_pedidos.id'),  # debe coincidir con __tablename__ en BDPedido
                       nullable=False
                   )
    producto_cod = db.Column(db.String(20), nullable=False)
    cantidad     = db.Column(db.Integer, nullable=False)
    precio_unit  = db.Column(db.Numeric(10,2), nullable=False)
    subtotal     = db.Column(db.Numeric(12,2), nullable=False)

    pedido       = db.relationship(
                       'BDPedido',
                       back_populates='items'
                   )