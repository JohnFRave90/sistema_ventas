from app import db


class BDTurno(db.Model):
    __tablename__ = 'bd_turnos'

    id = db.Column(db.Integer, primary_key=True)
    codigo_vendedor = db.Column(
        db.String(25),
        db.ForeignKey('vendedores.codigo_vendedor'),
        nullable=False,
    )
    fecha = db.Column(db.Date, nullable=False)
    turno_numero = db.Column(db.Integer, nullable=False, default=1)
    hora_inicio = db.Column(db.Time, nullable=False)
    hora_fin = db.Column(db.Time, nullable=True)
    estado = db.Column(db.String(12), nullable=False, default='abierto')
    comentarios = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)
    updated_at = db.Column(
        db.DateTime,
        server_default=db.func.now(),
        onupdate=db.func.now(),
        nullable=False,
    )

    __table_args__ = (
        db.UniqueConstraint(
            'codigo_vendedor',
            'fecha',
            'turno_numero',
            name='uq_bd_turnos_vendedor_fecha_numero',
        ),
        db.Index('idx_bd_turnos_vendedor_fecha', 'codigo_vendedor', 'fecha'),
        db.Index('idx_bd_turnos_estado', 'estado'),
    )

    vendedor = db.relationship('Vendedor')
