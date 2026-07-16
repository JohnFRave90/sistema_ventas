from sqlalchemy import case
from app.models import Producto

# ── FUENTE DE VERDAD del orden del catálogo del SISTEMA DE VENTAS ──────────────
# El orden NO viene de la columna `Producto.orden` (que está sin poblar / es 0),
# sino de esta lista fija de CÓDIGOS por posición. Es exactamente el orden que
# usan los formularios web (pedidos/extras/devoluciones/despachos) vía
# get_productos_ordenados(): ORDER BY <posición en la lista>, luego nombre.
# Los productos que NO están en la lista van al final (POSICION_FUERA) por nombre.
ORDEN_PRODUCTOS_CODIGOS = [
    '10001', '10003', '10297', '10004', '10041', '10040', '10137', '10251',
    '10238', '10068', '10019', '10058', '10020', '10021', '10059', '10022',
    '10023', '10060', '10092', '10219', '10024', '10291', '10254', '10094',
    '10218', '10061', '10031', '10034', '10296', '10033', '10035', '10192',
    '10193', '10007', '10009', '10133', '10322', '10008', '10010', '10016',
    '10321', '10072', '10069', '10070', '10080', '10079', '10063', '10203',
    '10183', '10082', '10055', '10326', '10002', '10052', '10043', '10073',
    '10086', '10091', '10175', '10202'
]

# Mapa código -> posición (0..N-1). Los que no están → POSICION_FUERA.
POSICION_FUERA = 9999
_ORDEN_INDEX = {codigo: idx for idx, codigo in enumerate(ORDEN_PRODUCTOS_CODIGOS)}


def orden_index(codigo):
    """Posición canónica del producto en el catálogo del sistema de ventas.

    Es el MISMO criterio que get_productos_ordenados (order_by posición, nombre).
    Los productos fuera de la lista devuelven POSICION_FUERA (9999) y se ordenan
    entre sí por nombre.
    """
    return _ORDEN_INDEX.get(str(codigo), POSICION_FUERA)


def get_productos_ordenados():
    orden_case = case(
        *[(Producto.codigo == codigo, idx) for idx, codigo in enumerate(ORDEN_PRODUCTOS_CODIGOS)],
        else_=POSICION_FUERA
    )

    productos = (Producto.query
                 .filter_by(activo=True)
                 .order_by(orden_case, Producto.nombre)
                 .all())

    return productos
