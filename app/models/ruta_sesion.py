from app import db


class BDRutaSesion(db.Model):
    __tablename__ = 'bd_rutas_sesiones'

    id = db.Column(db.Integer, primary_key=True)
    codigo_vendedor = db.Column(
        db.String(25),
        db.ForeignKey('vendedores.codigo_vendedor'),
        nullable=False,
    )
    ruta_nombre = db.Column(db.String(50), nullable=False)
    clientes_cargados = db.Column(db.Integer, nullable=False, default=0)
    estado = db.Column(db.String(12), nullable=False, default='activa')
    started_at = db.Column(db.DateTime, nullable=False, server_default=db.func.now())
    ended_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)
    updated_at = db.Column(
        db.DateTime,
        server_default=db.func.now(),
        onupdate=db.func.now(),
        nullable=False,
    )

    __table_args__ = (
        db.Index('idx_bd_rutas_sesiones_vendedor_estado', 'codigo_vendedor', 'estado'),
        db.Index('idx_bd_rutas_sesiones_vendedor_started', 'codigo_vendedor', 'started_at'),
    )

    vendedor = db.relationship('Vendedor')
