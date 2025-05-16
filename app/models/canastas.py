from app import db

# Tabla Canastas
class Canasta(db.Model):
    __tablename__ = 'canastas'  # Nombre explícito de la tabla en la base de datos

    codigo_barras = db.Column(db.String(100), primary_key=True, unique=True, nullable=False, comment='Código de barras único de la canasta')
    tamaño = db.Column(db.String(50), nullable=True, comment='Tamaño de la canasta')
    color = db.Column(db.String(50), nullable=True, comment='Color de la canasta')
    estado = db.Column(db.String(50), nullable=True, comment='Estado físico de la canasta: Nuevo o susas')
    fecha_registro = db.Column(db.DateTime, nullable=False, server_default=db.func.now(), comment='Fecha en que fue registrada')
    actualidad = db.Column(db.String(50), nullable=False, default='Disponible', comment='Disponible, Prestada o No disponible')

    # Relación con movimientos
    movimientos = db.relationship('MovimientoCanasta', backref='canasta', lazy=True, primaryjoin="Canasta.codigo_barras==MovimientoCanasta.codigo_barras")

    def __repr__(self):
        return f'<Canasta {self.codigo_barras} - {self.actualidad}>'

# Tabla de movimientos de canastas
class MovimientoCanasta(db.Model):
    __tablename__ = 'movimientos_canastas'

    id = db.Column(db.Integer, primary_key=True)
    codigo_vendedor = db.Column(db.String(50), nullable=False, comment='Código del vendedor que realizó el movimiento')
    tipo_movimiento = db.Column(db.String(20), nullable=False, comment='Entrada o Salida')
    codigo_barras = db.Column(db.String(100), db.ForeignKey('canastas.codigo_barras'), nullable=False, comment='Código de barras de la canasta')
    fecha_movimiento = db.Column(db.DateTime, nullable=False, server_default=db.func.now(), comment='Fecha del movimiento')

    def __repr__(self):
        return f'<Movimiento {self.id} - {self.tipo_movimiento} - {self.codigo_barras}>'
