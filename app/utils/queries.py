from app.models.vendedor import Vendedor


def obtener_mapa_vendedores():
    """
    Retorna un diccionario {codigo_vendedor: nombre} con todos los vendedores.
    Usado para mostrar nombres de vendedores en listados y reportes.
    """
    return {v.codigo_vendedor: v.nombre for v in Vendedor.query.all()}


def obtener_mapa_vendedores_obj():
    """
    Retorna un diccionario {codigo_vendedor: Vendedor} con todos los vendedores.
    Usado cuando se necesita acceder a campos completos del vendedor (comisiones, etc.)
    para evitar consultas N+1 en loops.
    """
    return {v.codigo_vendedor: v for v in Vendedor.query.all()}
