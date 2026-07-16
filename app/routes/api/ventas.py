from datetime import date
from flask import request
from flask_jwt_extended import jwt_required, get_jwt_identity
from app import db
from app.routes.api import api_bp, respuesta_ok, respuesta_error
from app.models.venta_autoventa import BDVentaAutoventa, BDVentaAutoventaItem
from app.models.producto import Producto
from app.models.cliente import Cliente
from app.models.turno import BDTurno
from app.models.visita_cliente import BDVisitaCliente
from app.utils.documentos import generar_consecutivo


_METODOS_PAGO = ('efectivo', 'transferencia', 'mixto')


def normalizar_pago(data, total=None):
    """Normaliza los campos de pago de un payload.

    Retorna (metodo_pago, monto_efectivo, monto_transferencia). Para métodos
    puros los montos quedan en None (el total cuenta completo en su forma). Para
    'mixto' se conservan los montos enviados; si no vienen y hay total, se deja
    el efectivo por defecto para no perder el importe.
    """
    metodo = data.get('metodo_pago')
    if metodo not in _METODOS_PAGO:
        return (None, None, None)
    if metodo != 'mixto':
        return (metodo, None, None)

    def _num(v):
        try:
            return round(float(v), 2)
        except (TypeError, ValueError):
            return None

    efectivo = _num(data.get('monto_efectivo'))
    transferencia = _num(data.get('monto_transferencia'))
    if efectivo is None and transferencia is None and total is not None:
        efectivo = round(float(total), 2)
        transferencia = 0.0
    return ('mixto', efectivo, transferencia)


def _guardar_venta(
    codigo_vendedor,
    cliente_id,
    fecha,
    items_data,
    uuid_origen=None,
    por_sync=False,
    turno_id=None,
    visit_id=None,
    pago=None,
):
    """Crea BDVentaAutoventa + items. Retorna la venta creada."""
    total = 0
    items_creados = []
    for it in items_data:
        prod = Producto.query.filter_by(codigo=it['producto_cod']).first()
        if not prod:
            raise ValueError(f"Producto {it['producto_cod']} no existe")
        subtotal = prod.precio * it['cantidad']
        total += subtotal
        items_creados.append((prod, it['cantidad'], subtotal))

    metodo_pago, monto_efectivo, monto_transferencia = normalizar_pago(pago or {}, total)

    venta = BDVentaAutoventa(
        consecutivo=generar_consecutivo(BDVentaAutoventa, 'AV'),
        codigo_vendedor=codigo_vendedor,
        cliente_id=cliente_id,
        turno_id=turno_id,
        visit_id=visit_id,
        fecha=fecha,
        total=total,
        metodo_pago=metodo_pago,
        monto_efectivo=monto_efectivo,
        monto_transferencia=monto_transferencia,
        enviada_por_sync=por_sync,
        uuid_origen=uuid_origen
    )
    db.session.add(venta)
    db.session.flush()

    for prod, cantidad, subtotal in items_creados:
        db.session.add(BDVentaAutoventaItem(
            autoventa_id=venta.id,
            producto_cod=prod.codigo,
            cantidad=cantidad,
            precio_unit=prod.precio,
            subtotal=subtotal
        ))
    db.session.commit()
    return venta


@api_bp.route('/ventas', methods=['POST'])
@jwt_required()
def registrar_venta():
    codigo_vendedor = get_jwt_identity()
    data = request.get_json(silent=True) or {}

    uuid_origen = data.get('uuid')
    cliente_id = data.get('cliente_id')
    turno_id = data.get('turno_id')
    visit_id = data.get('visit_id')
    items_data = data.get('items', [])

    if not cliente_id or not items_data:
        return respuesta_error('cliente_id e items son requeridos', 400)

    cliente = Cliente.query.filter_by(id=cliente_id).first()
    if not cliente or cliente.codigo_vendedor != codigo_vendedor:
        return respuesta_error('Cliente no encontrado', 404)

    if turno_id is not None:
        turno = BDTurno.query.filter_by(id=turno_id, codigo_vendedor=codigo_vendedor).first()
        if not turno:
            return respuesta_error('turno_id no valido para el vendedor', 400)

    if visit_id is not None:
        visita = BDVisitaCliente.query.filter_by(
            id=visit_id,
            cliente_id=cliente_id,
            codigo_vendedor=codigo_vendedor,
        ).first()
        if not visita:
            return respuesta_error('visit_id no valido para el cliente/vendedor', 400)

    # Idempotencia: si ya existe venta con este uuid, retornar la original
    if uuid_origen:
        existente = BDVentaAutoventa.query.filter_by(uuid_origen=uuid_origen).first()
        if existente:
            return respuesta_ok({
                'consecutivo': existente.consecutivo,
                'total': float(existente.total),
                'metodo_pago': existente.metodo_pago,
                'items': [{
                    'producto_cod': i.producto_cod,
                    'cantidad': i.cantidad,
                    'precio_unit': float(i.precio_unit),
                    'subtotal': float(i.subtotal)
                } for i in existente.items]
            })

    try:
        fecha = date.fromisoformat(data.get('fecha', str(date.today())))
        venta = _guardar_venta(
            codigo_vendedor,
            cliente_id,
            fecha,
            items_data,
            uuid_origen=uuid_origen,
            turno_id=turno_id,
            visit_id=visit_id,
            pago=data,
        )
    except ValueError as e:
        return respuesta_error(str(e), 400)

    return respuesta_ok({
        'consecutivo': venta.consecutivo,
        'total': float(venta.total),
        'metodo_pago': venta.metodo_pago,
        'items': [{
            'producto_cod': i.producto_cod,
            'cantidad': i.cantidad,
            'precio_unit': float(i.precio_unit),
            'subtotal': float(i.subtotal)
        } for i in venta.items]
    })


@api_bp.route('/ventas/dia', methods=['GET'])
@jwt_required()
def ventas_del_dia():
    codigo_vendedor = get_jwt_identity()
    hoy = date.today()
    ventas = BDVentaAutoventa.query.filter_by(
        codigo_vendedor=codigo_vendedor, fecha=hoy
    ).order_by(BDVentaAutoventa.id.desc()).all()

    return respuesta_ok([{
        'consecutivo':   v.consecutivo,
        'cliente_id':    v.cliente_id,
        'cliente_nombre': v.cliente.nombre if v.cliente else '',
        'fecha':         str(v.fecha),
        'total':         float(v.total) if v.total else 0
    } for v in ventas])
