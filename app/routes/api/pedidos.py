from datetime import date
from flask import request
from flask_jwt_extended import jwt_required, get_jwt_identity
from app import db
from app.routes.api import api_bp, respuesta_ok, respuesta_error
from app.models.pedidos import BDPedido
from app.models.pedido_item import BDPedidoItem
from app.models.producto import Producto
from app.utils.documentos import generar_consecutivo


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
            return respuesta_ok({'consecutivo': existente.consecutivo})

    try:
        fecha = date.fromisoformat(data.get('fecha', str(date.today())))
    except ValueError:
        return respuesta_error('fecha inválida', 400)

    pedido = BDPedido(
        consecutivo=generar_consecutivo(BDPedido, 'PD'),
        codigo_vendedor=codigo_vendedor,
        fecha=fecha,
        comentarios=data.get('comentarios', ''),
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
    return respuesta_ok({'consecutivo': pedido.consecutivo})


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
        'comentarios': p.comentarios,
        'usado':       p.usado,
        'items': [{
            'producto_cod': i.producto_cod,
            'cantidad':     i.cantidad,
            'precio_unit':  float(i.precio_unit),
            'subtotal':     float(i.subtotal)
        } for i in p.items]
    } for p in pedidos])
