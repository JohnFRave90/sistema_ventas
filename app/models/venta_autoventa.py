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
    turno_id         = db.Column(db.Integer, db.ForeignKey('bd_turnos.id'), nullable=True)
    visit_id         = db.Column(db.Integer, db.ForeignKey('bd_visitas_clientes.id'), nullable=True)
    fecha            = db.Column(db.Date, nullable=False)
    total            = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    # Forma de pago capturada en el app. 'mixto' reparte total entre
    # monto_efectivo + monto_transferencia. NULL en histórico previo a la feature.
    metodo_pago      = db.Column(db.Enum('efectivo', 'transferencia', 'mixto'), nullable=True)
    monto_efectivo   = db.Column(db.Numeric(10, 2), nullable=True)
    monto_transferencia = db.Column(db.Numeric(10, 2), nullable=True)
    enviada_por_sync = db.Column(db.Boolean, default=False, nullable=False)
    uuid_origen      = db.Column(db.String(36), unique=True, nullable=True)
    created_at       = db.Column(db.DateTime, server_default=db.func.now())

    cliente = db.relationship('Cliente', back_populates='ventas')
    turno = db.relationship('BDTurno')
    visita = db.relationship('BDVisitaCliente')
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
