# app/services/mapa_service.py
"""Recolección de datos para el mapa de rutas (capa con acceso a BD).

Devuelve clientes geolocalizados con su estado de visita (color), el recorrido
GPS del vendedor y su última ubicación. Lo consumen tanto la vista web (server-side,
sesión) como el endpoint JWT ``/api/v1/mapa/ruta``.
"""

from datetime import date as _date

from sqlalchemy import func

from app import db
from app.models.cliente import Cliente
from app.models.visita_cliente import BDVisitaCliente
from app.models.turno_ubicacion import BDTurnoUbicacion
from app.models.venta_autoventa import BDVentaAutoventa
from app.models.turno import BDTurno
from app.models.vendedor import Vendedor

# Estado de visita -> (etiqueta, color hex). Solo los estados con dato fiable.
COLOR_PENDIENTE = '#9ca3af'   # gris
COLOR_VISITADO = '#22c55e'    # verde
COLOR_EXCEPCION = '#f97316'   # naranja
COLOR_VENDEDOR = '#8b5cf6'    # morado

# Paleta para distinguir vendedores en el mapa (Regla 6: un color por vendedor,
# la línea GPS usa el mismo color).
PALETA_VENDEDORES = [
    '#3b82f6', '#22c55e', '#f97316', '#8b5cf6',
    '#ef4444', '#06b6d4', '#eab308', '#ec4899',
    '#14b8a6', '#a855f7',
]


def _to_float(value):
    return float(value) if value is not None else None


def colores_por_vendedor():
    """Asigna un color estable de PALETA_VENDEDORES a cada vendedor (orden por
    código), para que el mismo vendedor use siempre el mismo color sin importar
    los filtros aplicados. Usada por el mapa embebido en Clientes TaT."""
    codigos = [v.codigo_vendedor for v in Vendedor.query.order_by(Vendedor.codigo_vendedor).all()]
    return {
        codigo: PALETA_VENDEDORES[i % len(PALETA_VENDEDORES)]
        for i, codigo in enumerate(codigos)
    }


def recolectar_mapa_ruta(fecha=None, vendedor=None, ruta=None, turno_id=None):
    fecha = fecha or _date.today()

    # === DIAGNÓSTICO TEMPORAL (quitar tras resolver el incidente del mapa vacío) ===
    # Imprime el conteo en cada etapa del filtro para ver DÓNDE caen a 0 los clientes.
    import os as _os
    _diag = _os.environ.get('MAPA_DIAG', '1') == '1'
    if _diag:
        _total = Cliente.query.count()
        _con_coords = Cliente.query.filter(
            Cliente.latitud.isnot(None), Cliente.longitud.isnot(None)
        ).count()
        print(f'[MAPA DIAG] fecha={fecha} vendedor={vendedor!r} ruta={ruta!r} turno_id={turno_id!r}', flush=True)
        print(f'[MAPA DIAG] clientes TOTAL en BD            = {_total}', flush=True)
        print(f'[MAPA DIAG] clientes CON coordenadas        = {_con_coords}', flush=True)

    # --- Clientes geolocalizados ---
    cli_query = Cliente.query.filter(
        Cliente.latitud.isnot(None), Cliente.longitud.isnot(None)
    )
    if vendedor:
        cli_query = cli_query.filter(Cliente.codigo_vendedor == vendedor)
        if _diag:
            print(f'[MAPA DIAG] tras filtro vendedor={vendedor!r}  = {cli_query.count()}', flush=True)
    if ruta:
        cli_query = cli_query.filter(Cliente.ruta == ruta)
        if _diag:
            print(f'[MAPA DIAG] tras filtro ruta={ruta!r}          = {cli_query.count()}', flush=True)
    clientes = cli_query.order_by(Cliente.ruta, Cliente.orden_visita).all()

    cliente_ids = [c.id for c in clientes]

    if _diag:
        print(f'[MAPA DIAG] CLIENTES FINALES (con coords + filtros) = {len(clientes)}', flush=True)

    # Visitas del día por cliente (la más reciente gana).
    visitas_por_cliente = {}
    if cliente_ids:
        vis_query = BDVisitaCliente.query.filter(
            BDVisitaCliente.cliente_id.in_(cliente_ids),
            BDVisitaCliente.fecha_visita == fecha,
        )
        if vendedor:
            vis_query = vis_query.filter(BDVisitaCliente.codigo_vendedor == vendedor)
        if turno_id:
            vis_query = vis_query.filter(BDVisitaCliente.turno_id == turno_id)
        for v in vis_query.order_by(BDVisitaCliente.id.asc()).all():
            visitas_por_cliente[v.cliente_id] = v

    # Venta (autoventa) por cliente en la fecha.
    ventas_por_cliente = {}
    if cliente_ids:
        filas = db.session.query(
            BDVentaAutoventa.cliente_id,
            func.coalesce(func.sum(BDVentaAutoventa.total), 0),
        ).filter(
            BDVentaAutoventa.cliente_id.in_(cliente_ids),
            BDVentaAutoventa.fecha == fecha,
        ).group_by(BDVentaAutoventa.cliente_id).all()
        ventas_por_cliente = {cid: float(total or 0) for cid, total in filas}

    if _diag:
        print(f'[MAPA DIAG] visitas del día encontradas    = {len(visitas_por_cliente)}', flush=True)

    items = []
    for c in clientes:
        visita = visitas_por_cliente.get(c.id)
        estado = 'pendiente'
        color = COLOR_PENDIENTE
        hora_llegada = None
        if visita is not None:
            if visita.estado == 'excepcion':
                estado, color = 'excepcion', COLOR_EXCEPCION
            elif visita.estado == 'completada':
                estado, color = 'visitado', COLOR_VISITADO
            else:
                estado, color = visita.estado, COLOR_PENDIENTE
            hora_llegada = visita.checkin_at.isoformat() if visita.checkin_at else None

        items.append({
            'cliente_id': c.id,
            'nombre': c.nombre,
            'nombre_tienda': c.nombre_tienda or '',
            'direccion': c.direccion or '',
            'barrio': c.barrio or '',
            'vendedor': c.codigo_vendedor,
            'ruta': c.ruta or '',
            'lat': _to_float(c.latitud),
            'lng': _to_float(c.longitud),
            'estado': estado,
            'color': color,
            'hora_llegada': hora_llegada,
            'venta': ventas_por_cliente.get(c.id, 0),
        })

    # --- Ubicaciones de vendedores: última posición + recorrido ---
    # Regla 1: en "Todos" se muestra la ÚLTIMA ubicación de CADA vendedor con GPS.
    # Regla 2: la "última ubicación" es la MÁS RECIENTE registrada, SIN filtrar por
    #   fecha (antes se filtraba por captured_at == fecha y, como los puntos eran de
    #   otro día, "Todos" salía vacío — esa era la causa del mapa sin vendedores).
    # Regla 4/5: el recorrido (polyline) solo se dibuja cuando hay vendedor/turno
    #   enfocado; en "Todos" solo el último punto, sin saturar.
    enfocado = bool(vendedor or turno_id)

    if turno_id:
        _t = BDTurno.query.get(turno_id)
        codigos = [_t.codigo_vendedor] if _t else []
    elif vendedor:
        codigos = [vendedor]
    else:
        # "Todos": TODOS los vendedores con al menos un punto GPS (sin filtro de fecha).
        codigos = [
            r[0] for r in db.session.query(BDTurnoUbicacion.codigo_vendedor)
            .distinct().all()
        ]

    if _diag:
        print(f'[MAPA DIAG] VENDEDORES GPS (codigos) = {codigos}', flush=True)
        print(f'[MAPA DIAG] TOTAL VENDEDORES GPS     = {len(codigos)}', flush=True)

    nombres_vend = {}
    if codigos:
        nombres_vend = {
            v.codigo_vendedor: v.nombre
            for v in Vendedor.query.filter(Vendedor.codigo_vendedor.in_(codigos)).all()
        }

    vendedores_mapa = []
    for idx, code in enumerate(sorted(codigos)):
        # Base: puntos del vendedor (y del turno si está filtrado). SIN filtro de fecha,
        # para que la última ubicación conocida siempre sea visible.
        base_q = BDTurnoUbicacion.query.filter(BDTurnoUbicacion.codigo_vendedor == code)
        if turno_id:
            base_q = base_q.filter(BDTurnoUbicacion.turno_id == turno_id)

        ultima = base_q.order_by(BDTurnoUbicacion.captured_at.desc()).first()
        if not ultima:
            continue
        puntos_total = base_q.count()

        color = PALETA_VENDEDORES[idx % len(PALETA_VENDEDORES)]

        # Recorrido (polyline) SOLO si está enfocado. Para un vendedor sin turno, se
        # limita al turno de su última ubicación (su jornada más reciente), evitando
        # mezclar turnos/días. Para un turno filtrado, es ese turno.
        recorridos = []
        if enfocado:
            rec_q = base_q
            if not turno_id and ultima.turno_id is not None:
                rec_q = rec_q.filter(BDTurnoUbicacion.turno_id == ultima.turno_id)
            pts = rec_q.order_by(BDTurnoUbicacion.captured_at.asc()).all()
            coords = [[_to_float(p.latitud), _to_float(p.longitud)] for p in pts]
            if len(coords) >= 2:
                recorridos = [coords]

        # Stats para el popup (de la fecha seleccionada, o del turno si está filtrado).
        vis_q = BDVisitaCliente.query.filter(
            BDVisitaCliente.codigo_vendedor == code,
            BDVisitaCliente.fecha_visita == fecha,
            BDVisitaCliente.estado == 'completada',
        )
        ven_q = db.session.query(func.coalesce(func.sum(BDVentaAutoventa.total), 0)).filter(
            BDVentaAutoventa.codigo_vendedor == code,
            BDVentaAutoventa.fecha == fecha,
        )
        if turno_id:
            vis_q = vis_q.filter(BDVisitaCliente.turno_id == turno_id)
            ven_q = ven_q.filter(BDVentaAutoventa.turno_id == turno_id)

        vendedores_mapa.append({
            'codigo': code,
            'nombre': nombres_vend.get(code, code),
            'color': color,
            'ultima': {
                'lat': _to_float(ultima.latitud),
                'lng': _to_float(ultima.longitud),
                'captured_at': ultima.captured_at.isoformat() if ultima.captured_at else None,
                'turno_id': ultima.turno_id,
            },
            'puntos': puntos_total,
            'recorridos': recorridos,
            'clientes_visitados': vis_q.count(),
            'ventas': float(ven_q.scalar() or 0),
        })

    if _diag:
        print(f'[MAPA DIAG] vendedores EN MAPA (con ubicación) = {len(vendedores_mapa)} (enfocado={enfocado})', flush=True)

    return {
        'fecha': str(fecha),
        'vendedor': vendedor or None,
        'ruta': ruta or None,
        'turno_id': turno_id,
        'clientes': items,
        'vendedores': vendedores_mapa,
    }
