from datetime import datetime

from flask import request
from flask_jwt_extended import jwt_required

from app.routes.api import api_bp, respuesta_ok, respuesta_error
from app.models.despachos import BDDespacho
from app.services.despachos_service import (
    recolectar_diferencias,
    estado_de_despacho,
    _map_items_despacho,
)


def _parse_fecha(valor):
    if not valor:
        return None
    try:
        return datetime.strptime(valor, '%Y-%m-%d').date()
    except (TypeError, ValueError):
        return None


def _serializar_despacho(despacho):
    return {
        'id': despacho.id,
        'codigo_origen': despacho.codigo_origen,
        'tipo_origen': despacho.tipo_origen,
        'codigo_vendedor': despacho.vendedor_cod,
        'fecha': str(despacho.fecha),
        'despachado': bool(despacho.despachado),
        'turno_id': despacho.turno_id,
        'estado': estado_de_despacho(despacho),
        'items_count': len(despacho.items),
    }


@api_bp.route('/despachos', methods=['GET'])
@jwt_required()
def listar_despachos_api():
    """Lista despachos con estado derivado. Filtros: fecha, vendedor, ruta(no aplica), estado."""
    query = BDDespacho.query

    fecha = _parse_fecha(request.args.get('fecha'))
    if fecha is not None:
        query = query.filter(BDDespacho.fecha == fecha)

    vendedor = (request.args.get('vendedor') or '').strip()
    if vendedor:
        query = query.filter(BDDespacho.vendedor_cod == vendedor)

    despachos = query.order_by(BDDespacho.fecha.desc(), BDDespacho.id.desc()).limit(200).all()

    estado_filtro = (request.args.get('estado') or '').strip()
    data = [_serializar_despacho(d) for d in despachos]
    if estado_filtro:
        data = [d for d in data if d['estado'] == estado_filtro]

    return respuesta_ok({'despachos': data, 'count': len(data)})


@api_bp.route('/despachos/<int:did>/items', methods=['GET'])
@jwt_required()
def despacho_items_api(did):
    despacho = BDDespacho.query.get(did)
    if not despacho:
        return respuesta_error('Despacho no encontrado', 404)

    items = [{
        'producto_cod': i.producto_cod,
        'cantidad_pedida': i.cantidad_pedida,
        'cantidad': i.cantidad,
        'precio_unitario': float(i.precio_unitario or 0),
        'subtotal': float(i.subtotal or 0),
    } for i in despacho.items]

    return respuesta_ok({
        'despacho_id': despacho.id,
        'codigo_origen': despacho.codigo_origen,
        'estado': estado_de_despacho(despacho),
        'items': items,
    })


@api_bp.route('/despachos/<int:did>/diferencias', methods=['GET'])
@jwt_required()
def despacho_diferencias_api(did):
    """Diferencias: despachado sistema vs confirmado app vs vendido/devuelto/sobrante."""
    despacho = BDDespacho.query.get(did)
    if not despacho:
        return respuesta_error('Despacho no encontrado', 404)

    return respuesta_ok(recolectar_diferencias(despacho))
