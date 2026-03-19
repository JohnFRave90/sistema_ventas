import re
from datetime import date, timezone, timedelta, datetime
from flask import request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app import db
from app.routes.api import api_bp, respuesta_error
from app.routes.api.ventas import _guardar_venta
from app.models.venta_autoventa import BDVentaAutoventa
from app.models.devoluciones import BDDevolucion
from app.models.devolucion_item import BDDevolucionItem
from app.models.pedidos import BDPedido
from app.models.pedido_item import BDPedidoItem
from app.models.extras import BDExtra
from app.models.extra_item import BDExtraItem
from app.models.producto import Producto
from app.models.cliente import Cliente
from app.utils.documentos import generar_consecutivo


def _parse_timestamp(ts_str):
    """Parsea ISO 8601 con timezone y retorna datetime UTC-aware (stdlib only)."""
    try:
        m = re.match(r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})([+-]\d{2}:\d{2}|Z)?', ts_str or '')
        if not m:
            return datetime.min.replace(tzinfo=timezone.utc)
        dt_str, tz_str = m.group(1), m.group(2)
        dt = datetime.fromisoformat(dt_str)
        if tz_str and tz_str != 'Z':
            sign = 1 if tz_str[0] == '+' else -1
            h, mn = int(tz_str[1:3]), int(tz_str[4:6])
            dt = dt - timedelta(hours=sign*h, minutes=sign*mn)
        return dt.replace(tzinfo=timezone.utc)
    except Exception:
        return datetime.min.replace(tzinfo=timezone.utc)


def _procesar_venta(codigo_vendedor, data, uuid):
    existente = BDVentaAutoventa.query.filter_by(uuid_origen=uuid).first()
    if existente:
        return {'uuid': uuid, 'ok': True, 'consecutivo': existente.consecutivo}
    cliente_id = data.get('cliente_id')
    items_data = data.get('items', [])
    cliente = Cliente.query.filter_by(id=cliente_id).first()
    if not cliente or cliente.codigo_vendedor != codigo_vendedor:
        return {'uuid': uuid, 'ok': False, 'error': 'Cliente no encontrado'}
    try:
        venta = _guardar_venta(codigo_vendedor, cliente_id, date.today(), items_data, uuid, por_sync=True)
        return {'uuid': uuid, 'ok': True, 'consecutivo': venta.consecutivo}
    except Exception as e:
        db.session.rollback()
        return {'uuid': uuid, 'ok': False, 'error': str(e)}


def _procesar_devolucion(codigo_vendedor, data, uuid):
    items_data = data.get('items', [])
    for it in items_data:
        if it.get('cantidad', 0) < 0:
            return {'uuid': uuid, 'ok': False, 'error': f"Ítem {it.get('producto_cod')} tiene cantidad negativa"}
    try:
        devolucion = BDDevolucion(
            consecutivo=generar_consecutivo(BDDevolucion, 'DV'),
            codigo_vendedor=codigo_vendedor,
            fecha=date.today(),
            comentarios=data.get('comentarios', ''),
            usos=0
        )
        db.session.add(devolucion)
        db.session.flush()
        for it in items_data:
            prod = Producto.query.filter_by(codigo=it['producto_cod']).first()
            if not prod:
                db.session.rollback()
                return {'uuid': uuid, 'ok': False, 'error': f"Producto {it['producto_cod']} no existe"}
            db.session.add(BDDevolucionItem(
                devolucion_id=devolucion.id, producto_cod=prod.codigo,
                cantidad=it['cantidad'], precio_unit=prod.precio, subtotal=prod.precio * it['cantidad']
            ))
        db.session.commit()
        return {'uuid': uuid, 'ok': True, 'consecutivo': devolucion.consecutivo}
    except Exception as e:
        db.session.rollback()
        return {'uuid': uuid, 'ok': False, 'error': str(e)}


def _procesar_pedido(codigo_vendedor, data, uuid):
    existente = BDPedido.query.filter_by(uuid_origen=uuid).first()
    if existente:
        return {'uuid': uuid, 'ok': True, 'consecutivo': existente.consecutivo}
    try:
        pedido = BDPedido(
            consecutivo=generar_consecutivo(BDPedido, 'PD'),
            codigo_vendedor=codigo_vendedor,
            fecha=date.today(),
            comentarios=data.get('comentarios', ''),
            usado=False,
            uuid_origen=uuid
        )
        db.session.add(pedido)
        db.session.flush()
        for it in data.get('items', []):
            prod = Producto.query.filter_by(codigo=it['producto_cod']).first()
            if not prod:
                db.session.rollback()
                return {'uuid': uuid, 'ok': False, 'error': f"Producto {it['producto_cod']} no existe"}
            db.session.add(BDPedidoItem(
                pedido_id=pedido.id, producto_cod=prod.codigo,
                cantidad=it['cantidad'], precio_unit=prod.precio, subtotal=prod.precio * it['cantidad']
            ))
        db.session.commit()
        return {'uuid': uuid, 'ok': True, 'consecutivo': pedido.consecutivo}
    except Exception as e:
        db.session.rollback()
        return {'uuid': uuid, 'ok': False, 'error': str(e)}


def _procesar_extra(codigo_vendedor, data, uuid):
    existente = BDExtra.query.filter_by(uuid_origen=uuid).first()
    if existente:
        return {'uuid': uuid, 'ok': True, 'consecutivo': existente.consecutivo}
    try:
        extra = BDExtra(
            consecutivo=generar_consecutivo(BDExtra, 'EX'),
            codigo_vendedor=codigo_vendedor,
            fecha=date.today(),
            comentarios=data.get('comentarios', ''),
            usado=False,
            uuid_origen=uuid
        )
        db.session.add(extra)
        db.session.flush()
        for it in data.get('items', []):
            prod = Producto.query.filter_by(codigo=it['producto_cod']).first()
            if not prod:
                db.session.rollback()
                return {'uuid': uuid, 'ok': False, 'error': f"Producto {it['producto_cod']} no existe"}
            db.session.add(BDExtraItem(
                extra_id=extra.id, producto_cod=prod.codigo,
                cantidad=it['cantidad'], precio_unit=prod.precio, subtotal=prod.precio * it['cantidad']
            ))
        db.session.commit()
        return {'uuid': uuid, 'ok': True, 'consecutivo': extra.consecutivo}
    except Exception as e:
        db.session.rollback()
        return {'uuid': uuid, 'ok': False, 'error': str(e)}


PROCESADORES = {
    'venta':      _procesar_venta,
    'devolucion': _procesar_devolucion,
    'pedido':     _procesar_pedido,
    'extra':      _procesar_extra,
}


@api_bp.route('/sync', methods=['POST'])
@jwt_required()
def sync_batch():
    codigo_vendedor = get_jwt_identity()
    payload = request.get_json(silent=True) or {}
    operaciones = payload.get('operaciones', [])

    if not operaciones:
        return respuesta_error('operaciones es requerido', 400)

    operaciones_ordenadas = sorted(operaciones, key=lambda op: _parse_timestamp(op.get('timestamp', '')))

    resultados = []
    for op in operaciones_ordenadas:
        uuid = op.get('uuid', '')
        tipo = op.get('tipo', '')
        data = op.get('data', {})
        procesador = PROCESADORES.get(tipo)
        if not procesador:
            resultados.append({'uuid': uuid, 'ok': False, 'error': f"Tipo desconocido: {tipo}"})
            continue
        resultado = procesador(codigo_vendedor, data, uuid)
        resultados.append(resultado)

    return jsonify({'ok': True, 'resultados': resultados})
