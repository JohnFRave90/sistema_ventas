from app import db


class BDVisitaCliente(db.Model):
    __tablename__ = 'bd_visitas_clientes'

    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey('clientes.id'), nullable=False)
    codigo_vendedor = db.Column(
        db.String(25),
        db.ForeignKey('vendedores.codigo_vendedor'),
        nullable=False,
    )
    turno_id = db.Column(db.Integer, db.ForeignKey('bd_turnos.id'), nullable=True)
    fecha_visita = db.Column(db.Date, nullable=False)
    checkin_at = db.Column(db.DateTime, nullable=False, server_default=db.func.now())
    checkout_at = db.Column(db.DateTime, nullable=True)
    estado = db.Column(db.String(20), nullable=False, default='en_progreso')
    notas = db.Column(db.Text, nullable=True)
    lat_checkin = db.Column(db.Numeric(10, 8), nullable=True)
    lng_checkin = db.Column(db.Numeric(11, 8), nullable=True)
    lat_checkout = db.Column(db.Numeric(10, 8), nullable=True)
    lng_checkout = db.Column(db.Numeric(11, 8), nullable=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)
    updated_at = db.Column(
        db.DateTime,
        server_default=db.func.now(),
        onupdate=db.func.now(),
        nullable=False,
    )

    __table_args__ = (
        db.Index('idx_bd_visitas_cliente_fecha', 'cliente_id', 'fecha_visita'),
        db.Index('idx_bd_visitas_vendedor_fecha', 'codigo_vendedor', 'fecha_visita'),
        db.Index('idx_bd_visitas_estado', 'estado'),
        db.Index('idx_bd_visitas_turno', 'turno_id'),
    )

    cliente = db.relationship('Cliente')
    vendedor = db.relationship('Vendedor')
    turno = db.relationship('BDTurno')
    excepciones = db.relationship(
        'BDVisitaExcepcion',
        back_populates='visita',
        cascade='all, delete-orphan',
    )


class BDVisitaExcepcion(db.Model):
    __tablename__ = 'bd_visitas_excepciones'

    id = db.Column(db.Integer, primary_key=True)
    visita_id = db.Column(db.Integer, db.ForeignKey('bd_visitas_clientes.id'), nullable=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey('clientes.id'), nullable=False)
    codigo_vendedor = db.Column(
        db.String(25),
        db.ForeignKey('vendedores.codigo_vendedor'),
        nullable=False,
    )
    tipo = db.Column(db.String(40), nullable=False, default='otro')
    razon = db.Column(db.Text, nullable=False)
    requiere_seguimiento = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)

    __table_args__ = (
        db.Index('idx_bd_visita_ex_cliente_fecha', 'cliente_id', 'created_at'),
        db.Index('idx_bd_visita_ex_vendedor_fecha', 'codigo_vendedor', 'created_at'),
    )

    visita = db.relationship('BDVisitaCliente', back_populates='excepciones')
    cliente = db.relationship('Cliente')
    vendedor = db.relationship('Vendedor')
