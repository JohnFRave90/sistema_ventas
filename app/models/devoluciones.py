# app/models/devoluciones.py

from app import db

class BDDevolucion(db.Model):
    __tablename__ = 'BD_DEVOLUCIONES'

    id               = db.Column(db.Integer, primary_key=True)
    consecutivo      = db.Column(db.String(20), unique=True, nullable=False)
    codigo_vendedor  = db.Column(db.String(25), db.ForeignKey('vendedores.codigo_vendedor'), nullable=False) # CORREGIDO
    fecha            = db.Column(db.Date, nullable=False)
    # Turno al que pertenece la devolución (para que el resumen del turno cuadre).
    turno_id         = db.Column(db.Integer, db.ForeignKey('bd_turnos.id'), nullable=True)
    comentarios      = db.Column(db.Text, nullable=True)
    usos             = db.Column(db.Integer, nullable=False, default=0)
    # Idempotencia para sincronización offline (evita devoluciones duplicadas al reintentar).
    uuid_origen      = db.Column(db.String(36), unique=True, nullable=True)

    items            = db.relationship(
                          'BDDevolucionItem',
                          back_populates='devolucion',
                          cascade='all, delete-orphan'
                       )