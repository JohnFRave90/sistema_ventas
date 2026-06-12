from app import db


class BDTurnoUbicacion(db.Model):
    __tablename__ = 'bd_turnos_ubicaciones'

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    codigo_vendedor = db.Column(
        db.String(25),
        db.ForeignKey('vendedores.codigo_vendedor'),
        nullable=False,
    )
    turno_id = db.Column(db.Integer, db.ForeignKey('bd_turnos.id'), nullable=True)
    latitud = db.Column(db.Numeric(10, 8), nullable=False)
    longitud = db.Column(db.Numeric(11, 8), nullable=False)
    precision_m = db.Column(db.Numeric(8, 2), nullable=True)
    velocidad_mps = db.Column(db.Numeric(8, 3), nullable=True)
    rumbo_grados = db.Column(db.Numeric(6, 2), nullable=True)
    fuente = db.Column(db.String(20), nullable=False, default='background')
    captured_at = db.Column(db.DateTime, nullable=False, server_default=db.func.now())
    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)

    __table_args__ = (
        db.Index('idx_turno_ubicaciones_vendedor_fecha', 'codigo_vendedor', 'captured_at'),
        db.Index('idx_turno_ubicaciones_turno_fecha', 'turno_id', 'captured_at'),
    )

    vendedor = db.relationship('Vendedor')
    turno = db.relationship('BDTurno')
