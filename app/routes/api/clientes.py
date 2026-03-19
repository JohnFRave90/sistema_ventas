from flask_jwt_extended import jwt_required, get_jwt_identity
from app.routes.api import api_bp, respuesta_ok, respuesta_error
from app.models.cliente import Cliente
from app.models.venta_autoventa import BDVentaAutoventa


def _serializar_cliente(c):
    return {
        'id':            c.id,
        'codigo_cliente': c.codigo_cliente,
        'nombre':        c.nombre,
        'telefono':      c.telefono,
        'whatsapp':      c.whatsapp,
        'direccion':     c.direccion,
        'ciudad':        c.ciudad,
        'latitud':       float(c.latitud) if c.latitud else None,
        'longitud':      float(c.longitud) if c.longitud else None,
        'ruta':          c.ruta,
        'orden_visita':  c.orden_visita
    }


@api_bp.route('/clientes', methods=['GET'])
@jwt_required()
def listar_clientes():
    codigo_vendedor = get_jwt_identity()
    clientes = Cliente.query.filter_by(
        codigo_vendedor=codigo_vendedor, activo=True
    ).order_by(Cliente.ruta, Cliente.orden_visita).all()
    return respuesta_ok([_serializar_cliente(c) for c in clientes])


@api_bp.route('/clientes/<int:cliente_id>', methods=['GET'])
@jwt_required()
def detalle_cliente(cliente_id):
    codigo_vendedor = get_jwt_identity()
    cliente = Cliente.query.filter_by(id=cliente_id).first()
    if not cliente or cliente.codigo_vendedor != codigo_vendedor:
        return respuesta_error('Cliente no encontrado', 404)

    ultimas_ventas = BDVentaAutoventa.query.filter_by(
        cliente_id=cliente_id
    ).order_by(BDVentaAutoventa.id.desc()).limit(10).all()

    historial = [{
        'consecutivo': v.consecutivo,
        'fecha':       str(v.fecha),
        'total':       float(v.total) if v.total else 0,
        'items': [{
            'producto_cod': i.producto_cod,
            'nombre':       i.producto.nombre if i.producto else i.producto_cod,
            'cantidad':     i.cantidad,
            'precio_unit':  float(i.precio_unit),
            'subtotal':     float(i.subtotal)
        } for i in v.items]
    } for v in ultimas_ventas]

    data = _serializar_cliente(cliente)
    data['historial'] = historial
    return respuesta_ok(data)
