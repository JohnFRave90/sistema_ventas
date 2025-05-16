from app import db

class BDExtra(db.Model):
    __tablename__ = 'BD_EXTRAS'

    id              = db.Column(db.Integer, primary_key=True)
    consecutivo     = db.Column(db.String(20), unique=True, nullable=False)
    codigo_vendedor = db.Column(
                         db.String(20),
                         db.ForeignKey('vendedores.codigo_vendedor'),
                         nullable=False
                     )
    fecha           = db.Column(db.Date, nullable=False)
    comentarios     = db.Column(db.Text, nullable=True)
    usado           = db.Column(db.Boolean, default=False, nullable=False)

    items = db.relationship(
        'BDExtraItem',
        back_populates='extra',
        cascade='all, delete-orphan'
    )
