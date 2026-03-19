from datetime import date
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.routes.api import api_bp, respuesta_ok
from app.models.despachos import BDDespacho, BDDespachoItem
from app.models.devoluciones import BDDevolucion
from app.models.devolucion_item import BDDevolucionItem
from app.models.producto import Producto


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
