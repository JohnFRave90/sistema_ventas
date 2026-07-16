import time
from datetime import date, datetime

from flask import current_app, request
from flask_jwt_extended import get_jwt_identity, jwt_required
from sqlalchemy import func, or_
from sqlalchemy.orm import joinedload

from app import db
from app.routes.api import api_bp, respuesta_ok
from app.models.despachos import BDDespacho, BDDespachoItem
from app.models.devoluciones import BDDevolucion
from app.models.devolucion_item import BDDevolucionItem
from app.models.producto import Producto
from app.models.ruta_sesion import BDRutaSesion
from app.models.turno import BDTurno
from app.utils.inventario import calcular_inventario_inicial, calcular_devolucion_anterior_map
from app.utils.productos import orden_index

PRE_TURNO_TIPO_ORIGEN = 'PREAPP'


def _parse_fecha(valor):
    """Convierte 'YYYY-MM-DD' a date; devuelve hoy si es inválida/ausente."""
    if not valor:
        return date.today()
    try:
        return datetime.strptime(valor, '%Y-%m-%d').date()
    except (TypeError, ValueError):
        return date.today()


def _despachos_para_carga(codigo_vendedor, fecha, turno_id=None):
    """Despachos fuente del cargue inicial + cantidades agregadas por producto.

    Regla de negocio: el cargue es lo que REALMENTE salió de bodega = el/los
    despacho(s) web del vendedor (pueden venir como pedido 'PD-' y/o extra 'EX-').

    - turno_id dado (lectura histórica): solo los despachos de ese turno.
    - Preturno (turno_id=None): se AGREGAN TODOS los despachos PENDIENTES del
      vendedor (despachado=True, turno_id IS NULL), sumando PD + PX, **sin filtrar
      por fecha exacta** — cada despacho hereda la fecha de su pedido/extra de origen,
      que puede no ser hoy (esa era la causa de que faltaran unidades: solo se contaba
      el despacho cuya fecha coincidía con hoy). Fallback por fecha si no hay
      pendientes (compatibilidad con cargas PREAPP/manuales antiguas).

    Eager-load de items (joinedload) para evitar N+1.

    :returns: (lista_despachos, {producto_cod: cantidad})
    """
    base = BDDespacho.query.options(joinedload(BDDespacho.items)).filter(
        BDDespacho.vendedor_cod == codigo_vendedor,
        BDDespacho.despachado.is_(True),
    )

    if turno_id is not None:
        despachos = base.filter(BDDespacho.turno_id == turno_id).all()
    else:
        # Preturno: SOLO el último LOTE de despachos pendientes (no todo el backlog).
        # El lote = los despachos pendientes creados en la fecha de creación más
        # reciente (created_at). Así PD + EX del mismo cargue se suman juntos, pero
        # los despachos viejos pendientes de días anteriores quedan excluidos.
        pendientes_q = base.filter(BDDespacho.turno_id.is_(None))
        ultimo = pendientes_q.order_by(
            BDDespacho.created_at.desc(), BDDespacho.id.desc()
        ).first()

        if ultimo is None:
            despachos = base.filter(BDDespacho.fecha == fecha).all()
        elif getattr(ultimo, 'created_at', None) is not None:
            lote_fecha = ultimo.created_at.date()
            despachos = pendientes_q.filter(
                func.date(BDDespacho.created_at) == lote_fecha
            ).all()
        else:
            # Sin created_at (datos sin migrar): lote mínimo = el más reciente por id.
            despachos = [ultimo]

    acumulado = {}
    for despacho in despachos:
        for item in despacho.items:
            acumulado[item.producto_cod] = acumulado.get(item.producto_cod, 0) + int(item.cantidad or 0)
    return despachos, acumulado


def _ultimo_turno_cerrado_id(codigo_vendedor, fecha=None):
    """Id del último turno cerrado del vendedor (el de cuyo cierre viene el sobrante).

    Si se pasa ``fecha``, se consideran solo turnos en/antes de esa fecha (el
    "anterior" respecto del día que se está cargando). Devuelve ``None`` si no hay.

    Nota: el esquema actual NO liga turno↔ruta, por lo que el filtrado por ruta no
    es posible sin una migración (turno.ruta_sesion_id). Se difiere ese refinamiento.
    """
    query = BDTurno.query.filter_by(codigo_vendedor=codigo_vendedor, estado='cerrado')
    if fecha is not None:
        query = query.filter(BDTurno.fecha <= fecha)
    turno = query.order_by(BDTurno.fecha.desc(), BDTurno.id.desc()).first()
    return turno.id if turno else None


def _devoluciones_anteriores(codigo_vendedor, fecha=None):
    """ÚLTIMA devolución/SOBRANTE del vendedor PENDIENTE de uso.

    Regla de negocio (confirmada por el cliente, con datos reales DV-01790 del 20/06
    sumándose al pedido PD-02356 del 24/06):
      - NO se filtra por fecha actual.
      - NO se filtra por turno_id (la devolución puede ser de un turno anterior).
      - tipo_devolucion = 'vendedor' OR NULL (legacy). Cliente NUNCA se suma.
      - consumida_app = 0 (COALESCE) — sobrante aún no sumado por la app.
      - Se toma la MÁS RECIENTE: ORDER BY id DESC LIMIT 1.

    IMPORTANTE: NO se filtra por `usos`. `usos` es un CONTADOR del sistema WEB
    (ventas.py incrementa al cerrar ventas, disponible mientras usos<2). La app tiene
    su propio flag `consumida_app` para no colisionar con la contabilidad del web
    (DV-01790 tenía usos=1 por una venta web y por eso quedaba excluida con el filtro
    antiguo `usos==0`).

    Al confirmar el cargue se marca consumida_app=1 (consumo consistente
    lectura↔escritura). Devuelve (lista[0..1 devoluciones], {producto_cod: cantidad}).
    Eager-load de items. tipo_devolucion puede faltar en BD pre-migración: try/except.
    """
    def _ultima(con_tipo):
        q = BDDevolucion.query.options(joinedload(BDDevolucion.items)).filter(
            BDDevolucion.codigo_vendedor == codigo_vendedor,
            func.coalesce(BDDevolucion.consumida_app, 0) == 0,
        )
        if con_tipo:
            q = q.filter(or_(
                BDDevolucion.tipo_devolucion == 'vendedor',
                BDDevolucion.tipo_devolucion.is_(None),
            ))
        return q.order_by(BDDevolucion.id.desc()).first()

    try:
        dev = _ultima(True)
    except Exception:
        db.session.rollback()
        dev = _ultima(False)

    devoluciones = [dev] if dev else []
    acumulado = {}
    for d in devoluciones:
        for item in (d.items or []):
            acumulado[item.producto_cod] = acumulado.get(item.producto_cod, 0) + int(item.cantidad or 0)

    current_app.logger.info(
        '[inventario/devolucion] vendedor=%s devolucion=%s productos=%s',
        codigo_vendedor,
        {'id': dev.id, 'consecutivo': getattr(dev, 'consecutivo', None),
         'fecha': str(dev.fecha), 'usos': dev.usos,
         'consumida_app': getattr(dev, 'consumida_app', None),
         'tipo': getattr(dev, 'tipo_devolucion', None)} if dev else None,
        len(acumulado),
    )
    return devoluciones, acumulado


def _devolucion_anterior_map(codigo_vendedor, fecha=None):
    """Compat: solo el mapa {producto_cod: cantidad} del sobrante del vendedor."""
    _devoluciones, mapa = _devoluciones_anteriores(codigo_vendedor, fecha=fecha)
    return mapa


def _marcar_sobrante_usado(codigo_vendedor, fecha):
    """Marca consumida_app=1 en el sobrante del vendedor consumido por el cargue.

    Idempotente: solo afecta consumida_app=0, y carga-inicial retorna antes ante un
    uuid ya procesado (reintento offline), por lo que NUNCA marca dos veces.
    NO toca `usos` (contador del WEB) ni devoluciones de cliente. No hace commit
    (lo hace el llamador).
    """
    devoluciones, _ = _devoluciones_anteriores(codigo_vendedor, fecha=fecha)
    marcadas = []
    for d in devoluciones:
        if (getattr(d, 'consumida_app', 0) or 0) == 0:
            d.consumida_app = 1
            marcadas.append(d.id)
    if marcadas:
        current_app.logger.info('[inventario/carga-inicial] sobrante consumido devoluciones=%s', marcadas)
    return marcadas


def _serializar_item_despacho(item):
    nombre = item.producto.nombre if item.producto else item.producto_cod
    return {
        'producto_cod': item.producto_cod,
        'nombre':       nombre,
        'cantidad':     item.cantidad
    }


def _serializar_item_devolucion(item):
    prod = Producto.query.filter_by(codigo=item.producto_cod).first()
    nombre = prod.nombre if prod else item.producto_cod
    return {
        'producto_cod': item.producto_cod,
        'nombre':       nombre,
        'cantidad':     item.cantidad
    }


@api_bp.route('/inventario/dia', methods=['GET'])
@jwt_required()
def inventario_dia():
    codigo_vendedor = get_jwt_identity()
    hoy = date.today()

    # Despachos del día marcados como despachados
    despachos = BDDespacho.query.filter_by(
        vendedor_cod=codigo_vendedor,
        fecha=hoy,
        despachado=True
    ).all()

    despachos_data = [{
        'consecutivo': d.codigo_origen,
        'items': [_serializar_item_despacho(i) for i in d.items]
    } for d in despachos]

    # Devolución anterior más reciente PENDIENTE para la app (consumida_app = 0).
    # NO se usa `usos` (contador del WEB) — ver _devoluciones_anteriores.
    dev_anterior = BDDevolucion.query.filter(
        BDDevolucion.codigo_vendedor == codigo_vendedor,
        func.coalesce(BDDevolucion.consumida_app, 0) == 0,
    ).order_by(BDDevolucion.id.desc()).first()

    dev_data = None
    if dev_anterior:
        dev_data = {
            'consecutivo': dev_anterior.consecutivo,
            'items': [_serializar_item_devolucion(i) for i in dev_anterior.items]
        }

    return respuesta_ok({
        'fecha':               str(hoy),
        'despachos':           despachos_data,
        'devolucion_anterior': dev_data
    })


@api_bp.route('/inventario/inicial', methods=['GET'])
@jwt_required()
def inventario_inicial():
    """Inventario inicial calculado: despacho + devolución anterior.

    A diferencia de ``/inventario/dia`` (que devuelve despacho y devolución por
    separado y obliga a la app a cruzarlos contra TODO el catálogo), este endpoint
    entrega la lista YA unificada por producto y SOLO con los productos que el
    vendedor realmente carga (cantidad_inicial > 0).

    Parámetros opcionales (por defecto: vendedor del JWT y fecha de hoy):
      - ``codigo_vendedor``: override del vendedor.
      - ``fecha``: 'YYYY-MM-DD'.
      - ``turno_id``: limita el despacho a un turno específico.
    """
    _t0 = time.perf_counter()
    _log = current_app.logger

    def _mark(label):
        _log.info('[inventario/inicial] %s (+%.0fms)', label, (time.perf_counter() - _t0) * 1000)

    _mark('start')

    codigo_vendedor = (request.args.get('codigo_vendedor') or get_jwt_identity() or '').strip()
    fecha = _parse_fecha(request.args.get('fecha'))
    _mark(f'vendedor resolved cod={codigo_vendedor} fecha={fecha}')

    turno_id_raw = request.args.get('turno_id')
    turno_id = None
    if turno_id_raw:
        try:
            turno_id = int(turno_id_raw)
        except (TypeError, ValueError):
            turno_id = None

    despachos_fuente, despacho_map = _despachos_para_carga(codigo_vendedor, fecha, turno_id=turno_id)
    _mark(f'despacho query done despachos={len(despachos_fuente)} productos={len(despacho_map)}')
    _log.info(
        '[inventario/inicial] vendedor=%s despachos_candidatos=%s',
        codigo_vendedor,
        [
            {
                'id': d.id,
                'fecha': str(d.fecha),
                'created_at': str(getattr(d, 'created_at', None)),
                'codigo_origen': d.codigo_origen,
                'tipo_origen': d.tipo_origen,
                'turno_id': d.turno_id,
            }
            for d in despachos_fuente
        ],
    )

    devoluciones_fuente, devolucion_map = _devoluciones_anteriores(codigo_vendedor, fecha=fecha)
    _mark(f'devolucion query done productos={len(devolucion_map)}')

    codigos = set(despacho_map) | set(devolucion_map)
    productos = Producto.query.filter(Producto.codigo.in_(list(codigos))).all() if codigos else []
    productos_map = {p.codigo: p for p in productos}
    _mark(f'productos mapping done n={len(productos_map)}')

    # orden_index = posición canónica del sistema de ventas (misma fuente que
    # get_productos_ordenados), NO la columna Producto.orden.
    items = calcular_inventario_inicial(despacho_map, devolucion_map, productos_map, orden_fn=orden_index)
    _mark(f'response built items={len(items)}')

    # Contexto: turno activo y sesión de ruta activa (para que la app sepa a qué
    # turno/ruta pertenece la carga). No bloquea si no existen.
    turno_activo = BDTurno.query.filter_by(
        codigo_vendedor=codigo_vendedor,
        estado='abierto',
        fecha=fecha,
    ).order_by(BDTurno.id.desc()).first()

    sesion_ruta = BDRutaSesion.query.filter_by(
        codigo_vendedor=codigo_vendedor,
        estado='activa',
    ).order_by(BDRutaSesion.id.desc()).first()

    mensaje = None
    if not items:
        mensaje = 'No hay despacho ni devolución registrados para esta fecha.'

    despachos_incluidos = [
        {
            'despacho_id': d.id,
            'tipo_origen': d.tipo_origen,
            'codigo_origen': d.codigo_origen,
            'fecha': str(d.fecha),
            'created_at': str(getattr(d, 'created_at', None)),
        }
        for d in despachos_fuente
    ]

    fecha_creacion_lote = None
    if despachos_fuente and getattr(despachos_fuente[0], 'created_at', None) is not None:
        fecha_creacion_lote = max(
            (d.created_at.date() for d in despachos_fuente if d.created_at is not None),
            default=None,
        )

    dev_usada = devoluciones_fuente[0] if devoluciones_fuente else None
    devolucion_usada = None
    if dev_usada is not None:
        devolucion_usada = {
            'devolucion_id': dev_usada.id,
            'codigo': getattr(dev_usada, 'consecutivo', None),
            'fecha': str(dev_usada.fecha),
        }

    return respuesta_ok({
        'turno_id': turno_activo.id if turno_activo else turno_id,
        'ruta_sesion_id': sesion_ruta.id if sesion_ruta else None,
        'codigo_vendedor': codigo_vendedor,
        'fecha': str(fecha),
        'fuente': 'ultimo_lote_despachos_pendientes_mas_devolucion_vendedor',
        'criterio_despacho': {
            'campo': 'created_at',
            'fecha_creacion_lote': str(fecha_creacion_lote) if fecha_creacion_lote else None,
        },
        'despacho_ids': [d.id for d in despachos_fuente],
        'despachos_incluidos': despachos_incluidos,
        'devolucion_usada': devolucion_usada,
        'mensaje': mensaje,
        'items': items,
    })


@api_bp.route('/inventario/carga-inicial', methods=['POST'])
@jwt_required()
def guardar_carga_inicial():
    codigo_vendedor = get_jwt_identity()
    hoy = date.today()
    data = request.get_json(silent=True) or {}

    raw_items = data.get('items') or []
    comentarios = (data.get('comentarios') or 'Carga inicial registrada desde app').strip()
    uuid_origen = (data.get('uuid') or '').strip() or None

    # Idempotencia UUID: si este despacho ya se procesó, retornarlo sin duplicar.
    if uuid_origen:
        existente = BDDespacho.query.filter_by(uuid_origen=uuid_origen).first()
        if existente:
            return respuesta_ok({
                'saved': True,
                'despacho_id': existente.id,
                'items_count': len(existente.items),
                'turno_id': existente.turno_id,
            }, 200)

    if not isinstance(raw_items, list) or len(raw_items) == 0:
        return respuesta_ok({'saved': False, 'message': 'Sin items para guardar'})

    normalized_items = []
    product_codes = set()

    for entry in raw_items:
        if not isinstance(entry, dict):
            continue
        producto_cod = str(entry.get('producto_cod') or '').strip()
        cantidad_raw = entry.get('cantidad')
        try:
            cantidad = int(cantidad_raw)
        except (TypeError, ValueError):
            continue

        if not producto_cod or cantidad <= 0:
            continue

        normalized_items.append({'producto_cod': producto_cod, 'cantidad': cantidad})
        product_codes.add(producto_cod)

    if len(normalized_items) == 0:
        return respuesta_ok({'saved': False, 'message': 'Sin items validos para guardar'})

    productos = Producto.query.filter(Producto.codigo.in_(list(product_codes))).all()
    productos_map = {p.codigo: p for p in productos}

    missing_codes = sorted([code for code in product_codes if code not in productos_map])
    if missing_codes:
        return respuesta_ok({'saved': False, 'message': 'Productos no encontrados', 'missing_codes': missing_codes})

    turno_activo = BDTurno.query.filter_by(
        codigo_vendedor=codigo_vendedor,
        estado='abierto',
        fecha=hoy,
    ).order_by(BDTurno.id.desc()).first()

    # Si no hay turno activo, lo abrimos automaticamente al confirmar la carga inicial.
    if not turno_activo:
        ultimo_turno_vendedor = BDTurno.query.filter_by(
            codigo_vendedor=codigo_vendedor,
        ).order_by(BDTurno.turno_numero.desc(), BDTurno.id.desc()).first()

        siguiente_numero = (ultimo_turno_vendedor.turno_numero + 1) if ultimo_turno_vendedor else 1

        turno_activo = BDTurno(
            codigo_vendedor=codigo_vendedor,
            fecha=hoy,
            turno_numero=siguiente_numero,
            hora_inicio=datetime.now().time().replace(microsecond=0),
            estado='abierto',
            comentarios='Turno auto-iniciado por carga inicial de inventario',
        )
        db.session.add(turno_activo)
        db.session.flush()

    # Regla de negocio: el cargue REAL es el/los despacho(s) web (PD/EX) del ÚLTIMO
    # LOTE. Se usa EXACTAMENTE el mismo criterio que GET /inventario/inicial
    # (_despachos_para_carga: solo el lote de created_at más reciente), por lo que se
    # asocian al turno SOLO esos despachos — NUNCA todo el backlog pendiente.
    despachos_lote, _ = _despachos_para_carga(codigo_vendedor, hoy)
    despachos_web = [d for d in despachos_lote if d.tipo_origen != PRE_TURNO_TIPO_ORIGEN]

    if despachos_web:
        for d in despachos_web:
            d.turno_id = turno_activo.id
        # Idempotencia: el uuid se estampa en UN solo despacho (la columna es UNIQUE).
        # Un reintento con el mismo uuid lo detecta arriba y no re-asocia ni duplica.
        if uuid_origen and not despachos_web[0].uuid_origen:
            despachos_web[0].uuid_origen = uuid_origen
        # Consumir el sobrante del vendedor (usos=1) — ya fue sumado al cargue.
        devoluciones_usadas = _marcar_sobrante_usado(codigo_vendedor, hoy)
        db.session.commit()
        return respuesta_ok({
            'saved': True,
            'fuente': 'despachos_web_asociados',
            'despacho_ids': [d.id for d in despachos_web],
            'devoluciones_usadas': devoluciones_usadas,
            'items_count': sum(len(d.items) for d in despachos_web),
            'turno_id': turno_activo.id,
        }, 201)

    despacho = BDDespacho.query.filter_by(
        vendedor_cod=codigo_vendedor,
        fecha=hoy,
        tipo_origen=PRE_TURNO_TIPO_ORIGEN,
    ).order_by(BDDespacho.id.desc()).first()

    if not despacho:
        despacho = BDDespacho(
            fecha=hoy,
            vendedor_cod=codigo_vendedor,
            codigo_origen=f'PRE-{hoy.strftime("%Y%m%d")}',
            tipo_origen=PRE_TURNO_TIPO_ORIGEN,
            uuid_origen=uuid_origen,
            despachado=True,
            comentarios=comentarios,
            turno_id=turno_activo.id if turno_activo else None,
        )
        db.session.add(despacho)
        db.session.flush()
    else:
        despacho.despachado = True
        despacho.comentarios = comentarios or despacho.comentarios
        despacho.turno_id = turno_activo.id if turno_activo else despacho.turno_id
        if uuid_origen and not despacho.uuid_origen:
            despacho.uuid_origen = uuid_origen
        BDDespachoItem.query.filter_by(despacho_id=despacho.id).delete()

    for item in normalized_items:
        producto = productos_map[item['producto_cod']]
        cantidad = item['cantidad']
        precio = float(producto.precio or 0)
        despacho_item = BDDespachoItem(
            despacho_id=despacho.id,
            producto_cod=producto.codigo,
            cantidad_pedida=cantidad,
            cantidad=cantidad,
            precio_unitario=precio,
            subtotal=precio * cantidad,
        )
        db.session.add(despacho_item)

    # Consumir el sobrante del vendedor (usos=1) — ya fue sumado al cargue.
    devoluciones_usadas = _marcar_sobrante_usado(codigo_vendedor, hoy)
    db.session.commit()

    return respuesta_ok({
        'saved': True,
        'despacho_id': despacho.id,
        'items_count': len(normalized_items),
        'devoluciones_usadas': devoluciones_usadas,
        'turno_id': despacho.turno_id,
    }, 201)


@api_bp.route('/inventario/preturno-estado', methods=['GET'])
@jwt_required()
def preturno_estado():
    codigo_vendedor = get_jwt_identity()
    hoy = date.today()

    turno_activo = BDTurno.query.filter_by(
        codigo_vendedor=codigo_vendedor,
        estado='abierto',
        fecha=hoy,
    ).order_by(BDTurno.id.desc()).first()

    sesion_ruta_activa = BDRutaSesion.query.filter_by(
        codigo_vendedor=codigo_vendedor,
        estado='activa',
    ).order_by(BDRutaSesion.id.desc()).first()

    preturno_despacho = BDDespacho.query.filter_by(
        vendedor_cod=codigo_vendedor,
        fecha=hoy,
        tipo_origen=PRE_TURNO_TIPO_ORIGEN,
        despachado=True,
    ).order_by(BDDespacho.id.desc()).first()

    preturno_cargado = bool(preturno_despacho and len(preturno_despacho.items) > 0)

    return respuesta_ok({
        'fecha': str(hoy),
        'turno_activo': bool(turno_activo),
        'turno_id': turno_activo.id if turno_activo else None,
        'ruta_activa': bool(sesion_ruta_activa),
        'ruta_nombre': sesion_ruta_activa.ruta_nombre if sesion_ruta_activa else None,
        'preturno_cargado': preturno_cargado,
        'despacho_id': preturno_despacho.id if preturno_despacho else None,
        'should_skip_preturno': bool(sesion_ruta_activa and preturno_cargado),
    })
