# app/models/ventas.py

from datetime import datetime
from app import db

class BDVenta(db.Model):
    __tablename__ = 'BD_VENTAS'

    id                   = db.Column(db.Integer, primary_key=True)
    consecutivo          = db.Column(db.String(20), unique=True, nullable=False)
    codigo_vendedor      = db.Column(db.String(25), db.ForeignKey('vendedores.codigo_vendedor'), nullable=False)
     
    # Códigos originales de documentos
    codigo_dev_anterior  = db.Column(db.String(20), nullable=True)
    codigo_pedido        = db.Column(db.String(20), nullable=True)
    codigo_extra         = db.Column(db.String(20), nullable=True)
    codigo_dev_dia       = db.Column(db.String(20), nullable=True)

    # Datos numéricos de la venta
    fecha                = db.Column(db.Date,   nullable=False)
    devolucion_anterior  = db.Column(db.Integer, default=0, nullable=False)
    pedido               = db.Column(db.Integer, default=0, nullable=False)
    extras               = db.Column(db.Integer, default=0, nullable=False)
    devolucion_dia       = db.Column(db.Integer, default=0, nullable=False)

    total_venta          = db.Column(db.Float, nullable=False)
    comision             = db.Column(db.Float, nullable=False)
    pagar_pan            = db.Column(db.Float, nullable=False)
    liquidada            = db.Column(db.Boolean, default=False)  

    # Relación a los ítems de la venta
    items                = db.relationship(
                              'BDVentaItem',
                              back_populates='venta',
                              cascade='all, delete-orphan'
                          )

    # Timestamps
    created_at           = db.Column(
                              db.DateTime,
                              server_default=db.func.now(),
                              nullable=False
                           )
    updated_at           = db.Column(
                              db.DateTime,
                              server_default=db.func.now(),
                              onupdate=db.func.now(),
                              nullable=False
                           )

    def __repr__(self):
        return f"<BDVenta {self.consecutivo} ({self.codigo_vendedor})>"
