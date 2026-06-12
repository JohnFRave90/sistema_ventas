from datetime import date, datetime
from typing import Optional

from flask import request
from flask_jwt_extended import get_jwt_identity, jwt_required
from sqlalchemy import and_, func, or_

from app import db
from app.models.despachos import BDDespacho, BDDespachoItem
from app.models.devolucion_item import BDDevolucionItem
from app.models.devoluciones import BDDevolucion
from app.models.turno import BDTurno
from app.models.venta_autoventa import BDVentaAutoventa, BDVentaAutoventaItem
from app.models.visita_cliente import BDVisitaCliente
from app.routes.api import api_bp, respuesta_error, respuesta_ok


def _parse_date(value: Optional[str]) -> date:
    if not value:
        return date.today()
    return date.fromisoformat(value)


def _parse_time(value: Optional[str], default_now: bool = True):
    if value:
        return datetime.strptime(value, '%H:%M:%S').time() if len(value) == 8 else datetime.strptime(value, '%H:%M').time()
    if default_now:
        return datetime.now().time().replace(microsecond=0)
    return None


def _serializar_turno(turno: BDTurno):
    return {
        'id': turno.id,
        'codigo_vendedor': turno.codigo_vendedor,
        'fecha': str(turno.fecha),
        'turno_numero': turno.turno_numero,
        'hora_inicio': str(turno.hora_inicio) if turno.hora_inicio else None,
        'hora_fin': str(turno.hora_fin) if turno.hora_fin else None,
        'estado': turno.estado,
        'comentarios': turno.comentarios,
    }


def _obtener_turno_referencia(codigo_vendedor: str) -> Optional[BDTurno]:
    hoy = date.today()
    turno_hoy = BDTurno.query.filter_by(
        codigo_vendedor=codigo_vendedor,
        fecha=hoy,
    ).order_by(BDTurno.id.desc()).first()
    if turno_hoy:
        return turno_hoy

    return BDTurno.query.filter_by(codigo_vendedor=codigo_vendedor).order_by(BDTurno.id.desc()).first()


def _filtro_turno_o_fecha(turno: BDTurno, turno_col, fecha_col):
    return or_(
        turno_col == turno.id,
        and_(turno_col.is_(None), fecha_col == turno.fecha),
    )


@api_bp.route('/turnos/inicio', methods=['POST'])
@jwt_required()
def iniciar_turno():
    codigo_vendedor = get_jwt_identity()
    data = request.get_json(silent=True) or {}

    try:
        fecha = _parse_date(data.get('fecha'))
        turno_numero_raw = data.get('turno_numero')
        turno_numero = int(turno_numero_raw) if turno_numero_raw is not None else None
        hora_inicio = _parse_time(data.get('hora_inicio'))
    except (ValueError, TypeError):
        return respuesta_error('Datos invalidos para iniciar turno', 400)

    abierto = BDTurno.query.filter_by(codigo_vendedor=codigo_vendedor, estado='abierto').first()
    if abierto:
        return respuesta_ok(_serializar_turno(abierto))

    existentes_vendedor = BDTurno.query.filter_by(
        codigo_vendedor=codigo_vendedor,
    ).order_by(BDTurno.turno_numero.desc(), BDTurno.id.desc()).all()

    if turno_numero is None:
        turno_numero = (existentes_vendedor[0].turno_numero + 1) if existentes_vendedor else 1

    existente = next((item for item in existentes_vendedor if item.turno_numero == turno_numero), None)
    if existente:
        # Si ya existe un turno cerrado con ese número, crear el siguiente libre de forma automática.
        if existente.estado == 'abierto':
            return respuesta_ok(_serializar_turno(existente))
        turno_numero = (existentes_vendedor[0].turno_numero + 1) if existentes_vendedor else turno_numero

    turno = BDTurno(
        codigo_vendedor=codigo_vendedor,
        fecha=fecha,
        turno_numero=turno_numero,
        hora_inicio=hora_inicio,
        estado='abierto',
        comentarios=data.get('comentarios'),
    )
    db.session.add(turno)
    db.session.commit()

    return respuesta_ok(_serializar_turno(turno), 201)


@api_bp.route('/turnos/<int:turno_id>/cierre', methods=['POST'])
@jwt_required()
def cerrar_turno(turno_id):
    codigo_vendedor = get_jwt_identity()
    data = request.get_json(silent=True) or {}

    turno = BDTurno.query.filter_by(id=turno_id, codigo_vendedor=codigo_vendedor).first()
    if not turno:
        return respuesta_error('Turno no encontrado', 404)

    if turno.estado == 'cerrado':
        return respuesta_ok(_serializar_turno(turno))

    try:
        hora_fin = _parse_time(data.get('hora_fin'))
    except ValueError:
        return respuesta_error('hora_fin invalida. Usa HH:MM o HH:MM:SS', 400)

    turno.hora_fin = hora_fin
    turno.estado = 'cerrado'

    comentarios = data.get('comentarios')
    if comentarios:
        if turno.comentarios:
            turno.comentarios = f"{turno.comentarios}\n{comentarios}"
        else:
            turno.comentarios = comentarios

    db.session.commit()
    return respuesta_ok(_serializar_turno(turno))


@api_bp.route('/turnos/actual', methods=['GET'])
@jwt_required()
def turno_actual():
    codigo_vendedor = get_jwt_identity()
    turno = BDTurno.query.filter_by(codigo_vendedor=codigo_vendedor, estado='abierto').order_by(BDTurno.id.desc()).first()

    if not turno:
        return respuesta_ok(None)

    return respuesta_ok(_serializar_turno(turno))


@api_bp.route('/turnos/resumen', methods=['GET'])
@jwt_required()
def resumen_turno_actual():
    codigo_vendedor = get_jwt_identity()
    turno = _obtener_turno_referencia(codigo_vendedor)

    if not turno:
        return respuesta_ok({
            'turno_id': None,
            'fecha': str(date.today()),
            'completed_visits': 0,
            'checked_stock_items': 0,
            'units_loaded': 0,
            'units_sold': 0,
            'returns_handled': 0,
            'units_remaining': 0,
        })

    visitas_query = db.session.query(
        func.count(func.distinct(BDVisitaCliente.cliente_id))
    ).filter(
        BDVisitaCliente.codigo_vendedor == codigo_vendedor,
        BDVisitaCliente.estado.in_(['completada', 'excepcion']),
        _filtro_turno_o_fecha(turno, BDVisitaCliente.turno_id, BDVisitaCliente.fecha_visita),
    )

    despachos_query = db.session.query(
        func.coalesce(func.sum(BDDespachoItem.cantidad), 0),
        func.count(func.distinct(BDDespachoItem.producto_cod)),
    ).join(
        BDDespacho,
        BDDespacho.id == BDDespachoItem.despacho_id,
    ).filter(
        BDDespacho.vendedor_cod == codigo_vendedor,
        BDDespacho.despachado.is_(True),
        _filtro_turno_o_fecha(turno, BDDespacho.turno_id, BDDespacho.fecha),
    )

    ventas_query = db.session.query(
        func.coalesce(func.sum(BDVentaAutoventaItem.cantidad), 0)
    ).join(
        BDVentaAutoventa,
        BDVentaAutoventa.id == BDVentaAutoventaItem.autoventa_id,
    ).filter(
        BDVentaAutoventa.codigo_vendedor == codigo_vendedor,
        _filtro_turno_o_fecha(turno, BDVentaAutoventa.turno_id, BDVentaAutoventa.fecha),
    )

    # Contar SOLO las devoluciones ligadas a este turno (no todas las del día).
    # Antes se filtraba por fecha, lo que sumaba devoluciones de otros turnos, las
    # generadas por cambios y datos de prueba acumulados, inflando units_remaining.
    devoluciones_query = db.session.query(
        func.coalesce(func.sum(BDDevolucionItem.cantidad), 0)
    ).join(
        BDDevolucion,
        BDDevolucion.id == BDDevolucionItem.devolucion_id,
    ).filter(
        BDDevolucion.codigo_vendedor == codigo_vendedor,
        BDDevolucion.turno_id == turno.id,
    )

    completed_visits = int(visitas_query.scalar() or 0)
    units_loaded_raw, checked_stock_items_raw = despachos_query.first() or (0, 0)
    units_loaded = int(units_loaded_raw or 0)
    checked_stock_items = int(checked_stock_items_raw or 0)
    units_sold = int(ventas_query.scalar() or 0)
    returns_handled = int(devoluciones_query.scalar() or 0)
    units_remaining = max(0, units_loaded - units_sold + returns_handled)

    return respuesta_ok({
        'turno_id': turno.id,
        'fecha': str(turno.fecha),
        'completed_visits': completed_visits,
        'checked_stock_items': checked_stock_items,
        'units_loaded': units_loaded,
        'units_sold': units_sold,
        'returns_handled': returns_handled,
        'units_remaining': units_remaining,
    })
