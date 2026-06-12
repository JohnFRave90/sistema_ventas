import json
from urllib.error import URLError, HTTPError
from urllib.request import urlopen

from flask import request
from flask_jwt_extended import get_jwt_identity, jwt_required
from sqlalchemy.exc import SQLAlchemyError

from app import db
from app.models.ruta_sesion import BDRutaSesion
from app.routes.api import api_bp, respuesta_error, respuesta_ok

OSRM_BASE_URL = "https://router.project-osrm.org"
MAX_WAYPOINTS_PER_REQUEST = 25


def _serializar_sesion(sesion: BDRutaSesion):
    return {
        "id": sesion.id,
        "codigo_vendedor": sesion.codigo_vendedor,
        "ruta_nombre": sesion.ruta_nombre,
        "clientes_cargados": sesion.clientes_cargados,
        "estado": sesion.estado,
        "started_at": sesion.started_at.isoformat() if sesion.started_at else None,
        "ended_at": sesion.ended_at.isoformat() if sesion.ended_at else None,
    }


def _rehacer_tablas_si_faltan():
    db.create_all()


def _is_valid_point(point):
    if not isinstance(point, dict):
        return False
    lat = point.get("latitude")
    lng = point.get("longitude")
    return isinstance(lat, (int, float)) and isinstance(lng, (int, float))


def _to_osrm_coord(point):
    return f"{point['longitude']},{point['latitude']}"


def _split_chunks(points, chunk_size):
    if len(points) <= chunk_size:
        return [points]

    chunks = []
    start = 0
    while start < len(points):
        end = min(start + chunk_size, len(points))
        chunk = points[start:end]
        if start > 0 and len(chunk) > 0:
            chunk = [points[start - 1]] + chunk
        chunks.append(chunk)
        if end == len(points):
            break
        start = end
    return chunks


def _fetch_chunk(points):
    if len(points) < 2:
        return points

    coords = ";".join(_to_osrm_coord(point) for point in points)
    url = (
        f"{OSRM_BASE_URL}/route/v1/driving/{coords}"
        "?overview=full&geometries=geojson&steps=false"
    )

    try:
        with urlopen(url, timeout=15) as response:
            data = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        raise RuntimeError(f"OSRM HTTP {error.code}") from error
    except URLError as error:
        raise RuntimeError(f"OSRM URL error: {error.reason}") from error
    except Exception as error:
        raise RuntimeError(str(error)) from error

    geometry = ((data.get("routes") or [{}])[0].get("geometry") or {}).get("coordinates") or []
    if not geometry:
        raise RuntimeError("OSRM response without geometry")

    path = []
    for coord in geometry:
        if not isinstance(coord, list) or len(coord) < 2:
            continue
        path.append({"latitude": coord[1], "longitude": coord[0]})
    return path


@api_bp.route('/rutas/trazo', methods=['POST'])
@jwt_required()
def obtener_trazo_ruta():
    body = request.get_json(silent=True) or {}
    points = body.get("points") or []

    if not isinstance(points, list) or len(points) < 2:
        return respuesta_error("Se requieren al menos 2 puntos", 400)

    valid_points = [point for point in points if _is_valid_point(point)]
    if len(valid_points) < 2:
        return respuesta_error("Puntos invalidos", 400)

    chunks = _split_chunks(valid_points, MAX_WAYPOINTS_PER_REQUEST)
    merged = []

    try:
        for index, chunk in enumerate(chunks):
            chunk_path = _fetch_chunk(chunk)
            if len(chunk_path) == 0:
                continue
            if index == 0:
                merged.extend(chunk_path)
            else:
                merged.extend(chunk_path[1:])
    except RuntimeError as error:
        # Fallback a linea recta para no romper la experiencia
        return respuesta_ok({
            "source": "fallback",
            "points": valid_points,
            "error": str(error),
        })

    return respuesta_ok({
        "source": "osrm",
        "points": merged if len(merged) > 0 else valid_points,
    })


@api_bp.route('/rutas/sesion/iniciar', methods=['POST'])
@jwt_required()
def iniciar_sesion_ruta():
    codigo_vendedor = get_jwt_identity()
    data = request.get_json(silent=True) or {}

    ruta_nombre = (data.get("ruta_nombre") or data.get("ruta") or "").strip()
    if not ruta_nombre:
        return respuesta_error("ruta_nombre es requerido", 400)

    clientes_cargados = int(data.get("clientes_cargados") or 0)

    try:
        activa = BDRutaSesion.query.filter_by(codigo_vendedor=codigo_vendedor, estado='activa').order_by(BDRutaSesion.id.desc()).first()
        if activa:
            activa.ruta_nombre = ruta_nombre
            activa.clientes_cargados = clientes_cargados
            db.session.commit()
            return respuesta_ok(_serializar_sesion(activa))

        sesion = BDRutaSesion(
            codigo_vendedor=codigo_vendedor,
            ruta_nombre=ruta_nombre,
            clientes_cargados=clientes_cargados,
            estado='activa',
        )
        db.session.add(sesion)
        db.session.commit()
        return respuesta_ok(_serializar_sesion(sesion), 201)
    except SQLAlchemyError as error:
        db.session.rollback()
        try:
            _rehacer_tablas_si_faltan()
            activa = BDRutaSesion.query.filter_by(codigo_vendedor=codigo_vendedor, estado='activa').order_by(BDRutaSesion.id.desc()).first()
            if activa:
                activa.ruta_nombre = ruta_nombre
                activa.clientes_cargados = clientes_cargados
                db.session.commit()
                return respuesta_ok(_serializar_sesion(activa))

            sesion = BDRutaSesion(
                codigo_vendedor=codigo_vendedor,
                ruta_nombre=ruta_nombre,
                clientes_cargados=clientes_cargados,
                estado='activa',
            )
            db.session.add(sesion)
            db.session.commit()
            return respuesta_ok(_serializar_sesion(sesion), 201)
        except SQLAlchemyError as retry_error:
            db.session.rollback()
            return respuesta_error(f'No se pudo iniciar la sesion de ruta: {retry_error}', 503)


@api_bp.route('/rutas/sesion/actual', methods=['GET'])
@jwt_required()
def sesion_ruta_actual():
    codigo_vendedor = get_jwt_identity()
    try:
        sesion = BDRutaSesion.query.filter_by(codigo_vendedor=codigo_vendedor, estado='activa').order_by(BDRutaSesion.id.desc()).first()
        return respuesta_ok(_serializar_sesion(sesion) if sesion else None)
    except SQLAlchemyError as error:
        db.session.rollback()
        try:
            _rehacer_tablas_si_faltan()
            sesion = BDRutaSesion.query.filter_by(codigo_vendedor=codigo_vendedor, estado='activa').order_by(BDRutaSesion.id.desc()).first()
            return respuesta_ok(_serializar_sesion(sesion) if sesion else None)
        except SQLAlchemyError as retry_error:
            db.session.rollback()
            return respuesta_error(f'No se pudo leer la sesion de ruta: {retry_error}', 503)


@api_bp.route('/rutas/sesion/cerrar', methods=['POST'])
@jwt_required()
def cerrar_sesion_ruta():
    codigo_vendedor = get_jwt_identity()
    data = request.get_json(silent=True) or {}

    try:
        sesion = BDRutaSesion.query.filter_by(codigo_vendedor=codigo_vendedor, estado='activa').order_by(BDRutaSesion.id.desc()).first()
        if not sesion:
            return respuesta_ok(None)

        sesion.estado = 'cerrada'
        if data.get('clientes_cargados') is not None:
            sesion.clientes_cargados = int(data.get('clientes_cargados'))
        db.session.commit()
        return respuesta_ok(_serializar_sesion(sesion))
    except SQLAlchemyError as error:
        db.session.rollback()
        try:
            _rehacer_tablas_si_faltan()
            sesion = BDRutaSesion.query.filter_by(codigo_vendedor=codigo_vendedor, estado='activa').order_by(BDRutaSesion.id.desc()).first()
            if not sesion:
                return respuesta_ok(None)

            sesion.estado = 'cerrada'
            if data.get('clientes_cargados') is not None:
                sesion.clientes_cargados = int(data.get('clientes_cargados'))
            db.session.commit()
            return respuesta_ok(_serializar_sesion(sesion))
        except SQLAlchemyError as retry_error:
            db.session.rollback()
            return respuesta_error(f'No se pudo cerrar la sesion de ruta: {retry_error}', 503)
