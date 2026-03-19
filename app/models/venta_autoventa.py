# app/models/venta_autoventa.py

from app import db
from app.utils.documentos import generar_consecutivo

class BDVentaAutoventa(db.Model):
    __tablename__ = 'bd_ventas_autoventa'

    id               = db.Column(db.Integer, primary_key=True)
    consecutivo      = db.Column(db.String(20), unique=True, nullable=False)
    codigo_vendedor  = db.Column(
        db.String(25),
        db.ForeignKey('vendedores.codigo_vendedor'),
        nullable=False
    )
    cliente_id       = db.Column(db.Integer, db.ForeignKey('clientes.id'), nullable=False)
    fecha            = db.Column(db.Date, nullable=False)
    total            = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    enviada_por_sync = db.Column(db.Boolean, default=False, nullable=False)
    uuid_origen      = db.Column(db.String(36), unique=True, nullable=True)
    created_at       = db.Column(db.DateTime, server_default=db.func.now())

    cliente = db.relationship('Cliente', back_populates='ventas')
    items   = db.relationship(
        'BDVentaAutoventaItem',
        back_populates='venta',
        cascade='all, delete-orphan'
    )

    @staticmethod
    def siguiente_consecutivo():
        return generar_consecutivo(BDVentaAutoventa, 'AV')


class BDVentaAutoventaItem(db.Model):
    __tablename__ = 'bd_ventas_autoventa_items'

    id           = db.Column(db.Integer, primary_key=True)
    autoventa_id = db.Column(db.Integer, db.ForeignKey('bd_ventas_autoventa.id'), nullable=False)
    producto_cod = db.Column(db.String(20), db.ForeignKey('productos.codigo'), nullable=False)
    cantidad     = db.Column(db.Integer, nullable=False)
    precio_unit  = db.Column(db.Numeric(10, 2), nullable=False)
    subtotal     = db.Column(db.Numeric(10, 2), nullable=False)

    venta    = db.relationship('BDVentaAutoventa', back_populates='items')
    producto = db.relationship('Producto')
