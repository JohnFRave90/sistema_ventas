# app/models/cambio.py

from datetime import datetime

from app import db


# ── LEGACY WEB-ADMIN MODEL ──────────────────────────────────────────────────
# Descuento por cambio creado manualmente desde el admin web, usado por
# liquidaciones. Vive en la tabla BD_CAMBIO (un solo campo monetario
# valor_cambio). NO confundir con BDCambio (intercambios del app movil).
class BD_CAMBIO(db.Model):
    __tablename__ = 'BD_CAMBIO'

    id              = db.Column(db.Integer, primary_key=True)
    fecha           = db.Column(db.Date, nullable=False)
    codigo_vendedor = db.Column(db.String(25), nullable=False)
    valor_cambio    = db.Column(db.Float, nullable=False, default=0)
    comentarios     = db.Column(db.Text, nullable=True)
    usuario_creador = db.Column(db.String(50), nullable=False)
    fecha_creacion  = db.Column(db.DateTime, default=datetime.now)


# ── MOBILE-APP EXCHANGE TRANSACTION ─────────────────────────────────────────
# Un cambio del app es un intercambio con dos piernas: lo que el cliente
# devuelve (tipo='devolucion') y lo que el vendedor entrega (tipo='venta').
# Tabla propia (bd_cambios / bd_cambio_items): NO se mezcla con BD_DEVOLUCIONES.
class BDCambio(db.Model):
    __tablename__ = 'bd_cambios'

    id              = db.Column(db.Integer, primary_key=True)
    consecutivo     = db.Column(db.String(20), unique=True, nullable=False)
    codigo_vendedor = db.Column(db.String(25), db.ForeignKey('vendedores.codigo_vendedor'), nullable=False)
    cliente_id      = db.Column(db.Integer, db.ForeignKey('clientes.id'), nullable=False)
    turno_id        = db.Column(db.Integer, db.ForeignKey('bd_turnos.id'), nullable=True)
    visit_id        = db.Column(db.Integer, db.ForeignKey('bd_visitas_clientes.id'), nullable=True)
    fecha           = db.Column(db.Date, nullable=False)
    total_venta     = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    # Forma de pago del neto del cambio (mismo esquema que BDVentaAutoventa).
    metodo_pago     = db.Column(db.Enum('efectivo', 'transferencia', 'mixto'), nullable=True)
    monto_efectivo  = db.Column(db.Numeric(10, 2), nullable=True)
    monto_transferencia = db.Column(db.Numeric(10, 2), nullable=True)
    comentarios     = db.Column(db.Text, nullable=True)
    # Idempotencia offline: uuid enviado desde la app.
    uuid_origen     = db.Column(db.String(36), unique=True, nullable=True)
    fecha_creacion  = db.Column(db.DateTime, default=datetime.now)

    items = db.relationship(
        'BDCambioItem',
        back_populates='cambio',
        cascade='all, delete-orphan',
    )


class BDCambioItem(db.Model):
    __tablename__ = 'bd_cambio_items'

    id           = db.Column(db.Integer, primary_key=True)
    cambio_id    = db.Column(db.Integer, db.ForeignKey('bd_cambios.id'), nullable=False)
    # 'devolucion' = producto que regresa del cliente (pierna de devolucion)
    # 'venta'      = producto que sale al cliente (pierna de venta; espeja BDVentaAutoventa)
    tipo         = db.Column(db.Enum('devolucion', 'venta'), nullable=False)
    producto_cod = db.Column(db.String(20), db.ForeignKey('productos.codigo'), nullable=False)
    cantidad     = db.Column(db.Integer, nullable=False)
    precio_unit  = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    subtotal     = db.Column(db.Numeric(12, 2), nullable=False, default=0)

    cambio   = db.relationship('BDCambio', back_populates='items')
    producto = db.relationship('Producto')
