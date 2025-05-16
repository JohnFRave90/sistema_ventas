from app import db
from flask_login import UserMixin

class Usuario(db.Model, UserMixin):
    __tablename__ = 'usuarios'

    id = db.Column(db.Integer, primary_key=True)
    nombre_usuario = db.Column(db.String(100), unique=True, nullable=False)
    contraseña = db.Column(db.String(255), nullable=False)
    rol = db.Column(db.Enum('administrador', 'semiadmin', 'vendedor'), nullable=False)

    def __repr__(self):
        return f"<Usuario {self.nombre_usuario}>"

