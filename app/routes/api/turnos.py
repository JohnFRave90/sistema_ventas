from datetime import date, datetime
from typing import Optional

from flask import current_app, request
from flask_jwt_extended import get_jwt_identity, jwt_required
from sqlalchemy import and_, case, func, or_

from app import db
from app.models.cambio import BDCambio, BDCambioItem
from app.models.despachos import BDDespacho, BDDespachoItem
from app.models.devolucion_item import BDDevolucionItem
from app.models.devoluciones import BDDevolucion
from app.models.pedido_item import BDPedidoItem
from app.models.pedidos import BDPedido
from app.models.producto import Producto
from app.models.turno import BDTurno
from app.models.venta_autoventa import BDVentaAutoventa, BDVentaAutoventaItem
from app.models.visita_cliente import BDVisitaCliente
from app.routes.api import api_bp, respuesta_error, respuesta_ok


def _parse_date(value: Optional[str]) -> date:
    if not value:
        return date.today()
    return date.fromisoformat(value)


def _parse_time(value: Optional[str], default_now: bool = True):
    if value:
        return datetime.strptime(value, '%H:%M:%S').time() if len(value) == 8 else datetime.strptime(value, '%H:%M').time()
    if default_now:
        return datetime.now().time().replace(microsecond=0)
    return None


def _serializar_turno(turno: BDTurno):
    return {
        'id': turno.id,
        'codigo_vendedor': turno.codigo_vendedor,
        'fecha': str(turno.fecha),
        'turno_numero': turno.turno_numero,
        'hora_inicio': str(turno.hora_inicio) if turno.hora_inicio else None,
        'hora_fin': str(turno.hora_fin) if turno.hora_fin else None,
        'estado': turno.estado,
        'modo': turno.modo,
        'comentarios': turno.comentarios,
    }


def _obtener_turno_referencia(codigo_vendedor: str) -> Optional[BDTurno]:
    hoy = date.today()
    turno_hoy = BDTurno.query.filter_by(
        codigo_vendedor=codigo_vendedor,
        fecha=hoy,
    ).order_by(BDTurno.id.desc()).first()
    if turno_hoy:
        return turno_hoy

    return BDTurno.query.filter_by(codigo_vendedor=codigo_vendedor).order_by(BDTurno.id.desc()).first()


def _filtro_turno_o_fecha(turno: BDTurno, turno_col, fecha_col, incluir_null_fecha: bool = True):
    """Filtro de atribución de un registro a un turno.

    Siempre incluye lo ligado por ``turno_id``. Además, cuando ``incluir_null_fecha``
    es True, incluye los registros con ``turno_id`` NULL de la MISMA fecha (creados
    offline antes de resolver el turno). Ese fallback por fecha SOLO debe activarse
    para UN turno por (vendedor, fecha) — el turno primario — para no atribuir la
    misma venta a todos los turnos del día (ver ``_es_turno_primario_de_fecha``).
    """
    if not incluir_null_fecha:
        return turno_col == turno.id
    return or_(
        turno_col == turno.id,
        and_(turno_col.is_(None), fecha_col == turno.fecha),
    )


def _es_turno_primario_de_fecha(turno: BDTurno) -> bool:
    """True si ``turno`` es el turno primario de su fecha para el vendedor.

    Primario = el de mayor id (el más reciente) entre los turnos del vendedor en esa
    fecha. Las ventas con ``turno_id`` NULL de esa fecha se atribuyen SOLO a él, de
    forma determinista, para que una venta NUNCA cuente en varios turnos del mismo día.
    """
    max_id = db.session.query(func.max(BDTurno.id)).filter(
        BDTurno.codigo_vendedor == turno.codigo_vendedor,
        BDTurno.fecha == turno.fecha,
    ).scalar()
    return max_id == turno.id


def _resolver_sales_mode(turno: BDTurno) -> str:
    """Modo del turno para agregar la fuente correcta (ventas vs pedidos).

    Autoridad DURABLE = ``turno.modo`` (persistido al iniciar el turno). Si es NULL
    (turno legado), se acepta el hint ``sales_mode`` del app (el modo ligado al turno
    en el dispositivo) y, en último caso, se asume ``autoventa`` por compatibilidad.
    NUNCA se infiere el modo de si existen ventas o pedidos.
    """
    if turno.modo in ('autoventa', 'preventa'):
        return turno.modo
    hint = (request.args.get('sales_mode') or '').strip()
    if hint in ('autoventa', 'preventa'):
        return hint
    return 'autoventa'


def _resumen_comercial_preventa(codigo_vendedor: str, turno: BDTurno):
    """Agrega el bloque comercial de un turno de PREVENTA desde ``bd_pedidos``.

    Devuelve las MISMAS claves que el bloque de autoventa (para reutilizar el mismo
    adaptador en el app), pero calculadas sobre pedidos del turno EXACTO, excluyendo
    los cancelados. El total de un pedido = suma de subtotales de sus ítems (BDPedido
    no guarda total). Los montos de pago son el pago PACTADO al tomar el pedido
    (el app los etiqueta como "esperado"); mismo reparto de mixto que autoventa, con
    el invariante efectivo + transferencia = total.
    """
    pedido_filter = (
        BDPedido.codigo_vendedor == codigo_vendedor,
        BDPedido.turno_id == turno.id,
        BDPedido.estado != 'cancelado',
    )

    # Total y desglose de pago por pedido (N pequeño → se agrega en Python, decimal-safe).
    pago_rows = db.session.query(
        BDPedido.id,
        BDPedido.metodo_pago,
        BDPedido.monto_efectivo,
        func.coalesce(func.sum(BDPedidoItem.subtotal), 0),
    ).join(
        BDPedidoItem, BDPedidoItem.pedido_id == BDPedido.id,
    ).filter(*pedido_filter).group_by(
        BDPedido.id, BDPedido.metodo_pago, BDPedido.monto_efectivo,
    ).all()

    total = 0.0
    efectivo = 0.0
    transferencia = 0.0
    mixto = 0.0
    orders_count = 0
    for _pid, metodo, m_efe, ptotal in pago_rows:
        ptotal = float(ptotal or 0)
        total += ptotal
        orders_count += 1
        if metodo == 'transferencia':
            transferencia += ptotal
        elif metodo == 'mixto':
            efe = float(m_efe or 0)
            efectivo += efe
            transferencia += (ptotal - efe)
            mixto += ptotal
        else:  # 'efectivo' o NULL (histórico) → efectivo
            efectivo += ptotal

    # Consolidado de productos pedidos, preservando el orden del backend.
    prod_rows = db.session.query(
        BDPedidoItem.producto_cod,
        func.coalesce(func.sum(BDPedidoItem.cantidad), 0),
        func.coalesce(func.sum(BDPedidoItem.subtotal), 0),
        Producto.nombre,
        Producto.orden,
    ).join(
        BDPedido, BDPedido.id == BDPedidoItem.pedido_id,
    ).outerjoin(
        Producto, Producto.codigo == BDPedidoItem.producto_cod,
    ).filter(*pedido_filter).group_by(
        BDPedidoItem.producto_cod, Producto.nombre, Producto.orden,
    ).order_by(
        func.coalesce(Producto.orden, 999999), BDPedidoItem.producto_cod,
    ).all()

    productos = [
        {
            'producto_cod': cod,
            'nombre': nombre or cod,
            'cantidad': int(cantidad or 0),
            'total': float(subtotal or 0),
            'orden': orden,
        }
        for (cod, cantidad, subtotal, nombre, orden) in prod_rows
    ]
    units = sum(p['cantidad'] for p in productos)

    return {
        'total_sold': total,
        'total_efectivo': efectivo,
        'total_transferencia': transferencia,
        'total_mixto': mixto,
        'units_sold': units,
        'productos_vendidos': productos,
        'orders_count': orders_count,
    }


@api_bp.route('/turnos/inicio', methods=['POST'])
@jwt_required()
def iniciar_turno():
    codigo_vendedor = get_jwt_identity()
    data = request.get_json(silent=True) or {}

    try:
        fecha = _parse_date(data.get('fecha'))
        turno_numero_raw = data.get('turno_numero')
        turno_numero = int(turno_numero_raw) if turno_numero_raw is not None else None
        hora_inicio = _parse_time(data.get('hora_inicio'))
    except (ValueError, TypeError):
        return respuesta_error('Datos invalidos para iniciar turno', 400)

    modo = data.get('modo')
    if modo not in ('autoventa', 'preventa'):
        modo = None

    abierto = BDTurno.query.filter_by(codigo_vendedor=codigo_vendedor, estado='abierto').first()
    if abierto:
        # First-write-wins: si el turno abierto aún no tiene modo y el app lo envía,
        # se fija (un turno conserva su modo hasta cerrarse). Nunca se sobreescribe.
        if abierto.modo is None and modo is not None:
            abierto.modo = modo
            db.session.commit()
        return respuesta_ok(_serializar_turno(abierto))

    existentes_vendedor = BDTurno.query.filter_by(
        codigo_vendedor=codigo_vendedor,
    ).order_by(BDTurno.turno_numero.desc(), BDTurno.id.desc()).all()

    if turno_numero is None:
        turno_numero = (existentes_vendedor[0].turno_numero + 1) if existentes_vendedor else 1

    existente = next((item for item in existentes_vendedor if item.turno_numero == turno_numero), None)
    if existente:
        # Si ya existe un turno cerrado con ese número, crear el siguiente libre de forma automática.
        if existente.estado == 'abierto':
            return respuesta_ok(_serializar_turno(existente))
        turno_numero = (existentes_vendedor[0].turno_numero + 1) if existentes_vendedor else turno_numero

    turno = BDTurno(
        codigo_vendedor=codigo_vendedor,
        fecha=fecha,
        turno_numero=turno_numero,
        hora_inicio=hora_inicio,
        estado='abierto',
        modo=modo,
        comentarios=data.get('comentarios'),
    )
    db.session.add(turno)
    db.session.commit()

    return respuesta_ok(_serializar_turno(turno), 201)


@api_bp.route('/turnos/<int:turno_id>/cierre', methods=['POST'])
@jwt_required()
def cerrar_turno(turno_id):
    codigo_vendedor = get_jwt_identity()
    data = request.get_json(silent=True) or {}

    turno = BDTurno.query.filter_by(id=turno_id, codigo_vendedor=codigo_vendedor).first()
    if not turno:
        return respuesta_error('Turno no encontrado', 404)

    if turno.estado == 'cerrado':
        return respuesta_ok(_serializar_turno(turno))

    try:
        hora_fin = _parse_time(data.get('hora_fin'))
    except ValueError:
        return respuesta_error('hora_fin invalida. Usa HH:MM o HH:MM:SS', 400)

    turno.hora_fin = hora_fin
    turno.estado = 'cerrado'

    comentarios = data.get('comentarios')
    if comentarios:
        if turno.comentarios:
            turno.comentarios = f"{turno.comentarios}\n{comentarios}"
        else:
            turno.comentarios = comentarios

    db.session.commit()
    return respuesta_ok(_serializar_turno(turno))


@api_bp.route('/turnos', methods=['GET'])
@api_bp.route('/turnos/historial', methods=['GET'])
@jwt_required()
def listar_turnos():
    """Lista los turnos del vendedor desde la BD (fuente de verdad, multi-dispositivo).

    Permite poblar un selector de turnos sin depender del caché local. Más recientes
    primero. Filtros opcionales: ``estado`` (abierto/cerrado), ``limit`` (def 50, máx 200).
    """
    codigo_vendedor = get_jwt_identity()

    query = BDTurno.query.filter_by(codigo_vendedor=codigo_vendedor)

    estado = (request.args.get('estado') or '').strip()
    if estado:
        query = query.filter(BDTurno.estado == estado)

    limit = request.args.get('limit', default=50, type=int) or 50
    limit = max(1, min(limit, 200))

    turnos = query.order_by(
        BDTurno.fecha.desc(), BDTurno.id.desc()
    ).limit(limit).all()

    return respuesta_ok({
        'total': len(turnos),
        'turnos': [_serializar_turno(t) for t in turnos],
    })


@api_bp.route('/turnos/actual', methods=['GET'])
@jwt_required()
def turno_actual():
    codigo_vendedor = get_jwt_identity()
    turno = BDTurno.query.filter_by(codigo_vendedor=codigo_vendedor, estado='abierto').order_by(BDTurno.id.desc()).first()

    if not turno:
        return respuesta_ok(None)

    return respuesta_ok(_serializar_turno(turno))


@api_bp.route('/turnos/resumen', methods=['GET'])
@jwt_required()
def resumen_turno_actual():
    codigo_vendedor = get_jwt_identity()

    # Accept optional turno_id query param for historical turno queries
    turno_id_param = request.args.get('turno_id', type=int)
    if turno_id_param:
        turno = BDTurno.query.filter_by(id=turno_id_param, codigo_vendedor=codigo_vendedor).first()
    else:
        turno = _obtener_turno_referencia(codigo_vendedor)

    if not turno:
        return respuesta_ok({
            'turno_id': None,
            'fecha': str(date.today()),
            'sales_mode': 'autoventa',
            'completed_visits': 0,
            'exception_visits': 0,
            'checked_stock_items': 0,
            'units_loaded': 0,
            'units_sold': 0,
            'total_sold': 0,
            'total_efectivo': 0,
            'total_transferencia': 0,
            'total_mixto': 0,
            'productos_vendidos': [],
            'orders_count': 0,
            'returns_handled': 0,
            'units_remaining': 0,
            'attended_customers': [],
        })

    # Las ventas con turno_id NULL de esta fecha se atribuyen SOLO al turno primario
    # (el más reciente del día) para no contarlas en varios turnos de la misma fecha.
    incluir_null_ventas = _es_turno_primario_de_fecha(turno)

    # Visitas completadas (done) - count ALL events, not distinct clients
    visitas_completadas = db.session.query(
        func.count(BDVisitaCliente.id)
    ).filter(
        BDVisitaCliente.codigo_vendedor == codigo_vendedor,
        BDVisitaCliente.estado == 'completada',
        _filtro_turno_o_fecha(turno, BDVisitaCliente.turno_id, BDVisitaCliente.fecha_visita),
    ).scalar() or 0

    # Visitas con excepcion - count ALL events, not distinct clients
    visitas_excepcion = db.session.query(
        func.count(BDVisitaCliente.id)
    ).filter(
        BDVisitaCliente.codigo_vendedor == codigo_vendedor,
        BDVisitaCliente.estado == 'excepcion',
        _filtro_turno_o_fecha(turno, BDVisitaCliente.turno_id, BDVisitaCliente.fecha_visita),
    ).scalar() or 0

    # Clientes atendidos (detalle)
    visitas_detalle = db.session.query(
        BDVisitaCliente.id,
        BDVisitaCliente.cliente_id,
        BDVisitaCliente.estado,
        BDVisitaCliente.checkin_at,
    ).filter(
        BDVisitaCliente.codigo_vendedor == codigo_vendedor,
        BDVisitaCliente.estado.in_(['completada', 'excepcion']),
        _filtro_turno_o_fecha(turno, BDVisitaCliente.turno_id, BDVisitaCliente.fecha_visita),
    ).order_by(BDVisitaCliente.checkin_at.asc()).all()

    # Acción por cliente (venta/cambio/no_compra/visita) para el resumen parcial.
    # Fuente: qué operación registró el vendedor con ese cliente en el turno.
    venta_cliente_ids = {
        cid for (cid,) in db.session.query(BDVentaAutoventa.cliente_id).filter(
            BDVentaAutoventa.codigo_vendedor == codigo_vendedor,
            _filtro_turno_o_fecha(turno, BDVentaAutoventa.turno_id, BDVentaAutoventa.fecha, incluir_null_ventas),
        ).distinct().all()
    }
    cambio_cliente_ids = {
        cid for (cid,) in db.session.query(BDCambio.cliente_id).filter(
            BDCambio.codigo_vendedor == codigo_vendedor,
            BDCambio.turno_id == turno.id,
        ).distinct().all()
    }

    def _accion_cliente(cliente_id, estado):
        if estado == 'excepcion':
            return 'no_compra'
        if cliente_id in cambio_cliente_ids:
            return 'cambio'
        if cliente_id in venta_cliente_ids:
            return 'venta'
        return 'visita'

    attended_customers = [
        {
            'visita_id': v.id,
            'cliente_id': v.cliente_id,
            'estado': v.estado,
            'accion': _accion_cliente(v.cliente_id, v.estado),
            'timestamp': v.checkin_at.isoformat() if v.checkin_at else None,
        }
        for v in visitas_detalle
    ]

    # Anti doble-conteo: una vez que un despacho está ligado a turno_id, usar SOLO
    # ese filtro. Combinar "turno_id IS NULL AND fecha = turno.fecha" junto con los
    # despachos ligados al turno contaría el despacho admin Y el de preturno dos veces.
    has_turno_despacho = db.session.query(BDDespacho.id).filter(
        BDDespacho.vendedor_cod == codigo_vendedor,
        BDDespacho.despachado.is_(True),
        BDDespacho.turno_id == turno.id,
    ).first() is not None

    if has_turno_despacho:
        despacho_filter = (BDDespacho.turno_id == turno.id)
    else:
        despacho_filter = and_(
            BDDespacho.turno_id.is_(None),
            BDDespacho.fecha == turno.fecha,
        )

    despachos_query = db.session.query(
        func.coalesce(func.sum(BDDespachoItem.cantidad), 0),
        func.count(func.distinct(BDDespachoItem.producto_cod)),
    ).join(
        BDDespacho,
        BDDespacho.id == BDDespachoItem.despacho_id,
    ).filter(
        BDDespacho.vendedor_cod == codigo_vendedor,
        BDDespacho.despachado.is_(True),
        despacho_filter,
    )

    # Unidades vendidas (cantidad)
    ventas_query = db.session.query(
        func.coalesce(func.sum(BDVentaAutoventaItem.cantidad), 0)
    ).join(
        BDVentaAutoventa,
        BDVentaAutoventa.id == BDVentaAutoventaItem.autoventa_id,
    ).filter(
        BDVentaAutoventa.codigo_vendedor == codigo_vendedor,
        _filtro_turno_o_fecha(turno, BDVentaAutoventa.turno_id, BDVentaAutoventa.fecha, incluir_null_ventas),
    )

    # Total vendido en dinero
    total_sold_query = db.session.query(
        func.coalesce(func.sum(BDVentaAutoventa.total), 0)
    ).filter(
        BDVentaAutoventa.codigo_vendedor == codigo_vendedor,
        _filtro_turno_o_fecha(turno, BDVentaAutoventa.turno_id, BDVentaAutoventa.fecha, incluir_null_ventas),
    )

    # Desglose por FORMA DE PAGO. INVARIANTE: efectivo + transferencia = total_sold.
    # Una venta MIXTA reparte su importe: la porción en efectivo (monto_efectivo) va a
    # la cubeta de efectivo y el resto (total - monto_efectivo) a la de transferencia,
    # de modo que nunca se pierde ni se duplica dinero. NULL (histórico) = efectivo.
    # `mixto` es una métrica INFORMATIVA (bruto de las ventas mixtas): NO se suma al
    # gran total (ya está contenido dentro de efectivo + transferencia).
    # Fallback defensivo: si monto_efectivo es NULL en una venta mixta (registro
    # legado sin split), se trata como 0 → todo el importe cae en transferencia; no
    # se fabrica un split inexistente.
    mixto_efectivo = func.coalesce(BDVentaAutoventa.monto_efectivo, 0)
    efectivo_expr = case(
        (BDVentaAutoventa.metodo_pago == 'transferencia', 0),
        (BDVentaAutoventa.metodo_pago == 'mixto', mixto_efectivo),
        else_=BDVentaAutoventa.total,
    )
    transferencia_expr = case(
        (BDVentaAutoventa.metodo_pago == 'transferencia', BDVentaAutoventa.total),
        (BDVentaAutoventa.metodo_pago == 'mixto', BDVentaAutoventa.total - mixto_efectivo),
        else_=0,
    )
    mixto_expr = case(
        (BDVentaAutoventa.metodo_pago == 'mixto', BDVentaAutoventa.total),
        else_=0,
    )
    pago_breakdown_query = db.session.query(
        func.coalesce(func.sum(efectivo_expr), 0),
        func.coalesce(func.sum(transferencia_expr), 0),
        func.coalesce(func.sum(mixto_expr), 0),
    ).filter(
        BDVentaAutoventa.codigo_vendedor == codigo_vendedor,
        _filtro_turno_o_fecha(turno, BDVentaAutoventa.turno_id, BDVentaAutoventa.fecha, incluir_null_ventas),
    )

    # Consolidado de ventas por producto (para el recibo "Resumen de ventas").
    productos_vendidos_rows = db.session.query(
        BDVentaAutoventaItem.producto_cod,
        func.coalesce(func.sum(BDVentaAutoventaItem.cantidad), 0),
        func.coalesce(func.sum(BDVentaAutoventaItem.subtotal), 0),
        Producto.nombre,
        Producto.orden,
    ).join(
        BDVentaAutoventa,
        BDVentaAutoventa.id == BDVentaAutoventaItem.autoventa_id,
    ).outerjoin(
        Producto, Producto.codigo == BDVentaAutoventaItem.producto_cod,
    ).filter(
        BDVentaAutoventa.codigo_vendedor == codigo_vendedor,
        _filtro_turno_o_fecha(turno, BDVentaAutoventa.turno_id, BDVentaAutoventa.fecha, incluir_null_ventas),
    ).group_by(
        BDVentaAutoventaItem.producto_cod, Producto.nombre, Producto.orden,
    ).order_by(
        func.coalesce(Producto.orden, 999999), BDVentaAutoventaItem.producto_cod,
    ).all()

    # Devoluciones reales (vendedor + cliente), nunca cambios. Solo las del turno.
    devoluciones_query = db.session.query(
        func.coalesce(func.sum(BDDevolucionItem.cantidad), 0)
    ).join(
        BDDevolucion,
        BDDevolucion.id == BDDevolucionItem.devolucion_id,
    ).filter(
        BDDevolucion.codigo_vendedor == codigo_vendedor,
        BDDevolucion.turno_id == turno.id,
    )

    # Productos recibidos DE VUELTA del cliente como parte de un cambio.
    # Se registran en BDCambioItem(tipo='devolucion'), aparte de las devoluciones reales.
    cambio_returns_query = db.session.query(
        func.coalesce(func.sum(BDCambioItem.cantidad), 0)
    ).join(
        BDCambio,
        BDCambio.id == BDCambioItem.cambio_id,
    ).filter(
        BDCambio.codigo_vendedor == codigo_vendedor,
        BDCambio.turno_id == turno.id,
        BDCambioItem.tipo == 'devolucion',
    )

    completed_visits = int(visitas_completadas or 0)
    exception_visits = int(visitas_excepcion or 0)
    units_loaded_raw, checked_stock_items_raw = despachos_query.first() or (0, 0)
    units_loaded = int(units_loaded_raw or 0)
    checked_stock_items = int(checked_stock_items_raw or 0)
    units_sold = int(ventas_query.scalar() or 0)
    total_sold = float(total_sold_query.scalar() or 0)
    total_efectivo_raw, total_transferencia_raw, total_mixto_raw = pago_breakdown_query.first() or (0, 0, 0)
    total_efectivo = float(total_efectivo_raw or 0)
    total_transferencia = float(total_transferencia_raw or 0)
    total_mixto = float(total_mixto_raw or 0)
    productos_vendidos = [
        {
            'producto_cod': cod,
            'nombre': nombre or cod,
            'cantidad': int(cantidad or 0),
            'total': float(subtotal or 0),
            'orden': orden,
        }
        for (cod, cantidad, subtotal, nombre, orden) in productos_vendidos_rows
    ]
    returns_handled = int(devoluciones_query.scalar() or 0)
    cambio_returns = int(cambio_returns_query.scalar() or 0)
    # units_remaining SIEMPRE se calcula sobre la VENTA de autoventa (movimiento real
    # del inventario del vehículo). En preventa el inventario NO se toca, así que se
    # usa units_sold de ventas (0 en un turno de preventa puro), no las unidades pedidas.
    units_remaining = max(0, units_loaded - units_sold + returns_handled + cambio_returns)

    # ── Resumen COMERCIAL según el MODO del turno (ventas vs pedidos) ──────────────
    # autoventa → agrega ventas (BDVentaAutoventa); preventa → agrega pedidos (BDPedido).
    # Nunca se fuerzan pedidos a la tabla de ventas ni viceversa.
    sales_mode = _resolver_sales_mode(turno)
    orders_count = 0
    if sales_mode == 'preventa':
        pv = _resumen_comercial_preventa(codigo_vendedor, turno)
        total_sold = pv['total_sold']
        total_efectivo = pv['total_efectivo']
        total_transferencia = pv['total_transferencia']
        total_mixto = pv['total_mixto']
        units_sold = pv['units_sold']
        productos_vendidos = pv['productos_vendidos']
        orders_count = pv['orders_count']

    return respuesta_ok({
        'turno_id': turno.id,
        'fecha': str(turno.fecha),
        'sales_mode': sales_mode,
        'completed_visits': completed_visits,
        'exception_visits': exception_visits,
        'checked_stock_items': checked_stock_items,
        'units_loaded': units_loaded,
        'units_sold': units_sold,
        'total_sold': total_sold,
        'total_efectivo': total_efectivo,
        'total_transferencia': total_transferencia,
        'total_mixto': total_mixto,
        'productos_vendidos': productos_vendidos,
        'orders_count': orders_count,
        'returns_handled': returns_handled,
        'cambio_returns': cambio_returns,
        'units_remaining': units_remaining,
        'attended_customers': attended_customers,
    })


@api_bp.route('/turnos/historial-resumen', methods=['GET'])
@jwt_required()
def historial_resumen_turnos():
    """Historial COMPLETO de turnos del vendedor (BD, multi-dispositivo) con sus
    métricas agregadas en UNA sola respuesta.

    A diferencia de /turnos/resumen (un turno por llamada), aquí se devuelven N
    turnos con sus totales calculados por turno_id usando agregaciones GROUP BY:
    una query por métrica (no N+1, no por-turno round-trips).

    Filtros opcionales: ?desde=YYYY-MM-DD&hasta=YYYY-MM-DD&estado=abierto|cerrado|todos&limit=50

    El vendedor SIEMPRE sale del JWT (no de un parámetro manipulable).

    Métricas omitidas a propósito (no atribuibles por turno en el esquema actual):
      - pedidos_total / extras: BDPedido y BDExtra no tienen turno_id.
      - liquidado: BD_LIQUIDACION liga a BDVenta (web), no al turno de autoventa.
    """
    codigo_vendedor = get_jwt_identity()

    estado = (request.args.get('estado') or '').strip().lower()
    limit = request.args.get('limit', default=50, type=int) or 50
    limit = max(1, min(limit, 200))

    q = BDTurno.query.filter_by(codigo_vendedor=codigo_vendedor)
    if estado in ('abierto', 'cerrado'):
        q = q.filter(BDTurno.estado == estado)

    desde_raw = request.args.get('desde')
    hasta_raw = request.args.get('hasta')
    try:
        if desde_raw:
            q = q.filter(BDTurno.fecha >= _parse_date(desde_raw))
        if hasta_raw:
            q = q.filter(BDTurno.fecha <= _parse_date(hasta_raw))
    except (ValueError, TypeError):
        return respuesta_error('Rango de fechas inválido (usa YYYY-MM-DD)', 400)

    turnos = q.order_by(BDTurno.fecha.desc(), BDTurno.id.desc()).limit(limit).all()
    turno_ids = [t.id for t in turnos]
    # Fecha por turno, para atribuir por fecha las ventas con turno_id NULL
    # (ver comentario en la sección de ventas). Mismo criterio que /turnos/resumen.
    turno_fechas = {t.id: t.fecha for t in turnos}
    fechas = set(turno_fechas.values())

    # Turno PRIMARIO por fecha (mayor id) sobre TODOS los turnos del vendedor en esa
    # fecha (no solo los del window). Las ventas con turno_id NULL de una fecha se
    # atribuyen SOLO a su turno primario → nunca a varios turnos del mismo día.
    # Mismo criterio determinista que /turnos/resumen (_es_turno_primario_de_fecha).
    primary_turno_por_fecha = {}
    if fechas:
        primary_rows = db.session.query(
            BDTurno.fecha, func.max(BDTurno.id),
        ).filter(
            BDTurno.codigo_vendedor == codigo_vendedor,
            BDTurno.fecha.in_(fechas),
        ).group_by(BDTurno.fecha).all()
        primary_turno_por_fecha = {f: mid for f, mid in primary_rows}

    def _null_fecha(mapping, turno):
        """Aporte por fecha (turno_id NULL) SOLO si turno es primario de su fecha."""
        if primary_turno_por_fecha.get(turno.fecha) != turno.id:
            return 0
        return mapping.get(turno.fecha, 0)

    current_app.logger.info(
        '[historial-resumen] vendedor=%s estado=%s desde=%s hasta=%s limit=%s turnos_ids=%s',
        codigo_vendedor, estado or 'todos', desde_raw, hasta_raw, limit, turno_ids,
    )

    if not turno_ids:
        return respuesta_ok({
            'codigo_vendedor': codigo_vendedor,
            'desde': desde_raw,
            'hasta': hasta_raw,
            'total': 0,
            'turnos': [],
        })

    # --- Agregaciones por turno_id (una query por métrica, acotadas a turno_ids) ---
    def _to_map(rows):
        return {row[0]: row[1:] for row in rows}

    despacho_rows = db.session.query(
        BDDespacho.turno_id,
        func.coalesce(func.sum(BDDespachoItem.cantidad), 0),
    ).join(BDDespachoItem, BDDespacho.id == BDDespachoItem.despacho_id).filter(
        BDDespacho.vendedor_cod == codigo_vendedor,
        BDDespacho.despachado.is_(True),
        BDDespacho.turno_id.in_(turno_ids),
    ).group_by(BDDespacho.turno_id).all()
    despacho_map = {tid: int(qty or 0) for tid, qty in despacho_rows}

    ventas_rows = db.session.query(
        BDVentaAutoventa.turno_id,
        func.coalesce(func.sum(BDVentaAutoventa.total), 0),
    ).filter(
        BDVentaAutoventa.codigo_vendedor == codigo_vendedor,
        BDVentaAutoventa.turno_id.in_(turno_ids),
    ).group_by(BDVentaAutoventa.turno_id).all()
    ventas_total_map = {tid: float(total or 0) for tid, total in ventas_rows}

    # Ventas con turno_id NULL (offline-first: el turno abierto aún no estaba
    # resuelto al registrar la venta). Se atribuyen por fecha, EXACTAMENTE como
    # /turnos/resumen (turno_id == t.id OR (turno_id IS NULL AND fecha == t.fecha)),
    # pero SOLO al turno primario de la fecha (ver _null_fecha) → sin doble conteo.
    ventas_null_rows = db.session.query(
        BDVentaAutoventa.fecha,
        func.coalesce(func.sum(BDVentaAutoventa.total), 0),
    ).filter(
        BDVentaAutoventa.codigo_vendedor == codigo_vendedor,
        BDVentaAutoventa.turno_id.is_(None),
        BDVentaAutoventa.fecha.in_(fechas),
    ).group_by(BDVentaAutoventa.fecha).all()
    ventas_total_null_by_fecha = {f: float(total or 0) for f, total in ventas_null_rows}

    # Desglose por forma de pago por turno (mismo criterio que /turnos/resumen):
    # la venta mixta se reparte efectivo (monto_efectivo) + transferencia (resto), así
    # efectivo + transferencia = total; `mixto` es informativo (no se suma aparte).
    pago_mixto_efectivo = func.coalesce(BDVentaAutoventa.monto_efectivo, 0)
    pago_efectivo_expr = case(
        (BDVentaAutoventa.metodo_pago == 'transferencia', 0),
        (BDVentaAutoventa.metodo_pago == 'mixto', pago_mixto_efectivo),
        else_=BDVentaAutoventa.total,
    )
    pago_transferencia_expr = case(
        (BDVentaAutoventa.metodo_pago == 'transferencia', BDVentaAutoventa.total),
        (BDVentaAutoventa.metodo_pago == 'mixto', BDVentaAutoventa.total - pago_mixto_efectivo),
        else_=0,
    )
    pago_mixto_expr = case(
        (BDVentaAutoventa.metodo_pago == 'mixto', BDVentaAutoventa.total),
        else_=0,
    )
    pago_rows = db.session.query(
        BDVentaAutoventa.turno_id,
        func.coalesce(func.sum(pago_efectivo_expr), 0),
        func.coalesce(func.sum(pago_transferencia_expr), 0),
        func.coalesce(func.sum(pago_mixto_expr), 0),
    ).filter(
        BDVentaAutoventa.codigo_vendedor == codigo_vendedor,
        BDVentaAutoventa.turno_id.in_(turno_ids),
    ).group_by(BDVentaAutoventa.turno_id).all()
    efectivo_map = {tid: float(ef or 0) for tid, ef, _tr, _mx in pago_rows}
    transferencia_map = {tid: float(tr or 0) for tid, _ef, tr, _mx in pago_rows}
    mixto_map = {tid: float(mx or 0) for tid, _ef, _tr, mx in pago_rows}

    # Mismo fallback por fecha para el desglose de pago de ventas con turno_id NULL.
    pago_null_rows = db.session.query(
        BDVentaAutoventa.fecha,
        func.coalesce(func.sum(pago_efectivo_expr), 0),
        func.coalesce(func.sum(pago_transferencia_expr), 0),
        func.coalesce(func.sum(pago_mixto_expr), 0),
    ).filter(
        BDVentaAutoventa.codigo_vendedor == codigo_vendedor,
        BDVentaAutoventa.turno_id.is_(None),
        BDVentaAutoventa.fecha.in_(fechas),
    ).group_by(BDVentaAutoventa.fecha).all()
    efectivo_null_by_fecha = {f: float(ef or 0) for f, ef, _tr, _mx in pago_null_rows}
    transferencia_null_by_fecha = {f: float(tr or 0) for f, _ef, tr, _mx in pago_null_rows}
    mixto_null_by_fecha = {f: float(mx or 0) for f, _ef, _tr, mx in pago_null_rows}

    unidades_rows = db.session.query(
        BDVentaAutoventa.turno_id,
        func.coalesce(func.sum(BDVentaAutoventaItem.cantidad), 0),
    ).join(BDVentaAutoventaItem, BDVentaAutoventa.id == BDVentaAutoventaItem.autoventa_id).filter(
        BDVentaAutoventa.codigo_vendedor == codigo_vendedor,
        BDVentaAutoventa.turno_id.in_(turno_ids),
    ).group_by(BDVentaAutoventa.turno_id).all()
    unidades_map = {tid: int(qty or 0) for tid, qty in unidades_rows}

    # Mismo fallback por fecha para las unidades vendidas de ventas con turno_id NULL.
    unidades_null_rows = db.session.query(
        BDVentaAutoventa.fecha,
        func.coalesce(func.sum(BDVentaAutoventaItem.cantidad), 0),
    ).join(BDVentaAutoventaItem, BDVentaAutoventa.id == BDVentaAutoventaItem.autoventa_id).filter(
        BDVentaAutoventa.codigo_vendedor == codigo_vendedor,
        BDVentaAutoventa.turno_id.is_(None),
        BDVentaAutoventa.fecha.in_(fechas),
    ).group_by(BDVentaAutoventa.fecha).all()
    unidades_null_by_fecha = {f: int(qty or 0) for f, qty in unidades_null_rows}

    # Devoluciones por tipo (vendedor / cliente) en unidades.
    dev_rows = db.session.query(
        BDDevolucion.turno_id,
        BDDevolucion.tipo_devolucion,
        func.coalesce(func.sum(BDDevolucionItem.cantidad), 0),
    ).join(BDDevolucionItem, BDDevolucion.id == BDDevolucionItem.devolucion_id).filter(
        BDDevolucion.codigo_vendedor == codigo_vendedor,
        BDDevolucion.turno_id.in_(turno_ids),
    ).group_by(BDDevolucion.turno_id, BDDevolucion.tipo_devolucion).all()
    dev_vendedor_map = {}
    dev_cliente_map = {}
    for tid, tipo, qty in dev_rows:
        if tipo == 'cliente':
            dev_cliente_map[tid] = int(qty or 0)
        else:
            dev_vendedor_map[tid] = dev_vendedor_map.get(tid, 0) + int(qty or 0)

    cambios_count_rows = db.session.query(
        BDCambio.turno_id,
        func.count(BDCambio.id),
    ).filter(
        BDCambio.codigo_vendedor == codigo_vendedor,
        BDCambio.turno_id.in_(turno_ids),
    ).group_by(BDCambio.turno_id).all()
    cambios_count_map = {tid: int(n or 0) for tid, n in cambios_count_rows}

    cambio_returns_rows = db.session.query(
        BDCambio.turno_id,
        func.coalesce(func.sum(BDCambioItem.cantidad), 0),
    ).join(BDCambioItem, BDCambio.id == BDCambioItem.cambio_id).filter(
        BDCambio.codigo_vendedor == codigo_vendedor,
        BDCambio.turno_id.in_(turno_ids),
        BDCambioItem.tipo == 'devolucion',
    ).group_by(BDCambio.turno_id).all()
    cambio_returns_map = {tid: int(qty or 0) for tid, qty in cambio_returns_rows}

    visitas_rows = db.session.query(
        BDVisitaCliente.turno_id,
        BDVisitaCliente.estado,
        func.count(BDVisitaCliente.id),
    ).filter(
        BDVisitaCliente.codigo_vendedor == codigo_vendedor,
        BDVisitaCliente.turno_id.in_(turno_ids),
    ).group_by(BDVisitaCliente.turno_id, BDVisitaCliente.estado).all()
    visitas_total_map = {}
    visitas_hechas_map = {}
    for tid, vestado, n in visitas_rows:
        n = int(n or 0)
        visitas_total_map[tid] = visitas_total_map.get(tid, 0) + n
        if vestado in ('completada', 'excepcion'):
            visitas_hechas_map[tid] = visitas_hechas_map.get(tid, 0) + n

    items = []
    for t in turnos:
        carga_inicial = despacho_map.get(t.id, 0)
        # Ventas del turno = ligadas por turno_id + ligadas por fecha (turno_id NULL,
        # SOLO si t es el turno primario de su fecha). Idéntico a /turnos/resumen para
        # que pantalla y recibo coincidan, sin doble conteo entre turnos del mismo día.
        unidades_vendidas = unidades_map.get(t.id, 0) + _null_fecha(unidades_null_by_fecha, t)
        dev_vendedor = dev_vendedor_map.get(t.id, 0)
        dev_cliente = dev_cliente_map.get(t.id, 0)
        cambio_returns = cambio_returns_map.get(t.id, 0)
        # Consistente con /turnos/resumen: restante = cargado - vendido + devoluciones + cambio_returns
        saldo_final = max(0, carga_inicial - unidades_vendidas + dev_vendedor + dev_cliente + cambio_returns)
        items.append({
            'turno_id': t.id,
            'turno_numero': t.turno_numero,
            'fecha': str(t.fecha),
            'estado': t.estado,
            'carga_inicial': carga_inicial,
            'ventas_total': ventas_total_map.get(t.id, 0.0) + _null_fecha(ventas_total_null_by_fecha, t),
            'total_efectivo': efectivo_map.get(t.id, 0.0) + _null_fecha(efectivo_null_by_fecha, t),
            'total_transferencia': transferencia_map.get(t.id, 0.0) + _null_fecha(transferencia_null_by_fecha, t),
            'total_mixto': mixto_map.get(t.id, 0.0) + _null_fecha(mixto_null_by_fecha, t),
            'unidades_vendidas': unidades_vendidas,
            'cambios': cambios_count_map.get(t.id, 0),
            'cambio_returns': cambio_returns,
            'devoluciones_cliente': dev_cliente,
            'devoluciones_vendedor': dev_vendedor,
            'saldo_final': saldo_final,
            'visitas_total': visitas_total_map.get(t.id, 0),
            'visitas_realizadas': visitas_hechas_map.get(t.id, 0),
        })

    return respuesta_ok({
        'codigo_vendedor': codigo_vendedor,
        'desde': desde_raw,
        'hasta': hasta_raw,
        'total': len(items),
        'turnos': items,
    })
