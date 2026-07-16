# app/models/pedidos.py

from app import db

class BDPedido(db.Model):
    __tablename__ = 'bd_pedidos'

    id               = db.Column(db.Integer, primary_key=True)
    consecutivo      = db.Column(db.String(20), unique=True, nullable=False)
    codigo_vendedor  = db.Column(db.String(25), db.ForeignKey('vendedores.codigo_vendedor'), nullable=False) # CORREGIDO Y AÑADIDO FK
    # Preventa: el pedido se atribuye a un cliente y (opcionalmente) a un turno.
    cliente_id       = db.Column(db.Integer, db.ForeignKey('clientes.id'), nullable=True)
    turno_id         = db.Column(db.Integer, nullable=True)
    fecha            = db.Column(db.Date, nullable=False)
    comentarios      = db.Column(db.Text)
    # Forma de pago pactada al tomar el pedido (mismo esquema que las ventas).
    metodo_pago      = db.Column(db.Enum('efectivo', 'transferencia', 'mixto'), nullable=True)
    monto_efectivo   = db.Column(db.Numeric(10, 2), nullable=True)
    monto_transferencia = db.Column(db.Numeric(10, 2), nullable=True)
    # Estado de cumplimiento: pendiente -> entregado | cancelado.
    estado           = db.Column(
                          db.Enum('pendiente', 'entregado', 'cancelado'),
                          nullable=False,
                          default='pendiente'
                       )
    usado            = db.Column(db.Boolean, default=False)
    uuid_origen      = db.Column(db.String(36), unique=True, nullable=True)

    cliente          = db.relationship('Cliente')

    items            = db.relationship(
                          'BDPedidoItem',
                          back_populates='pedido',
                          cascade='all, delete-orphan'
                       )
