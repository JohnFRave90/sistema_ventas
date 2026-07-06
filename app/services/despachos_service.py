# app/services/despachos_service.py
"""Recolección de datos para diferencias de despacho (capa con acceso a BD).

La aritmética vive en ``app.utils.despachos`` (pura/testeable). Aquí solo se
arman los mapas ``{producto_cod: cantidad}`` desde la BD y se delega el cálculo,
para que web y API compartan exactamente la misma lógica sin duplicar.
"""

from app.models.despachos import BDDespacho
from app.models.ventas import BDVenta
from app.models.venta_item import BDVentaItem
from app.models.devoluciones import BDDevolucion
from app.models.producto import Producto
from app.models.turno import BDTurno
from app.utils.despachos import calcular_diferencias_despacho, derivar_estado_despacho

PRE_TURNO_TIPO_ORIGEN = 'PREAPP'


def estado_de_despacho(despacho):
    """Estado derivado del despacho (consulta el turno asociado si existe)."""
    turno_estado = None
    if despacho.turno_id:
        turno = BDTurno.query.get(despacho.turno_id)
        turno_estado = turno.estado if turno else None
    return derivar_estado_despacho(bool(despacho.despachado), turno_estado)


def _map_items_despacho(despacho):
    acumulado = {}
    for item in despacho.items:
        acumulado[item.producto_cod] = acumulado.get(item.producto_cod, 0) + int(item.cantidad or 0)
    return acumulado


def _confirmada_app_map(vendedor_cod, fecha):
    """Lo que el vendedor confirmó cargar en la app = despacho PREAPP de ese día."""
    preapp = BDDespacho.query.filter_by(
        vendedor_cod=vendedor_cod,
        fecha=fecha,
        tipo_origen=PRE_TURNO_TIPO_ORIGEN,
    ).order_by(BDDespacho.id.desc()).first()
    return _map_items_despacho(preapp) if preapp else {}


def _vendida_map(vendedor_cod, fecha):
    """Cantidad vendida por producto (suma de items de las ventas del día)."""
    ventas = BDVenta.query.filter_by(codigo_vendedor=vendedor_cod, fecha=fecha).all()
    if not ventas:
        return {}
    venta_ids = [v.id for v in ventas]
    items = BDVentaItem.query.filter(BDVentaItem.venta_id.in_(venta_ids)).all()
    acumulado = {}
    for item in items:
        acumulado[item.producto_cod] = acumulado.get(item.producto_cod, 0) + int(item.cantidad or 0)
    return acumulado


def _devuelta_map(vendedor_cod, fecha):
    """Devolución del día por producto (devoluciones registradas en esa fecha)."""
    devoluciones = BDDevolucion.query.filter_by(
        codigo_vendedor=vendedor_cod, fecha=fecha
    ).all()
    acumulado = {}
    for dev in devoluciones:
        for item in dev.items:
            acumulado[item.producto_cod] = acumulado.get(item.producto_cod, 0) + int(item.cantidad or 0)
    return acumulado


def recolectar_diferencias(despacho):
    """Arma los mapas desde BD y devuelve el resultado de diferencias + contexto."""
    vendedor_cod = despacho.vendedor_cod
    fecha = despacho.fecha

    despacho_sistema_map = _map_items_despacho(despacho)
    confirmada_app_map = _confirmada_app_map(vendedor_cod, fecha)
    vendida_map = _vendida_map(vendedor_cod, fecha)
    devuelta_map = _devuelta_map(vendedor_cod, fecha)

    codigos = (
        set(despacho_sistema_map)
        | set(confirmada_app_map)
        | set(vendida_map)
        | set(devuelta_map)
    )
    productos = Producto.query.filter(Producto.codigo.in_(list(codigos))).all() if codigos else []
    productos_map = {p.codigo: p for p in productos}

    resultado = calcular_diferencias_despacho(
        despacho_sistema_map,
        confirmada_app_map,
        vendida_map,
        devuelta_map,
        productos_map,
    )

    return {
        'despacho_id': despacho.id,
        'codigo_origen': despacho.codigo_origen,
        'codigo_vendedor': vendedor_cod,
        'fecha': str(fecha),
        'estado': estado_de_despacho(despacho),
        'items': resultado['items'],
        'totales': resultado['totales'],
    }
