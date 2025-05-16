from app import db

class BDDevolucionItem(db.Model):
    __tablename__ = 'BD_DEVOLUCION_ITEMS'

    id               = db.Column(db.Integer, primary_key=True)
    devolucion_id    = db.Column(
                          db.Integer,
                          db.ForeignKey('BD_DEVOLUCIONES.id'),
                          nullable=False
                       )
    producto_cod     = db.Column(db.String(20), nullable=False)
    cantidad         = db.Column(db.Integer, nullable=False)
    precio_unit      = db.Column(db.Numeric(10,2), nullable=False)
    subtotal         = db.Column(db.Numeric(12,2), nullable=False)

    devolucion       = db.relationship(
                          'BDDevolucion',
                          back_populates='items'
                       )
