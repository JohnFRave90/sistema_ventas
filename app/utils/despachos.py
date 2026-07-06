# app/utils/despachos.py
"""Lógica pura (sin Flask/DB) de despachos: estado derivado y diferencias.

No se agrega columna de estado a la BD (regla: no modificar el esquema sin
justificar). En su lugar el estado se DERIVA de campos reales (``despachado`` y
el estado del turno asociado). Un state-machine completo
(borrador/preparado/confirmado/cargado_en_app/en_ruta/cerrado/anulado) requeriría
una migración (``BD_DESPACHOS.estado``); se deja documentado para más adelante.
"""

CATEGORIA_DEFECTO = 'Sin categoria'

# Estados derivables hoy a partir de datos reales (subconjunto del spec).
ESTADO_BORRADOR = 'borrador'
ESTADO_PREPARADO = 'preparado'
ESTADO_EN_RUTA = 'en_ruta'
ESTADO_CERRADO = 'cerrado'


def derivar_estado_despacho(despachado, turno_estado=None):
    """Deriva un estado legible del despacho a partir de campos existentes.

    :param despachado: bool ``BDDespacho.despachado``.
    :param turno_estado: ``'abierto'`` / ``'cerrado'`` / ``None`` del turno asociado.

    - no despachado            -> 'borrador'
    - despachado, sin turno     -> 'preparado'
    - despachado, turno abierto -> 'en_ruta'
    - despachado, turno cerrado -> 'cerrado'
    """
    if not despachado:
        return ESTADO_BORRADOR
    if turno_estado == 'cerrado':
        return ESTADO_CERRADO
    if turno_estado == 'abierto':
        return ESTADO_EN_RUTA
    return ESTADO_PREPARADO


def calcular_diferencias_despacho(
    despacho_sistema_map,
    confirmada_app_map,
    vendida_map,
    devuelta_map,
    productos_map=None,
):
    """Cruza, por ``producto_cod``, lo despachado por el sistema contra lo que el
    vendedor confirmó en la app, lo vendido y lo devuelto.

    Fórmulas (validadas con el ejemplo del cliente 20/18/10/3 → sobrante 5, dif -2):

        sobrante_estimado = confirmada_app - vendida - devuelta
        diferencia        = confirmada_app - despacho_sistema

    :returns: dict con ``items`` (lista ordenada por producto_cod) y ``totales``.
    """
    despacho_sistema_map = despacho_sistema_map or {}
    confirmada_app_map = confirmada_app_map or {}
    vendida_map = vendida_map or {}
    devuelta_map = devuelta_map or {}
    productos_map = productos_map or {}

    codigos = (
        set(despacho_sistema_map)
        | set(confirmada_app_map)
        | set(vendida_map)
        | set(devuelta_map)
    )

    items = []
    totales = {
        'despacho_sistema': 0,
        'confirmada_app': 0,
        'vendida': 0,
        'devuelta': 0,
        'sobrante_estimado': 0,
        'diferencia': 0,
    }

    for codigo in sorted(codigos):
        despacho_sistema = int(despacho_sistema_map.get(codigo, 0) or 0)
        confirmada_app = int(confirmada_app_map.get(codigo, 0) or 0)
        vendida = int(vendida_map.get(codigo, 0) or 0)
        devuelta = int(devuelta_map.get(codigo, 0) or 0)
        sobrante_estimado = confirmada_app - vendida - devuelta
        diferencia = confirmada_app - despacho_sistema

        producto = productos_map.get(codigo)
        nombre = getattr(producto, 'nombre', None) or codigo

        items.append({
            'producto_cod': codigo,
            'nombre': nombre,
            'cantidad_despacho_sistema': despacho_sistema,
            'cantidad_confirmada_app': confirmada_app,
            'cantidad_vendida': vendida,
            'cantidad_devuelta': devuelta,
            'sobrante_estimado': sobrante_estimado,
            'diferencia': diferencia,
        })

        totales['despacho_sistema'] += despacho_sistema
        totales['confirmada_app'] += confirmada_app
        totales['vendida'] += vendida
        totales['devuelta'] += devuelta
        totales['sobrante_estimado'] += sobrante_estimado
        totales['diferencia'] += diferencia

    return {'items': items, 'totales': totales}
