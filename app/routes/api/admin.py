from datetime import datetime, timedelta

from flask import request
from sqlalchemy import func

from app import db
from app.routes.api import api_bp, respuesta_ok, respuesta_error, admin_jwt_required
from app.models.vendedor import Vendedor
from app.models.producto import Producto
from app.models.despachos import BDDespacho, BDDespachoItem
from app.models.devoluciones import BDDevolucion
from app.models.devolucion_item import BDDevolucionItem
from app.models.pedidos import BDPedido
from app.models.pedido_item import BDPedidoItem
from app.services.analitica_service import recolectar_resumen, recolectar_breakdown

RANGO_MAX_DIAS = 92

# Campos de recolectar_resumen que tiene sentido sumar a través de varios días.
CAMPOS_ADITIVOS = (
    'total_vendido', 'clientes_visitados', 'excepciones', 'devoluciones',
    'cambios', 'inventario_despachado', 'inventario_vendido', 'inventario_devuelto',
)


def _parse_fecha(valor):
    if not valor:
        return None
    try:
        return datetime.strptime(valor, '%Y-%m-%d').date()
    except (TypeError, ValueError):
        return None


def _parse_codigos(valor):
    if not valor:
        return None
    return [c.strip() for c in valor.split(',') if c.strip()]


def _validar_rango(desde, hasta):
    if not desde or not hasta:
        return respuesta_error('desde y hasta son requeridos (YYYY-MM-DD)', 400)
    if hasta < desde:
        return respuesta_error('hasta debe ser >= desde', 400)
    return None


def _con_nombres_producto(filas):
    """filas: lista de (producto_cod, cantidad_total). Adjunta el nombre del producto."""
    codigos = [c for c, _ in filas]
    nombres = {}
    if codigos:
        nombres = {p.codigo: p.nombre for p in Producto.query.filter(Producto.codigo.in_(codigos)).all()}
    return [
        {'producto_cod': c, 'nombre': nombres.get(c, c), 'cantidad': int(q or 0)}
        for c, q in filas
    ]


@api_bp.route('/admin/vendedores', methods=['GET'])
@admin_jwt_required
def admin_listar_vendedores():
    """Catálogo de vendedores (código y nombre), para saber qué códigos usar como filtro."""
    vendedores = Vendedor.query.order_by(Vendedor.nombre).all()
    return respuesta_ok([
        {'codigo_vendedor': v.codigo_vendedor, 'nombre': v.nombre}
        for v in vendedores
    ])


@api_bp.route('/admin/analitica/resumen', methods=['GET'])
@admin_jwt_required
def admin_analitica_resumen():
    """Resumen diario. vendedor vacío = agregado de todos los vendedores."""
    fecha = _parse_fecha(request.args.get('fecha'))
    vendedor = (request.args.get('vendedor') or '').strip() or None
    return respuesta_ok(recolectar_resumen(fecha=fecha, vendedor=vendedor))


@api_bp.route('/admin/analitica/breakdown', methods=['GET'])
@admin_jwt_required
def admin_analitica_breakdown():
    """Ranking de ventas por vendedor + top productos vendidos/devueltos de un día."""
    fecha = _parse_fecha(request.args.get('fecha'))
    return respuesta_ok(recolectar_breakdown(fecha=fecha))


@api_bp.route('/admin/analitica/rango', methods=['GET'])
@admin_jwt_required
def admin_analitica_rango():
    """Serie diaria + agregado sobre un rango de fechas (máx. 92 días)."""
    desde = _parse_fecha(request.args.get('desde'))
    hasta = _parse_fecha(request.args.get('hasta'))
    vendedor = (request.args.get('vendedor') or '').strip() or None

    if not desde or not hasta:
        return respuesta_error('desde y hasta son requeridos (YYYY-MM-DD)', 400)
    if hasta < desde:
        return respuesta_error('hasta debe ser >= desde', 400)
    if (hasta - desde).days + 1 > RANGO_MAX_DIAS:
        return respuesta_error(f'rango máximo de {RANGO_MAX_DIAS} días', 400)

    serie = []
    agregado = {campo: 0 for campo in CAMPOS_ADITIVOS}

    dia = desde
    while dia <= hasta:
        resumen = recolectar_resumen(fecha=dia, vendedor=vendedor)
        serie.append(resumen)
        for campo in CAMPOS_ADITIVOS:
            agregado[campo] += resumen[campo]
        dia += timedelta(days=1)

    return respuesta_ok({
        'desde': str(desde),
        'hasta': str(hasta),
        'vendedor': vendedor,
        'serie': serie,
        'agregado': agregado,
    })


@api_bp.route('/admin/despachos/por_producto', methods=['GET'])
@admin_jwt_required
def admin_despachos_por_producto():
    """Unidades despachadas (entregadas a vendedores) por producto en un rango de fechas.

    Refleja lo que los vendedores necesitaron/recibieron para su ruta —
    dato base para programar producción.
    """
    desde = _parse_fecha(request.args.get('desde'))
    hasta = _parse_fecha(request.args.get('hasta'))
    vendedor = (request.args.get('vendedor') or '').strip() or None
    codigos = _parse_codigos(request.args.get('producto_codigos'))

    error = _validar_rango(desde, hasta)
    if error:
        return error

    query = db.session.query(
        BDDespachoItem.producto_cod,
        func.coalesce(func.sum(BDDespachoItem.cantidad), 0),
    ).join(BDDespacho, BDDespacho.id == BDDespachoItem.despacho_id).filter(
        BDDespacho.fecha >= desde, BDDespacho.fecha <= hasta,
    )
    if vendedor:
        query = query.filter(BDDespacho.vendedor_cod == vendedor)
    if codigos:
        query = query.filter(BDDespachoItem.producto_cod.in_(codigos))

    filas = query.group_by(BDDespachoItem.producto_cod).all()
    return respuesta_ok({
        'desde': str(desde), 'hasta': str(hasta), 'vendedor': vendedor,
        'productos': _con_nombres_producto(filas),
    })


@api_bp.route('/admin/devoluciones/por_producto', methods=['GET'])
@admin_jwt_required
def admin_devoluciones_por_producto():
    """Unidades devueltas por producto en un rango de fechas."""
    desde = _parse_fecha(request.args.get('desde'))
    hasta = _parse_fecha(request.args.get('hasta'))
    vendedor = (request.args.get('vendedor') or '').strip() or None
    codigos = _parse_codigos(request.args.get('producto_codigos'))

    error = _validar_rango(desde, hasta)
    if error:
        return error

    query = db.session.query(
        BDDevolucionItem.producto_cod,
        func.coalesce(func.sum(BDDevolucionItem.cantidad), 0),
    ).join(BDDevolucion, BDDevolucion.id == BDDevolucionItem.devolucion_id).filter(
        BDDevolucion.fecha >= desde, BDDevolucion.fecha <= hasta,
    )
    if vendedor:
        query = query.filter(BDDevolucion.codigo_vendedor == vendedor)
    if codigos:
        query = query.filter(BDDevolucionItem.producto_cod.in_(codigos))

    filas = query.group_by(BDDevolucionItem.producto_cod).all()
    return respuesta_ok({
        'desde': str(desde), 'hasta': str(hasta), 'vendedor': vendedor,
        'productos': _con_nombres_producto(filas),
    })


@api_bp.route('/admin/pedidos/por_producto', methods=['GET'])
@admin_jwt_required
def admin_pedidos_por_producto():
    """Unidades en pedidos anticipados (preventa de clientes) por producto en un rango de fechas.

    No representa lo que un vendedor necesita para su ruta diaria — es la
    demanda puntual de clientes específicos registrada por los vendedores.
    """
    desde = _parse_fecha(request.args.get('desde'))
    hasta = _parse_fecha(request.args.get('hasta'))
    vendedor = (request.args.get('vendedor') or '').strip() or None
    codigos = _parse_codigos(request.args.get('producto_codigos'))

    error = _validar_rango(desde, hasta)
    if error:
        return error

    query = db.session.query(
        BDPedidoItem.producto_cod,
        func.coalesce(func.sum(BDPedidoItem.cantidad), 0),
    ).join(BDPedido, BDPedido.id == BDPedidoItem.pedido_id).filter(
        BDPedido.fecha >= desde, BDPedido.fecha <= hasta,
    )
    if vendedor:
        query = query.filter(BDPedido.codigo_vendedor == vendedor)
    if codigos:
        query = query.filter(BDPedidoItem.producto_cod.in_(codigos))

    filas = query.group_by(BDPedidoItem.producto_cod).all()
    return respuesta_ok({
        'desde': str(desde), 'hasta': str(hasta), 'vendedor': vendedor,
        'productos': _con_nombres_producto(filas),
    })
