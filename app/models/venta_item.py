from app import db

class BDVentaItem(db.Model):
    __tablename__ = 'BD_VENTA_ITEMS'

    id           = db.Column(db.Integer, primary_key=True)
    venta_id     = db.Column(
                       db.Integer,
                       db.ForeignKey('BD_VENTAS.id'),
                       nullable=False
                   )
    producto_cod = db.Column(db.String(20), nullable=False)
    cantidad     = db.Column(db.Integer, nullable=False)
    precio_unit  = db.Column(db.Numeric(10,2), nullable=False)
    subtotal     = db.Column(db.Numeric(12,2), nullable=False)
    comision     = db.Column(db.Numeric(12,2), nullable=False)
    pagar_pan    = db.Column(db.Numeric(12,2), nullable=False)

    venta        = db.relationship(
                       'BDVenta',
                       back_populates='items'
                   )

    def __repr__(self):
        return (
            f"<BDVentaItem venta_id={self.venta_id} "
            f"producto={self.producto_cod} qty={self.cantidad}>"
        )
