from datetime import date, datetime

from flask import request
from flask_jwt_extended import get_jwt_identity, jwt_required

from app import db
from app.routes.api import api_bp, respuesta_ok
from app.models.despachos import BDDespacho, BDDespachoItem
from app.models.devoluciones import BDDevolucion
from app.models.devolucion_item import BDDevolucionItem
from app.models.producto import Producto
from app.models.ruta_sesion import BDRutaSesion
from app.models.turno import BDTurno

PRE_TURNO_TIPO_ORIGEN = 'PREAPP'


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

    # Devolución anterior más reciente con usos = 0
    dev_anterior = BDDevolucion.query.filter_by(
        codigo_vendedor=codigo_vendedor,
        usos=0
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


@api_bp.route('/inventario/carga-inicial', methods=['POST'])
@jwt_required()
def guardar_carga_inicial():
    codigo_vendedor = get_jwt_identity()
    hoy = date.today()
    data = request.get_json(silent=True) or {}

    raw_items = data.get('items') or []
    comentarios = (data.get('comentarios') or 'Carga inicial registrada desde app').strip()

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

    db.session.commit()

    return respuesta_ok({
        'saved': True,
        'despacho_id': despacho.id,
        'items_count': len(normalized_items),
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
