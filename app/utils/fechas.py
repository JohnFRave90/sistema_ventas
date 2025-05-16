# app/utils/fechas.py

from datetime import date, timedelta
import calendar
from app.models.festivo import Festivo
from app import db
import holidays

def es_festivo(d: date) -> bool:
    """Comprueba si d está en la tabla Festivo."""
    return db.session.query(Festivo).filter_by(fecha=d).first() is not None

def rango_fechas(start: date, end: date):
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)

def contar_habiles(start: date, end: date) -> int:
    """
    Cuenta lunes–sábado excluyendo festivos.
    Ahora weekday()<6 incluye sábados (0 = lunes, …, 5 = sábado).
    """
    cnt = 0
    for d in rango_fechas(start, end):
        if d.weekday() < 6 and not es_festivo(d):
            cnt += 1
    return cnt

def dias_habiles_mes(year: int, month: int) -> int:
    """Días hábiles totales de un mes (lunes–sábado), excluyendo festivos."""
    first = date(year, month, 1)
    last  = date(year, month, calendar.monthrange(year, month)[1])
    return contar_habiles(first, last)

def sync_festivos_oficiales(years):
    """
    Sincroniza tu tabla Festivo con los festivos oficiales de Colombia
    usando la librería `holidays`. Llama a esta función al inicio del año
    o periódicamente.
    """
    co_hols = holidays.Colombia(years=years)
    for d, name in co_hols.items():
        if not Festivo.query.filter_by(fecha=d).first():
            db.session.add(Festivo(fecha=d, nota=name))
    db.session.commit()
