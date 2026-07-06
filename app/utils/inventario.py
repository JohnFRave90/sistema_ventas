# app/utils/inventario.py
"""Cálculo del inventario inicial de la app.

Regla de negocio (cliente): el inventario inicial que ve el vendedor NO es todo
el catálogo, sino lo que realmente carga para la jornada:

    inventario_inicial(producto) = cantidad_despachada + cantidad_devolucion_anterior

Es decir, el despacho del día MÁS el sobrante/devolución del turno anterior.
Solo se incluyen productos con cantidad_inicial > 0 (nunca el catálogo completo).

Esta función es pura (sin dependencias de Flask/DB) para poder testearla sin
levantar la aplicación.
"""

UNIDAD_DEFECTO = 'UND'
CATEGORIA_DEFECTO = 'Sin categoria'


def calcular_devolucion_anterior_map(devoluciones, turno_cerrado_id=None):
    """Consolida el sobrante/devolución del turno anterior por ``producto_cod``.

    Regla de negocio (refinada): la devolución anterior debe provenir del **último
    turno cerrado** del mismo vendedor, no de "cualquier devolución con usos=0".

    :param devoluciones: iterable de devoluciones del vendedor. Cada una expone
        ``turno_id``, ``usos`` e ``items`` (con ``producto_cod`` y ``cantidad``).
        Se asume ordenado de más reciente a más antiguo para el fallback.
    :param turno_cerrado_id: id del último turno cerrado anterior, o ``None`` si no
        se pudo determinar.
    :returns: ``{producto_cod: cantidad}`` consolidado.

    Estrategia:
      1. Si hay ``turno_cerrado_id``: se toman SOLO las devoluciones ligadas a ese
         turno (``turno_id == turno_cerrado_id``) y se consolidan. Esto evita
         mezclar turnos y respeta el aislamiento por turno/vendedor.
      2. Si no se determinó turno o ninguna devolución quedó ligada por ``turno_id``
         (datos antiguos sin asociación), se cae al comportamiento previo: la
         devolución más reciente con ``usos == 0``. Así no se regresa la cobertura.
    """
    devoluciones = list(devoluciones or [])

    if turno_cerrado_id is not None:
        ligadas = [d for d in devoluciones if getattr(d, 'turno_id', None) == turno_cerrado_id]
        if ligadas:
            return _consolidar_items(ligadas)

    # Fallback: primera (más reciente) devolución sin usar.
    for dev in devoluciones:
        if int(getattr(dev, 'usos', 0) or 0) == 0:
            return _consolidar_items([dev])

    return {}


def _consolidar_items(devoluciones):
    acumulado = {}
    for dev in devoluciones:
        for item in getattr(dev, 'items', []) or []:
            cod = item.producto_cod
            acumulado[cod] = acumulado.get(cod, 0) + int(getattr(item, 'cantidad', 0) or 0)
    return acumulado


def calcular_inventario_inicial(despacho_map, devolucion_map, productos_map):
    """Unifica despacho + devolución anterior por ``producto_cod``.

    :param despacho_map: ``{producto_cod: cantidad_despachada}``
    :param devolucion_map: ``{producto_cod: cantidad_devuelta_anterior}``
    :param productos_map: ``{producto_cod: Producto}`` (para nombre/categoria/precio).
        Puede no contener todos los códigos; los faltantes usan valores por defecto.
    :returns: lista de dicts ordenada por ``producto_cod`` con la forma del API.

    Reglas:
      - Producto solo en despacho: se incluye.
      - Producto solo en devolución: se incluye.
      - Producto en ambos: se suman las cantidades.
      - cantidad_inicial <= 0: se omite (no se trae el catálogo completo).
      - Sin devolución anterior para un producto: su aporte es 0.
    """
    codigos = set(despacho_map or {}) | set(devolucion_map or {})
    items = []

    for codigo in sorted(codigos):
        cantidad_despacho = int((despacho_map or {}).get(codigo, 0) or 0)
        cantidad_devolucion = int((devolucion_map or {}).get(codigo, 0) or 0)
        cantidad_inicial = cantidad_despacho + cantidad_devolucion

        if cantidad_inicial <= 0:
            continue

        producto = (productos_map or {}).get(codigo)
        nombre = getattr(producto, 'nombre', None) or codigo
        categoria = getattr(producto, 'categoria', None) or CATEGORIA_DEFECTO
        precio_attr = getattr(producto, 'precio', None)
        precio = float(precio_attr) if precio_attr is not None else 0.0

        items.append({
            'producto_cod': codigo,
            'nombre': nombre,
            'categoria': categoria,
            'precio': precio,
            'cantidad_despacho': cantidad_despacho,
            'cantidad_devolucion_anterior': cantidad_devolucion,
            'cantidad_inicial': cantidad_inicial,
            # Al cargar la jornada disponible == inicial (aún no hay ventas).
            'cantidad_disponible': cantidad_inicial,
            'unidad': UNIDAD_DEFECTO,
        })

    return items
