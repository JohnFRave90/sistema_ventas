# app/routes/analitica.py
from datetime import date, datetime

from flask import Blueprint, render_template, request
from flask_login import login_required

from app.models.vendedor import Vendedor
from app.services.analitica_service import recolectar_resumen, recolectar_breakdown
from app.utils.roles import rol_requerido

analitica_bp = Blueprint('analitica', __name__)


def _parse_fecha(valor):
    if not valor:
        return date.today()
    try:
        return datetime.strptime(valor, '%Y-%m-%d').date()
    except (TypeError, ValueError):
        return date.today()


@analitica_bp.route('/analitica', methods=['GET'])
@login_required
@rol_requerido('semiadmin', 'administrador')
def ver_analitica():
    """Cards de analítica diaria. Filtros server-side por GET (fecha, vendedor)."""
    fecha = _parse_fecha(request.args.get('fecha'))
    vendedor = (request.args.get('vendedor') or '').strip() or None

    data = recolectar_resumen(fecha=fecha, vendedor=vendedor)
    breakdown = recolectar_breakdown(fecha=fecha)
    vendedores = Vendedor.query.order_by(Vendedor.nombre).all()

    return render_template(
        'analitica/index.html',
        data=data,
        breakdown=breakdown,
        vendedores=vendedores,
        filtro_fecha=str(fecha),
        filtro_vendedor=vendedor or '',
    )
