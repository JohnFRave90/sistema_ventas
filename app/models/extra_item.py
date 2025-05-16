from app import db

class BDExtraItem(db.Model):
    __tablename__ = 'BD_EXTRA_ITEMS'

    id           = db.Column(db.Integer, primary_key=True)
    extra_id     = db.Column(
                       db.Integer,
                       db.ForeignKey('BD_EXTRAS.id'),  # referencia a la tabla de arriba
                       nullable=False
                   )
    producto_cod = db.Column(db.String(20), nullable=False)
    cantidad     = db.Column(db.Integer, nullable=False)
    precio_unit  = db.Column(db.Numeric(10,2), nullable=False)
    subtotal     = db.Column(db.Numeric(12,2), nullable=False)

    extra        = db.relationship(
                       'BDExtra',
                       back_populates='items'
                   )

