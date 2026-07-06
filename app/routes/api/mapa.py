from datetime import datetime

from flask import request
from flask_jwt_extended import jwt_required

from app.routes.api import api_bp, respuesta_ok
from app.services.mapa_service import recolectar_mapa_ruta


def _parse_fecha(valor):
    if not valor:
        return None
    try:
        return datetime.strptime(valor, '%Y-%m-%d').date()
    except (TypeError, ValueError):
        return None


@api_bp.route('/mapa/ruta', methods=['GET'])
@jwt_required()
def mapa_ruta():
    """Clientes geolocalizados + recorrido GPS del vendedor para el mapa."""
    fecha = _parse_fecha(request.args.get('fecha'))
    vendedor = (request.args.get('vendedor') or '').strip() or None
    ruta = (request.args.get('ruta_id') or request.args.get('ruta') or '').strip() or None
    turno_id = request.args.get('turno_id', type=int)

    return respuesta_ok(recolectar_mapa_ruta(
        fecha=fecha, vendedor=vendedor, ruta=ruta, turno_id=turno_id
    ))
