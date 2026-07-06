# app/routes/mapa.py
from datetime import date, datetime

from flask import Blueprint, render_template, request
from flask_login import login_required

from app import db
from app.models.cliente import Cliente
from app.models.turno import BDTurno
from app.models.vendedor import Vendedor
from app.services.mapa_service import recolectar_mapa_ruta
from app.utils.roles import rol_requerido

mapa_bp = Blueprint('mapa', __name__)


def _parse_fecha(valor):
    if not valor:
        return date.today()
    try:
        return datetime.strptime(valor, '%Y-%m-%d').date()
    except (TypeError, ValueError):
        return date.today()


@mapa_bp.route('/mapa', methods=['GET'])
@login_required
@rol_requerido('semiadmin', 'administrador')
def ver_mapa():
    """Mapa de rutas (Leaflet + OpenStreetMap). Filtros server-side por GET."""
    fecha = _parse_fecha(request.args.get('fecha'))
    _vendedor_raw = request.args.get('vendedor')
    vendedor = (_vendedor_raw or '').strip() or None
    ruta = (request.args.get('ruta') or '').strip() or None
    turno_id = request.args.get('turno_id', type=int)

    # === DIAGNÓSTICO TEMPORAL: evidencia del valor de vendedor (Todos → None) ===
    import os as _os
    if _os.environ.get('MAPA_DIAG', '1') == '1':
        print(f'[MAPA DIAG][ROUTE] vendedor RECIBIDO={_vendedor_raw!r} NORMALIZADO={vendedor!r} (Todos => None)', flush=True)

    data = recolectar_mapa_ruta(fecha=fecha, vendedor=vendedor, ruta=ruta, turno_id=turno_id)

    # === DIAGNÓSTICO TEMPORAL (quitar tras resolver el mapa vacío) ===
    import os as _os
    if _os.environ.get('MAPA_DIAG', '1') == '1':
        print(f'[MAPA DIAG][ROUTE] filtros: fecha={fecha} vendedor={vendedor!r} ruta={ruta!r} turno_id={turno_id!r}', flush=True)
        print(f'[MAPA DIAG][ROUTE] CLIENTES ENVIADOS AL TEMPLATE = {len(data["clientes"])}', flush=True)

    vendedores = Vendedor.query.order_by(Vendedor.nombre).all()

    # --- Jerarquía de negocio: Vendedor → Rutas → Turnos (NO usuario) ---
    # Rutas agrupadas por vendedor (para que el selector de ruta DEPENDA del vendedor).
    ruta_rows = db.session.query(Cliente.codigo_vendedor, Cliente.ruta).filter(
        Cliente.ruta.isnot(None), Cliente.ruta != ''
    ).distinct().all()
    rutas_por_vendedor = {}
    rutas_set = set()
    for cod, r in ruta_rows:
        rutas_por_vendedor.setdefault(cod, [])
        if r not in rutas_por_vendedor[cod]:
            rutas_por_vendedor[cod].append(r)
        rutas_set.add(r)
    for cod in rutas_por_vendedor:
        rutas_por_vendedor[cod].sort()
    rutas_all = sorted(rutas_set)

    # Turnos recientes (todos los vendedores) agrupados por vendedor para el selector.
    turnos_recientes = BDTurno.query.order_by(
        BDTurno.fecha.desc(), BDTurno.id.desc()
    ).limit(200).all()
    turnos_data = [{
        'id': t.id, 'fecha': str(t.fecha), 'turno_numero': t.turno_numero,
        'estado': t.estado, 'codigo_vendedor': t.codigo_vendedor,
    } for t in turnos_recientes]
    turnos_por_vendedor = {}
    for t in turnos_data:
        turnos_por_vendedor.setdefault(t['codigo_vendedor'], []).append(t)

    # Opciones iniciales del render: dependientes del vendedor seleccionado (o globales en "Todos").
    rutas = rutas_por_vendedor.get(vendedor, []) if vendedor else rutas_all
    turnos = turnos_por_vendedor.get(vendedor, []) if vendedor else turnos_data

    if _os.environ.get('MAPA_DIAG', '1') == '1':
        print(f'[MAPA DIAG][ROUTE] vendedores={len(vendedores)} rutas(de vendedor)={len(rutas)} turnos(de vendedor)={len(turnos)}', flush=True)

    return render_template(
        'mapa/index.html',
        data=data,
        vendedores=vendedores,
        turnos=turnos,
        rutas=rutas,
        rutas_por_vendedor=rutas_por_vendedor,
        rutas_all=rutas_all,
        turnos_por_vendedor=turnos_por_vendedor,
        turnos_all=turnos_data,
        filtro_fecha=str(fecha),
        filtro_vendedor=vendedor or '',
        filtro_ruta=ruta or '',
        filtro_turno_id=turno_id or '',
    )
