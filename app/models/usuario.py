from app import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

class Usuario(db.Model, UserMixin):
    __tablename__ = 'usuarios'

    id = db.Column(db.Integer, primary_key=True)
    nombre_usuario = db.Column(db.String(100), unique=True, nullable=False)
    contraseña = db.Column(db.String(255), nullable=False)  # Se mantiene el nombre
    rol = db.Column(db.Enum('administrador', 'semiadmin', 'vendedor'), nullable=False)

    def __repr__(self):
        return f"<Usuario {self.nombre_usuario}>"

    def set_password(self, password):
        self.contraseña = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.contraseña, password)
