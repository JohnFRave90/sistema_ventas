# app/utils/analitica.py
"""Aritmética pura (sin Flask/DB) de la analítica de inventario.

Fórmula de negocio (coherente con el inventario automático de la app):

    inventario_inicial   = despachado + devolucion_anterior
    restante_estimado    = inicial - vendido - cambios_entregados + devoluciones_recibidas

Se mantiene pura para poder testearla sin levantar la aplicación.
"""


def calcular_metricas_inventario(
    despachado,
    vendido,
    devuelto,
    devolucion_anterior=0,
    cambios_entregados=0,
):
    """Devuelve el desglose de inventario para la analítica.

    :param despachado: unidades despachadas por el sistema en la fecha.
    :param vendido: unidades vendidas (items de autoventa).
    :param devuelto: unidades devueltas en el día (devoluciones recibidas).
    :param devolucion_anterior: sobrante del turno anterior (default 0 a nivel agregado).
    :param cambios_entregados: unidades entregadas por cambios. ``BD_CAMBIO`` solo
        guarda valor monetario (sin granularidad por producto), por lo que a nivel
        agregado se pasa 0; se deja el parámetro para cuando exista el dato.
    """
    despachado = int(despachado or 0)
    vendido = int(vendido or 0)
    devuelto = int(devuelto or 0)
    devolucion_anterior = int(devolucion_anterior or 0)
    cambios_entregados = int(cambios_entregados or 0)

    inicial = despachado + devolucion_anterior
    restante_estimado = inicial - vendido - cambios_entregados + devuelto

    return {
        'despachado': despachado,
        'devolucion_anterior': devolucion_anterior,
        'inicial': inicial,
        'vendido': vendido,
        'cambios_entregados': cambios_entregados,
        'devuelto': devuelto,
        'restante_estimado': restante_estimado,
    }
