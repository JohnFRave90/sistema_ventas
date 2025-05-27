# app/utils/documentos.py
from sqlalchemy import func

def generar_consecutivo(model, prefix):
    """
    Devuelve un consecutivo tipo PREFIX-0001, basado en el último id de model.
    Uso: generar_consecutivo(BDPedido, 'PD'), generar_consecutivo(BDExtra, 'EX'), etc.
    """
    ultimo = model.query.order_by(model.id.desc()).first()
    n = (ultimo.id + 1) if ultimo else 1
    return f"{prefix}-{n:05d}"
