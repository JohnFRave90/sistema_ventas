from datetime import datetime, timedelta

from flask import request

from app.routes.api import api_bp, respuesta_ok, respuesta_error, admin_jwt_required
from app.models.vendedor import Vendedor
from app.services.analitica_service import recolectar_resumen, recolectar_breakdown

RANGO_MAX_DIAS = 92

# Campos de recolectar_resumen que tiene sentido sumar a través de varios días.
CAMPOS_ADITIVOS = (
    'total_vendido', 'clientes_visitados', 'excepciones', 'devoluciones',
    'cambios', 'inventario_despachado', 'inventario_vendido', 'inventario_devuelto',
)


def _parse_fecha(valor):
    if not valor:
        return None
    try:
        return datetime.strptime(valor, '%Y-%m-%d').date()
    except (TypeError, ValueError):
        return None


@api_bp.route('/admin/vendedores', methods=['GET'])
@admin_jwt_required
def admin_listar_vendedores():
    """Catálogo de vendedores (código y nombre), para saber qué códigos usar como filtro."""
    vendedores = Vendedor.query.order_by(Vendedor.nombre).all()
    return respuesta_ok([
        {'codigo_vendedor': v.codigo_vendedor, 'nombre': v.nombre}
        for v in vendedores
    ])


@api_bp.route('/admin/analitica/resumen', methods=['GET'])
@admin_jwt_required
def admin_analitica_resumen():
    """Resumen diario. vendedor vacío = agregado de todos los vendedores."""
    fecha = _parse_fecha(request.args.get('fecha'))
    vendedor = (request.args.get('vendedor') or '').strip() or None
    return respuesta_ok(recolectar_resumen(fecha=fecha, vendedor=vendedor))


@api_bp.route('/admin/analitica/breakdown', methods=['GET'])
@admin_jwt_required
def admin_analitica_breakdown():
    """Ranking de ventas por vendedor + top productos vendidos/devueltos de un día."""
    fecha = _parse_fecha(request.args.get('fecha'))
    return respuesta_ok(recolectar_breakdown(fecha=fecha))


@api_bp.route('/admin/analitica/rango', methods=['GET'])
@admin_jwt_required
def admin_analitica_rango():
    """Serie diaria + agregado sobre un rango de fechas (máx. 92 días)."""
    desde = _parse_fecha(request.args.get('desde'))
    hasta = _parse_fecha(request.args.get('hasta'))
    vendedor = (request.args.get('vendedor') or '').strip() or None

    if not desde or not hasta:
        return respuesta_error('desde y hasta son requeridos (YYYY-MM-DD)', 400)
    if hasta < desde:
        return respuesta_error('hasta debe ser >= desde', 400)
    if (hasta - desde).days + 1 > RANGO_MAX_DIAS:
        return respuesta_error(f'rango máximo de {RANGO_MAX_DIAS} días', 400)

    serie = []
    agregado = {campo: 0 for campo in CAMPOS_ADITIVOS}

    dia = desde
    while dia <= hasta:
        resumen = recolectar_resumen(fecha=dia, vendedor=vendedor)
        serie.append(resumen)
        for campo in CAMPOS_ADITIVOS:
            agregado[campo] += resumen[campo]
        dia += timedelta(days=1)

    return respuesta_ok({
        'desde': str(desde),
        'hasta': str(hasta),
        'vendedor': vendedor,
        'serie': serie,
        'agregado': agregado,
    })
