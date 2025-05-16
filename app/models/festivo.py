# app/models/festivo.py

from app import db

class Festivo(db.Model):
    __tablename__ = 'bd_festivos'
    id     = db.Column(db.Integer, primary_key=True)
    fecha  = db.Column(db.Date, unique=True, nullable=False)
    nota   = db.Column(db.String(100), nullable=True)
