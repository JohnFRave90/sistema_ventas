from datetime import datetime
from typing import Optional

from flask import request
from flask_jwt_extended import get_jwt_identity, jwt_required

from app import db
from app.models.turno import BDTurno
from app.models.turno_ubicacion import BDTurnoUbicacion
from app.routes.api import api_bp, respuesta_error, respuesta_ok


def _parse_datetime(value: Optional[str]) -> datetime:
    if not value:
        return datetime.now()
    normalized = value.replace('Z', '+00:00')
    return datetime.fromisoformat(normalized)


def _to_float(value):
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _validar_lat_lng(latitud: Optional[float], longitud: Optional[float]) -> bool:
    if latitud is None or longitud is None:
        return False
    return -90 <= latitud <= 90 and -180 <= longitud <= 180


def _resolver_turno(codigo_vendedor: str, turno_id: Optional[int]) -> Optional[BDTurno]:
    if turno_id:
        return BDTurno.query.filter_by(id=turno_id, codigo_vendedor=codigo_vendedor).first()

    return BDTurno.query.filter_by(
        codigo_vendedor=codigo_vendedor,
        estado='abierto',
    ).order_by(BDTurno.id.desc()).first()


def _serializar_punto(punto: BDTurnoUbicacion):
    return {
        'id': punto.id,
        'codigo_vendedor': punto.codigo_vendedor,
        'turno_id': punto.turno_id,
        'latitud': float(punto.latitud),
        'longitud': float(punto.longitud),
        'precision_m': float(punto.precision_m) if punto.precision_m is not None else None,
        'velocidad_mps': float(punto.velocidad_mps) if punto.velocidad_mps is not None else None,
        'rumbo_grados': float(punto.rumbo_grados) if punto.rumbo_grados is not None else None,
        'fuente': punto.fuente,
        'captured_at': punto.captured_at.isoformat() if punto.captured_at else None,
    }


@api_bp.route('/turnos/ubicacion', methods=['POST'])
@jwt_required()
def registrar_ubicacion_turno():
    codigo_vendedor = get_jwt_identity()
    data = request.get_json(silent=True) or {}

    latitud = _to_float(data.get('latitud'))
    longitud = _to_float(data.get('longitud'))
    if not _validar_lat_lng(latitud, longitud):
        return respuesta_error('Latitud/longitud invalidas', 400)

    turno_id = data.get('turno_id')
    try:
        turno_id = int(turno_id) if turno_id is not None else None
    except (TypeError, ValueError):
        return respuesta_error('turno_id invalido', 400)

    turno = _resolver_turno(codigo_vendedor, turno_id)
    if turno_id and not turno:
        return respuesta_error('turno_id no corresponde al vendedor', 400)

    try:
        captured_at = _parse_datetime(data.get('captured_at'))
    except ValueError:
        return respuesta_error('captured_at invalido. Usa ISO-8601', 400)

    punto = BDTurnoUbicacion(
        codigo_vendedor=codigo_vendedor,
        turno_id=turno.id if turno else None,
        latitud=latitud,
        longitud=longitud,
        precision_m=_to_float(data.get('precision_m')),
        velocidad_mps=_to_float(data.get('velocidad_mps')),
        rumbo_grados=_to_float(data.get('rumbo_grados')),
        fuente=(data.get('fuente') or 'background')[:20],
        captured_at=captured_at,
    )
    db.session.add(punto)
    db.session.commit()

    return respuesta_ok(_serializar_punto(punto), 201)


@api_bp.route('/turnos/ubicacion/lote', methods=['POST'])
@jwt_required()
def registrar_ubicacion_turno_lote():
    codigo_vendedor = get_jwt_identity()
    data = request.get_json(silent=True) or {}
    puntos = data.get('puntos') or []

    if not isinstance(puntos, list) or len(puntos) == 0:
        return respuesta_error('puntos debe ser una lista no vacia', 400)

    creados = []
    for item in puntos:
        latitud = _to_float(item.get('latitud'))
        longitud = _to_float(item.get('longitud'))
        if not _validar_lat_lng(latitud, longitud):
            continue

        turno_id_raw = item.get('turno_id')
        try:
            turno_id = int(turno_id_raw) if turno_id_raw is not None else None
        except (TypeError, ValueError):
            turno_id = None

        turno = _resolver_turno(codigo_vendedor, turno_id)
        if turno_id and not turno:
            continue

        try:
            captured_at = _parse_datetime(item.get('captured_at'))
        except ValueError:
            captured_at = datetime.now()

        punto = BDTurnoUbicacion(
            codigo_vendedor=codigo_vendedor,
            turno_id=turno.id if turno else None,
            latitud=latitud,
            longitud=longitud,
            precision_m=_to_float(item.get('precision_m')),
            velocidad_mps=_to_float(item.get('velocidad_mps')),
            rumbo_grados=_to_float(item.get('rumbo_grados')),
            fuente=(item.get('fuente') or 'background')[:20],
            captured_at=captured_at,
        )
        db.session.add(punto)
        creados.append(punto)

    if not creados:
        return respuesta_error('No se recibieron puntos validos', 400)

    db.session.commit()
    return respuesta_ok({'insertados': len(creados)})


@api_bp.route('/turnos/<int:turno_id>/ubicaciones', methods=['GET'])
@jwt_required()
def listar_ubicaciones_turno(turno_id):
    codigo_vendedor = get_jwt_identity()
    turno = BDTurno.query.filter_by(id=turno_id, codigo_vendedor=codigo_vendedor).first()
    if not turno:
        return respuesta_error('Turno no encontrado', 404)

    limit = request.args.get('limit', default=2000, type=int)
    limit = max(1, min(limit, 5000))

    puntos = BDTurnoUbicacion.query.filter_by(
        codigo_vendedor=codigo_vendedor,
        turno_id=turno.id,
    ).order_by(BDTurnoUbicacion.captured_at.asc()).limit(limit).all()

    return respuesta_ok({
        'turno_id': turno.id,
        'total': len(puntos),
        'puntos': [_serializar_punto(punto) for punto in puntos],
    })
