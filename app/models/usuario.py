# app/models/usuario.py

from app import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

class Usuario(db.Model, UserMixin):
    __tablename__ = 'usuarios'

    id = db.Column(db.Integer, primary_key=True)
    nombre_usuario = db.Column(db.String(100), unique=True, nullable=False)
    contraseña = db.Column(db.String(255), nullable=False)
    rol = db.Column(db.Enum('administrador', 'semiadmin', 'vendedor'), nullable=False)
    
    # --- NUEVOS CAMPOS ---
    pin = db.Column(db.String(255), nullable=True) # PIN para autenticación por voz
    voice_id = db.Column(db.String(255), nullable=True, unique=True) # ID de Voice Match

    def __repr__(self):
        return f"<Usuario {self.nombre_usuario}>"

    def set_password(self, password):
        self.contraseña = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.contraseña, password)

    # --- NUEVOS MÉTODOS PARA EL PIN ---
    def set_pin(self, pin_code):
        self.pin = generate_password_hash(pin_code)

    def check_pin(self, pin_code):
        return check_password_hash(self.pin, pin_code)