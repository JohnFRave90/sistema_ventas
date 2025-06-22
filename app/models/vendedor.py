# app/models/vendedor.py

from app import db
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin

class Vendedor(db.Model, UserMixin):
    __tablename__ = 'vendedores'

    id = db.Column(db.Integer, primary_key=True)
    codigo_vendedor = db.Column(db.String(25), unique=True, nullable=False) # CORREGIDO
    nombre = db.Column(db.String(100), nullable=False)
    nombre_usuario = db.Column(db.String(50), unique=True, nullable=False)
    contraseña = db.Column(db.String(200), nullable=False)
    rol = db.Column(db.String(20), default='vendedor')
    comision_panaderia = db.Column(db.Float, default=0.0)
    comision_bizcocheria = db.Column(db.Float, default=0.0)

    def set_password(self, password):
        self.contraseña = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.contraseña, password)
 


        
    
