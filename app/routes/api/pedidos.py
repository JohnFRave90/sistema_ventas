from datetime import date
from flask import request
from flask_jwt_extended import jwt_required, get_jwt_identity
from app import db
from app.routes.api import api_bp, respuesta_ok, respuesta_error
from app.models.pedidos import BDPedido
from app.models.pedido_item import BDPedidoItem
from app.models.producto import Producto
from app.models.cliente import Cliente
from app.utils.documentos import generar_consecutivo
from app.routes.api.ventas import normalizar_pago


@api_bp.route('/pedidos', methods=['POST'])
@jwt_required()
def crear_pedido():
    codigo_vendedor = get_jwt_identity()
    data = request.get_json(silent=True) or {}

    uuid_origen = data.get('uuid')
    items_data = data.get('items', [])
    if not items_data:
        return respuesta_error('items es requerido', 400)

    # Idempotencia
    if uuid_origen:
        existente = BDPedido.query.filter_by(uuid_origen=uuid_origen).first()
        if existente:
            return respuesta_ok({'consecutivo': existente.consecutivo, 'estado': existente.estado})

    try:
        fecha = date.fromisoformat(data.get('fecha', str(date.today())))
    except ValueError:
        return respuesta_error('fecha inválida', 400)

    # Cliente opcional pero, si viene, debe pertenecer al vendedor (Preventa).
    cliente_id = data.get('cliente_id')
    if cliente_id is not None:
        cliente = Cliente.query.filter_by(id=cliente_id).first()
        if not cliente or cliente.codigo_vendedor != codigo_vendedor:
            return respuesta_error('Cliente no encontrado', 404)

    # Total server-side para repartir un pago mixto sin dato de montos.
    total_estimado = 0
    for it in items_data:
        prod = Producto.query.filter_by(codigo=it['producto_cod']).first()
        if prod:
            total_estimado += float(prod.precio) * it['cantidad']
    metodo_pago, monto_efectivo, monto_transferencia = normalizar_pago(data, total_estimado)

    pedido = BDPedido(
        consecutivo=generar_consecutivo(BDPedido, 'PD'),
        codigo_vendedor=codigo_vendedor,
        cliente_id=cliente_id,
        turno_id=data.get('turno_id'),
        fecha=fecha,
        comentarios=data.get('comentarios', ''),
        metodo_pago=metodo_pago,
        monto_efectivo=monto_efectivo,
        monto_transferencia=monto_transferencia,
        estado='pendiente',
        usado=False,
        uuid_origen=uuid_origen
    )

    db.session.add(pedido)
    db.session.flush()

    for it in items_data:
        prod = Producto.query.filter_by(codigo=it['producto_cod']).first()
        if not prod:
            db.session.rollback()
            return respuesta_error(f"Producto {it['producto_cod']} no existe", 400)
        cantidad = it['cantidad']
        subtotal = prod.precio * cantidad
        db.session.add(BDPedidoItem(
            pedido_id=pedido.id,
            producto_cod=prod.codigo,
            cantidad=cantidad,
            precio_unit=prod.precio,
            subtotal=subtotal
        ))

    db.session.commit()
    return respuesta_ok({'consecutivo': pedido.consecutivo, 'estado': pedido.estado})


@api_bp.route('/pedidos', methods=['GET'])
@jwt_required()
def listar_pedidos():
    codigo_vendedor = get_jwt_identity()
    pedidos = BDPedido.query.filter_by(
        codigo_vendedor=codigo_vendedor
    ).order_by(BDPedido.id.desc()).all()

    return respuesta_ok([{
        'consecutivo': p.consecutivo,
        'fecha':       str(p.fecha),
        'cliente_id':  p.cliente_id,
        'cliente_nombre': p.cliente.nombre if p.cliente else '',
        'comentarios': p.comentarios,
        'metodo_pago': p.metodo_pago,
        'estado':      p.estado,
        'usado':       p.usado,
        'total':       float(sum((i.subtotal for i in p.items), 0)),
        'items': [{
            'producto_cod': i.producto_cod,
            'cantidad':     i.cantidad,
            'precio_unit':  float(i.precio_unit),
            'subtotal':     float(i.subtotal)
        } for i in p.items]
    } for p in pedidos])


@api_bp.route('/pedidos/<int:pedido_id>/estado', methods=['PATCH'])
@jwt_required()
def actualizar_estado_pedido(pedido_id):
    """Cumplimiento de pedido: pendiente -> entregado | cancelado."""
    codigo_vendedor = get_jwt_identity()
    data = request.get_json(silent=True) or {}
    nuevo_estado = data.get('estado')
    if nuevo_estado not in ('pendiente', 'entregado', 'cancelado'):
        return respuesta_error('estado inválido', 400)

    pedido = BDPedido.query.filter_by(id=pedido_id, codigo_vendedor=codigo_vendedor).first()
    if not pedido:
        return respuesta_error('Pedido no encontrado', 404)

    pedido.estado = nuevo_estado
    if nuevo_estado == 'entregado':
        pedido.usado = True
    db.session.commit()
    return respuesta_ok({'consecutivo': pedido.consecutivo, 'estado': pedido.estado})
