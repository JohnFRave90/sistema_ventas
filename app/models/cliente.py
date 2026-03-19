# app/models/cliente.py

from app import db
from app.utils.documentos import generar_consecutivo

class Cliente(db.Model):
    __tablename__ = 'clientes'

    id             = db.Column(db.Integer, primary_key=True)
    codigo_cliente = db.Column(db.String(20), unique=True, nullable=False)
    nombre         = db.Column(db.String(100), nullable=False)
    telefono       = db.Column(db.String(20))
    whatsapp       = db.Column(db.String(20))
    direccion      = db.Column(db.String(200))
    ciudad         = db.Column(db.String(100))
    latitud        = db.Column(db.Numeric(10, 8))
    longitud       = db.Column(db.Numeric(11, 8))
    ruta           = db.Column(db.String(50))
    orden_visita   = db.Column(db.Integer)
    codigo_vendedor = db.Column(
        db.String(25),
        db.ForeignKey('vendedores.codigo_vendedor'),
        nullable=False
    )
    activo         = db.Column(db.Boolean, default=True, nullable=False)
    created_at     = db.Column(db.DateTime, server_default=db.func.now())

    ventas         = db.relationship('BDVentaAutoventa', back_populates='cliente')

    @staticmethod
    def siguiente_codigo():
        return generar_consecutivo(Cliente, 'CL')
