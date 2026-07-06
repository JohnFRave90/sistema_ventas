from datetime import datetime

from flask import request
from flask_jwt_extended import jwt_required

from app.routes.api import api_bp, respuesta_ok
from app.services.analitica_service import recolectar_resumen


def _parse_fecha(valor):
    if not valor:
        return None
    try:
        return datetime.strptime(valor, '%Y-%m-%d').date()
    except (TypeError, ValueError):
        return None


@api_bp.route('/analitica/resumen', methods=['GET'])
@jwt_required()
def analitica_resumen():
    """Resumen diario: ventas, visitas, devoluciones, cambios e inventario."""
    fecha = _parse_fecha(request.args.get('fecha'))
    vendedor = (request.args.get('vendedor') or '').strip() or None
    return respuesta_ok(recolectar_resumen(fecha=fecha, vendedor=vendedor))
