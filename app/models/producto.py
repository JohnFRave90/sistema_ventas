from app import db

class Producto(db.Model):
    __tablename__ = 'productos'
    id = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(20), unique=True, nullable=False)
    nombre = db.Column(db.String(50), nullable=False)
    precio = db.Column(db.Float, nullable=False)
    categoria = db.Column(db.String(20), nullable=False)  # 'panadería' o 'bizcochería'
    activo = db.Column(db.Boolean, default=True, nullable=False)
