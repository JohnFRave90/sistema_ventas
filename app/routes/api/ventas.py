from datetime import date
from flask import request
from flask_jwt_extended import jwt_required, get_jwt_identity
from app import db
from app.routes.api import api_bp, respuesta_ok, respuesta_error
from app.models.venta_autoventa import BDVentaAutoventa, BDVentaAutoventaItem
from app.models.producto import Producto
from app.models.cliente import Cliente
from app.utils.documentos import generar_consecutivo


def _guardar_venta(codigo_vendedor, cliente_id, fecha, items_data, uuid_origen=None, por_sync=False):
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

    venta = BDVentaAutoventa(
        consecutivo=generar_consecutivo(BDVentaAutoventa, 'AV'),
        codigo_vendedor=codigo_vendedor,
        cliente_id=cliente_id,
        fecha=fecha,
        total=total,
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
    items_data = data.get('items', [])

    if not cliente_id or not items_data:
        return respuesta_error('cliente_id e items son requeridos', 400)

    cliente = Cliente.query.filter_by(id=cliente_id).first()
    if not cliente or cliente.codigo_vendedor != codigo_vendedor:
        return respuesta_error('Cliente no encontrado', 404)

    # Idempotencia: si ya existe venta con este uuid, retornar la original
    if uuid_origen:
        existente = BDVentaAutoventa.query.filter_by(uuid_origen=uuid_origen).first()
        if existente:
            return respuesta_ok({
                'consecutivo': existente.consecutivo,
                'total': float(existente.total),
                'items': [{
                    'producto_cod': i.producto_cod,
                    'cantidad': i.cantidad,
                    'precio_unit': float(i.precio_unit),
                    'subtotal': float(i.subtotal)
                } for i in existente.items]
            })

    try:
        fecha = date.fromisoformat(data.get('fecha', str(date.today())))
        venta = _guardar_venta(codigo_vendedor, cliente_id, fecha, items_data, uuid_origen)
    except ValueError as e:
        return respuesta_error(str(e), 400)

    return respuesta_ok({
        'consecutivo': venta.consecutivo,
        'total': float(venta.total),
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
