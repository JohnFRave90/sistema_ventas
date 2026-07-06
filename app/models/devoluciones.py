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
    # Discrimina el tipo de devolución:
    #   'vendedor' — producto que el vendedor devuelve al almacén al cerrar ruta (default legacy)
    #   'cliente'  — producto que un cliente devuelve (nota crédito)
    # Los cambios (intercambios) se registran en BDCambio/BDCambioItem, NO aquí.
    tipo_devolucion  = db.Column(db.Enum('vendedor', 'cliente'), nullable=False, default='vendedor')
    comentarios      = db.Column(db.Text, nullable=True)
    usos             = db.Column(db.Integer, nullable=False, default=0)
    # Flag PROPIO de la app (independiente de `usos`, que es contador del WEB):
    #   0 = sobrante pendiente de sumarse a un cargue inicial.
    #   1 = ya consumido por un cargue (no se vuelve a sumar).
    # La app NUNCA escribe `usos`; el web NUNCA escribe `consumida_app`.
    consumida_app    = db.Column(db.Integer, nullable=False, default=0)
    # Idempotencia para sincronización offline (evita devoluciones duplicadas al reintentar).
    uuid_origen      = db.Column(db.String(36), unique=True, nullable=True)

    items            = db.relationship(
                          'BDDevolucionItem',
                          back_populates='devolucion',
                          cascade='all, delete-orphan'
                       )