from datetime import date, datetime
from typing import Optional

from flask import request
from flask_jwt_extended import get_jwt_identity, jwt_required

from app import db
from app.models.cliente import Cliente
from app.models.turno import BDTurno
from app.models.visita_cliente import BDVisitaCliente, BDVisitaExcepcion
from app.routes.api import api_bp, respuesta_error, respuesta_ok


def _parse_date(value: Optional[str]) -> date:
    if not value:
        return date.today()
    return date.fromisoformat(value)


def _to_float_or_none(value):
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _serializar_visita(v: BDVisitaCliente, transacciones=None):
    data = {
        'id': v.id,
        'cliente_id': v.cliente_id,
        'codigo_vendedor': v.codigo_vendedor,
        'turno_id': v.turno_id,
        'fecha_visita': str(v.fecha_visita),
        'checkin_at': v.checkin_at.isoformat() if v.checkin_at else None,
        'checkout_at': v.checkout_at.isoformat() if v.checkout_at else None,
        'estado': v.estado,
        'notas': v.notas,
        'lat_checkin': float(v.lat_checkin) if v.lat_checkin is not None else None,
        'lng_checkin': float(v.lng_checkin) if v.lng_checkin is not None else None,
        'lat_checkout': float(v.lat_checkout) if v.lat_checkout is not None else None,
        'lng_checkout': float(v.lng_checkout) if v.lng_checkout is not None else None,
    }
    if transacciones is not None:
        data['transacciones'] = transacciones
    return data


def _serializar_excepcion(ex: BDVisitaExcepcion):
    return {
        'id': ex.id,
        'visita_id': ex.visita_id,
        'cliente_id': ex.cliente_id,
        'codigo_vendedor': ex.codigo_vendedor,
        'tipo': ex.tipo,
        'razon': ex.razon,
        'requiere_seguimiento': ex.requiere_seguimiento,
        'created_at': ex.created_at.isoformat() if ex.created_at else None,
    }


@api_bp.route('/clientes/<int:cliente_id>/visita/checkin', methods=['POST'])
@jwt_required()
def checkin_visita(cliente_id):
    codigo_vendedor = get_jwt_identity()
    data = request.get_json(silent=True) or {}

    cliente = Cliente.query.filter_by(id=cliente_id).first()
    if not cliente or cliente.codigo_vendedor != codigo_vendedor:
        return respuesta_error('Cliente no encontrado', 404)

    try:
        fecha_visita = _parse_date(data.get('fecha_visita'))
    except ValueError:
        return respuesta_error('fecha_visita invalida. Usa YYYY-MM-DD', 400)

    visita_activa = BDVisitaCliente.query.filter_by(
        cliente_id=cliente_id,
        codigo_vendedor=codigo_vendedor,
        fecha_visita=fecha_visita,
        estado='en_progreso',
    ).order_by(BDVisitaCliente.id.desc()).first()
    if visita_activa:
        return respuesta_ok(_serializar_visita(visita_activa))

    turno_id = data.get('turno_id')
    if turno_id is not None:
        turno = BDTurno.query.filter_by(id=turno_id, codigo_vendedor=codigo_vendedor).first()
        if not turno:
            return respuesta_error('turno_id no corresponde al vendedor', 400)

    visita = BDVisitaCliente(
        cliente_id=cliente_id,
        codigo_vendedor=codigo_vendedor,
        turno_id=turno_id,
        fecha_visita=fecha_visita,
        checkin_at=datetime.now(),
        estado='en_progreso',
        notas=data.get('notas'),
        lat_checkin=_to_float_or_none(data.get('latitud')),
        lng_checkin=_to_float_or_none(data.get('longitud')),
    )
    db.session.add(visita)
    db.session.commit()

    return respuesta_ok(_serializar_visita(visita), 201)


@api_bp.route('/clientes/<int:cliente_id>/visita/checkout', methods=['POST'])
@jwt_required()
def checkout_visita(cliente_id):
    codigo_vendedor = get_jwt_identity()
    data = request.get_json(silent=True) or {}

    cliente = Cliente.query.filter_by(id=cliente_id).first()
    if not cliente or cliente.codigo_vendedor != codigo_vendedor:
        return respuesta_error('Cliente no encontrado', 404)

    visita_id = data.get('visita_id')
    if visita_id:
        visita = BDVisitaCliente.query.filter_by(
            id=visita_id,
            cliente_id=cliente_id,
            codigo_vendedor=codigo_vendedor,
        ).first()
    else:
        visita = BDVisitaCliente.query.filter_by(
            cliente_id=cliente_id,
            codigo_vendedor=codigo_vendedor,
            estado='en_progreso',
        ).order_by(BDVisitaCliente.id.desc()).first()

    if not visita:
        return respuesta_error('No hay visita activa para cerrar', 404)

    visita.estado = 'completada'
    visita.checkout_at = datetime.now()
    visita.lat_checkout = _to_float_or_none(data.get('latitud'))
    visita.lng_checkout = _to_float_or_none(data.get('longitud'))

    notas = data.get('notas')
    if notas:
        if visita.notas:
            visita.notas = f"{visita.notas}\n{notas}"
        else:
            visita.notas = notas

    db.session.commit()
    return respuesta_ok(_serializar_visita(visita))


@api_bp.route('/clientes/<int:cliente_id>/visita/excepcion', methods=['POST'])
@jwt_required()
def registrar_excepcion_visita(cliente_id):
    codigo_vendedor = get_jwt_identity()
    data = request.get_json(silent=True) or {}

    cliente = Cliente.query.filter_by(id=cliente_id).first()
    if not cliente or cliente.codigo_vendedor != codigo_vendedor:
        return respuesta_error('Cliente no encontrado', 404)

    razon = (data.get('razon') or '').strip()
    if not razon:
        return respuesta_error('razon es requerida', 400)

    visita_id = data.get('visita_id')
    if visita_id:
        visita = BDVisitaCliente.query.filter_by(
            id=visita_id,
            cliente_id=cliente_id,
            codigo_vendedor=codigo_vendedor,
        ).first()
        if not visita:
            return respuesta_error('visita_id no encontrada para este cliente', 404)
    else:
        visita = BDVisitaCliente.query.filter_by(
            cliente_id=cliente_id,
            codigo_vendedor=codigo_vendedor,
            estado='en_progreso',
        ).order_by(BDVisitaCliente.id.desc()).first()

    if not visita:
        visita = BDVisitaCliente(
            cliente_id=cliente_id,
            codigo_vendedor=codigo_vendedor,
            turno_id=data.get('turno_id'),
            fecha_visita=date.today(),
            checkin_at=datetime.now(),
            checkout_at=datetime.now(),
            estado='excepcion',
            notas=razon,
        )
        db.session.add(visita)
        db.session.flush()
    else:
        visita.estado = 'excepcion'
        visita.checkout_at = datetime.now()
        if razon:
            if visita.notas:
                visita.notas = f"{visita.notas}\n{razon}"
            else:
                visita.notas = razon

    ex = BDVisitaExcepcion(
        visita_id=visita.id if visita else None,
        cliente_id=cliente_id,
        codigo_vendedor=codigo_vendedor,
        tipo=(data.get('tipo') or 'otro').strip() or 'otro',
        razon=razon,
        requiere_seguimiento=bool(data.get('requiere_seguimiento', False)),
    )
    db.session.add(ex)
    db.session.commit()

    return respuesta_ok({
        "visita": _serializar_visita(visita),
        "excepcion": _serializar_excepcion(ex),
    }, 201)


@api_bp.route('/clientes/<int:cliente_id>/visitas', methods=['GET'])
@jwt_required()
def listar_visitas_cliente(cliente_id):
    codigo_vendedor = get_jwt_identity()

    cliente = Cliente.query.filter_by(id=cliente_id).first()
    if not cliente or cliente.codigo_vendedor != codigo_vendedor:
        return respuesta_error('Cliente no encontrado', 404)

    visitas = BDVisitaCliente.query.filter_by(
        cliente_id=cliente_id,
        codigo_vendedor=codigo_vendedor,
    ).order_by(BDVisitaCliente.id.desc()).limit(30).all()

    visita_ids = [v.id for v in visitas]
    
    ventas_autoventa = []
    if visita_ids:
        from app.models.venta_autoventa import BDVentaAutoventa
        ventas_autoventa = BDVentaAutoventa.query.filter(
            BDVentaAutoventa.visit_id.in_(visita_ids)
        ).all()

    transacciones_por_visita = {v.id: [] for v in visitas}
    for venta in ventas_autoventa:
        if venta.visit_id:
            items = []
            for item in venta.items:
                items.append({
                    'producto_cod': item.producto_cod,
                    'nombre': item.producto.nombre if item.producto else item.producto_cod,
                    'cantidad': item.cantidad,
                    'precio_unit': float(item.precio_unit)
                })
            transacciones_por_visita[venta.visit_id].append({
                'consecutivo': venta.consecutivo,
                'total': float(venta.total),
                'items': items
            })

    return respuesta_ok([_serializar_visita(v, transacciones_por_visita.get(v.id, [])) for v in visitas])


@api_bp.route('/clientes/<int:cliente_id>/visita/actual', methods=['GET'])
@jwt_required()
def visita_actual_cliente(cliente_id):
    codigo_vendedor = get_jwt_identity()

    cliente = Cliente.query.filter_by(id=cliente_id).first()
    if not cliente or cliente.codigo_vendedor != codigo_vendedor:
        return respuesta_error('Cliente no encontrado', 404)

    # Prioriza visita en progreso de hoy, si no retorna la ultima registrada.
    hoy = date.today()
    visita = BDVisitaCliente.query.filter_by(
        cliente_id=cliente_id,
        codigo_vendedor=codigo_vendedor,
        fecha_visita=hoy,
        estado='en_progreso',
    ).order_by(BDVisitaCliente.id.desc()).first()

    if not visita:
        visita = BDVisitaCliente.query.filter_by(
            cliente_id=cliente_id,
            codigo_vendedor=codigo_vendedor,
        ).order_by(BDVisitaCliente.id.desc()).first()

    return respuesta_ok(_serializar_visita(visita) if visita else None)


@api_bp.route('/visitas/dia', methods=['GET'])
@jwt_required()
def visitas_del_dia():
    codigo_vendedor = get_jwt_identity()
    hoy = date.today()

    turno_id_param = request.args.get('turno_id', type=int)
    turno_ref = None

    if turno_id_param is not None:
        turno_ref = BDTurno.query.filter_by(
            id=turno_id_param,
            codigo_vendedor=codigo_vendedor,
        ).first()
        if not turno_ref:
            return respuesta_error('turno_id invalido para el vendedor', 400)
    else:
        turno_ref = BDTurno.query.filter_by(
            codigo_vendedor=codigo_vendedor,
            fecha=hoy,
            estado='abierto',
        ).order_by(BDTurno.id.desc()).first()

        if not turno_ref:
            # Fallback para compatibilidad: ultimo turno del dia (si existe).
            turno_ref = BDTurno.query.filter_by(
                codigo_vendedor=codigo_vendedor,
                fecha=hoy,
            ).order_by(BDTurno.id.desc()).first()

    visitas_query = BDVisitaCliente.query.filter(
        BDVisitaCliente.codigo_vendedor == codigo_vendedor,
        BDVisitaCliente.fecha_visita == hoy,
        BDVisitaCliente.estado.in_(['completada', 'excepcion'])
    )

    if turno_ref:
        visitas_query = visitas_query.filter(BDVisitaCliente.turno_id == turno_ref.id)

    visitas = visitas_query.all()

    cliente_ids = sorted({str(v.cliente_id) for v in visitas})
    return respuesta_ok(cliente_ids)


@api_bp.route('/visitas/estado-lote', methods=['POST'])
@jwt_required()
def estado_visitas_lote():
    codigo_vendedor = get_jwt_identity()
    hoy = date.today()
    data = request.get_json(silent=True) or {}

    raw_cliente_ids = data.get('cliente_ids') or []
    if not isinstance(raw_cliente_ids, list):
        return respuesta_error('cliente_ids debe ser una lista', 400)

    cliente_ids = []
    for item in raw_cliente_ids:
        try:
            cliente_id = int(item)
        except (TypeError, ValueError):
            continue
        if cliente_id > 0:
            cliente_ids.append(cliente_id)

    cliente_ids = sorted(set(cliente_ids))
    if len(cliente_ids) == 0:
        return respuesta_ok({'turno_id': None, 'statuses': {}})

    turno_actual = BDTurno.query.filter_by(
        codigo_vendedor=codigo_vendedor,
        estado='abierto',
    ).order_by(BDTurno.id.desc()).first()

    visitas = BDVisitaCliente.query.filter(
        BDVisitaCliente.codigo_vendedor == codigo_vendedor,
        BDVisitaCliente.cliente_id.in_(cliente_ids),
    ).order_by(BDVisitaCliente.id.desc()).all()

    latest_by_cliente = {}
    for visita in visitas:
        if visita.cliente_id not in latest_by_cliente:
            latest_by_cliente[visita.cliente_id] = visita

    statuses = {}
    for cliente_id in cliente_ids:
        visita = latest_by_cliente.get(cliente_id)
        if not visita:
            statuses[str(cliente_id)] = None
            continue

        is_today_visit = visita.fecha_visita == hoy
        is_same_active_turno = bool(
            turno_actual and visita.turno_id and visita.turno_id == turno_actual.id
        )

        if turno_actual and visita.turno_id and not is_same_active_turno:
            statuses[str(cliente_id)] = 'Pendiente'
        elif is_today_visit and visita.estado == 'completada':
            statuses[str(cliente_id)] = 'Visitado'
        elif is_today_visit and visita.estado == 'excepcion':
            statuses[str(cliente_id)] = 'Excepcion'
        else:
            statuses[str(cliente_id)] = 'Pendiente'

    return respuesta_ok({
        'turno_id': turno_actual.id if turno_actual else None,
        'statuses': statuses,
    })
