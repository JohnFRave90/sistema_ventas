from flask import request
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError

from app import db
from app.routes.api import api_bp, respuesta_ok, respuesta_error
from app.models.cliente import Cliente
from app.models.venta_autoventa import BDVentaAutoventa


def _serializar_cliente(c):
    return {
        'id':            c.id,
        'codigo_cliente': c.codigo_cliente,
        'nombre':        c.nombre,
        'nombre_tienda': c.nombre_tienda,
        'telefono':      c.telefono,
        'whatsapp':      c.whatsapp,
        'direccion':     c.direccion,
        'barrio':        c.barrio,
        'ciudad':        c.ciudad,
        'latitud':       float(c.latitud) if c.latitud else None,
        'longitud':      float(c.longitud) if c.longitud else None,
        'ruta':          c.ruta,
        'orden_visita':  c.orden_visita,
        'codigo_vendedor': c.codigo_vendedor
    }


@api_bp.route('/clientes', methods=['GET'])
@jwt_required()
def listar_clientes():
    codigo_vendedor = get_jwt_identity()
    clientes = Cliente.query.filter_by(
        codigo_vendedor=codigo_vendedor
    ).order_by(Cliente.ruta, Cliente.orden_visita).all()
    return respuesta_ok([_serializar_cliente(c) for c in clientes])


def _parse_coord(valor, lo, hi):
    """Devuelve float dentro de [lo, hi] o None si vacío/inválido/fuera de rango."""
    if valor is None or valor == '':
        return None, True
    try:
        f = float(valor)
    except (TypeError, ValueError):
        return None, False
    if f < lo or f > hi:
        return None, False
    return f, True


def _count_ruta(codigo_vendedor, ruta):
    return Cliente.query.filter_by(codigo_vendedor=codigo_vendedor, ruta=ruta).count()


def _abrir_hueco(codigo_vendedor, ruta, pos, excluir_id=None):
    """Deja un hueco en `pos`: suma +1 a orden_visita de los clientes >= pos."""
    q = Cliente.query.filter(
        Cliente.codigo_vendedor == codigo_vendedor,
        Cliente.ruta == ruta,
        Cliente.orden_visita >= pos,
    )
    if excluir_id is not None:
        q = q.filter(Cliente.id != excluir_id)
    q.update({Cliente.orden_visita: Cliente.orden_visita + 1}, synchronize_session=False)


def _resequence_ruta(codigo_vendedor, ruta):
    """Renumera orden_visita 1..N por orden actual — garantiza secuencia sin
    duplicados ni huecos. Sin commit (lo hace el endpoint dentro de su transacción)."""
    clientes = Cliente.query.filter_by(
        codigo_vendedor=codigo_vendedor, ruta=ruta
    ).order_by(Cliente.orden_visita.asc(), Cliente.id.asc()).all()
    for idx, c in enumerate(clientes, start=1):
        if c.orden_visita != idx:
            c.orden_visita = idx


def _parse_pos(valor):
    """Posición 1-based solicitada, o None si no viene/ inválida."""
    if valor is None or valor == '':
        return None
    try:
        p = int(valor)
    except (TypeError, ValueError):
        return None
    return p if p >= 1 else None


@api_bp.route('/clientes', methods=['POST'])
@jwt_required()
def crear_cliente():
    """Crea un cliente nuevo desde la app, asociado al vendedor del JWT.

    La ruta es un nombre (string) — el esquema NO maneja ruta_id ni tabla
    clientes_rutas; el cliente se asocia por el campo `cliente.ruta`.
    """
    codigo_vendedor = get_jwt_identity()
    data = request.get_json(silent=True) or {}

    nombre = (data.get('nombre') or data.get('nombre_tienda') or '').strip()
    nombre_tienda = (data.get('nombre_tienda') or '').strip() or None
    ruta = (data.get('ruta') or '').strip()

    if not nombre:
        return respuesta_error('El nombre del cliente es obligatorio', 400)
    if not ruta:
        return respuesta_error('La ruta es obligatoria', 400)

    # Validar coordenadas (opcionales, pero si vienen deben ser válidas).
    latitud, lat_ok = _parse_coord(data.get('latitud'), -90, 90)
    longitud, lng_ok = _parse_coord(data.get('longitud'), -180, 180)
    if not lat_ok or not lng_ok:
        return respuesta_error('Latitud/longitud inválidas', 400)

    # Evitar duplicado obvio: mismo nombre + ruta para el mismo vendedor.
    existente = Cliente.query.filter(
        Cliente.codigo_vendedor == codigo_vendedor,
        Cliente.ruta == ruta,
        func.lower(Cliente.nombre) == nombre.lower(),
    ).first()
    if existente:
        return respuesta_error('Ya existe un cliente con ese nombre en la ruta', 409)

    # Posición en la ruta (orden_visita). Si el usuario elige una posición, se
    # inserta ahí y se desplazan los siguientes; si no, va al final.
    count = _count_ruta(codigo_vendedor, ruta)
    requested = _parse_pos(data.get('orden_visita'))
    pos = requested if (requested is not None and requested <= count + 1) else count + 1

    try:
        if pos <= count:
            _abrir_hueco(codigo_vendedor, ruta, pos)

        nuevo = Cliente(
            codigo_cliente=Cliente.siguiente_codigo(),
            nombre=nombre,
            nombre_tienda=nombre_tienda,
            codigo_vendedor=codigo_vendedor,
            telefono=(data.get('telefono') or '').strip() or None,
            whatsapp=(data.get('whatsapp') or '').strip() or None,
            direccion=(data.get('direccion') or '').strip() or None,
            barrio=(data.get('barrio') or '').strip() or None,
            ciudad=(data.get('ciudad') or '').strip() or None,
            ruta=ruta,
            latitud=latitud,
            longitud=longitud,
            orden_visita=pos,
        )
        db.session.add(nuevo)
        db.session.flush()
        # Garantía de secuencia contigua sin duplicados.
        _resequence_ruta(codigo_vendedor, ruta)
        db.session.commit()
    except SQLAlchemyError as error:
        db.session.rollback()
        return respuesta_error(f'No se pudo crear el cliente: {error}', 500)

    return respuesta_ok(_serializar_cliente(nuevo), 201)


@api_bp.route('/clientes/<int:cliente_id>', methods=['PUT', 'PATCH'])
@jwt_required()
def actualizar_cliente(cliente_id):
    """Edita un cliente. Soporta mover su posición en la ruta (orden_visita) y/o
    cambiarlo de ruta; recalcula y persiste las posiciones afectadas de forma
    transaccional, manteniendo numeración secuencial sin duplicados."""
    codigo_vendedor = get_jwt_identity()
    data = request.get_json(silent=True) or {}

    cliente = Cliente.query.filter_by(id=cliente_id).first()
    if not cliente or cliente.codigo_vendedor != codigo_vendedor:
        return respuesta_error('Cliente no encontrado', 404)

    # Campos simples (opcionales).
    for campo in ('nombre', 'nombre_tienda', 'telefono', 'whatsapp', 'direccion', 'barrio', 'ciudad'):
        if campo in data:
            valor = (data.get(campo) or '').strip()
            setattr(cliente, campo, valor or None)
    if 'nombre' in data and not (cliente.nombre or '').strip():
        return respuesta_error('El nombre del cliente es obligatorio', 400)

    if 'latitud' in data or 'longitud' in data:
        latitud, lat_ok = _parse_coord(data.get('latitud', cliente.latitud), -90, 90)
        longitud, lng_ok = _parse_coord(data.get('longitud', cliente.longitud), -180, 180)
        if not lat_ok or not lng_ok:
            return respuesta_error('Latitud/longitud inválidas', 400)
        cliente.latitud = latitud
        cliente.longitud = longitud

    old_ruta = cliente.ruta
    target_ruta = (data.get('ruta') or old_ruta or '').strip() or old_ruta
    requested = _parse_pos(data.get('orden_visita'))
    ruta_cambia = target_ruta != old_ruta
    mueve = requested is not None or ruta_cambia

    try:
        if mueve:
            # Nº de clientes en la ruta destino EXCLUYENDO este si ya está ahí.
            base = _count_ruta(codigo_vendedor, target_ruta)
            if not ruta_cambia:
                base = max(0, base - 1)  # el propio cliente ya cuenta en su ruta
            pos = requested if (requested is not None and requested <= base + 1) else base + 1

            _abrir_hueco(codigo_vendedor, target_ruta, pos, excluir_id=cliente.id)
            cliente.ruta = target_ruta
            cliente.orden_visita = pos
            db.session.flush()
            _resequence_ruta(codigo_vendedor, target_ruta)
            if ruta_cambia:
                _resequence_ruta(codigo_vendedor, old_ruta)

        db.session.commit()
    except SQLAlchemyError as error:
        db.session.rollback()
        return respuesta_error(f'No se pudo actualizar el cliente: {error}', 500)

    return respuesta_ok(_serializar_cliente(cliente))


@api_bp.route('/clientes/<int:cliente_id>', methods=['GET'])
@jwt_required()
def detalle_cliente(cliente_id):
    codigo_vendedor = get_jwt_identity()
    cliente = Cliente.query.filter_by(id=cliente_id).first()
    if not cliente or cliente.codigo_vendedor != codigo_vendedor:
        return respuesta_error('Cliente no encontrado', 404)

    ultimas_ventas = BDVentaAutoventa.query.filter_by(
        cliente_id=cliente_id
    ).order_by(BDVentaAutoventa.id.desc()).limit(10).all()

    historial = [{
        'consecutivo': v.consecutivo,
        'fecha':       str(v.fecha),
        'total':       float(v.total) if v.total else 0,
        'items': [{
            'producto_cod': i.producto_cod,
            'nombre':       i.producto.nombre if i.producto else i.producto_cod,
            'cantidad':     i.cantidad,
            'precio_unit':  float(i.precio_unit),
            'subtotal':     float(i.subtotal)
        } for i in v.items]
    } for v in ultimas_ventas]

    data = _serializar_cliente(cliente)
    data['historial'] = historial
    return respuesta_ok(data)
