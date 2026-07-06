from datetime import date

from flask import request
from flask_jwt_extended import get_jwt_identity, jwt_required

from app import db
from app.models.cambio import BDCambio, BDCambioItem
from app.models.cliente import Cliente
from app.models.producto import Producto
from app.models.turno import BDTurno
from app.models.venta_autoventa import BDVentaAutoventa, BDVentaAutoventaItem
from app.models.visita_cliente import BDVisitaCliente
from app.routes.api import api_bp, respuesta_error, respuesta_ok
from app.utils.documentos import generar_consecutivo


def _parse_items(items_data):
    parsed = []
    for item in items_data:
        codigo = (item or {}).get("producto_cod")
        cantidad = (item or {}).get("cantidad", 0)
        if not codigo or not isinstance(cantidad, int) or cantidad <= 0:
            raise ValueError("Todos los items deben tener producto_cod y cantidad > 0")
        parsed.append({"producto_cod": codigo, "cantidad": cantidad})
    return parsed


@api_bp.route('/cambios', methods=['POST'])
@jwt_required()
def registrar_cambio():
    codigo_vendedor = get_jwt_identity()
    data = request.get_json(silent=True) or {}

    cliente_id = data.get('cliente_id')
    turno_id = data.get('turno_id')
    visit_id = data.get('visit_id')
    uuid_origen = data.get('uuid')

    items_devolucion_raw = data.get('items_devolucion', [])
    items_venta_raw = data.get('items_venta', [])

    if not cliente_id:
        return respuesta_error('cliente_id es requerido', 400)

    if not items_devolucion_raw or not items_venta_raw:
        return respuesta_error('items_devolucion e items_venta son requeridos', 400)

    cliente = Cliente.query.filter_by(id=cliente_id).first()
    if not cliente or cliente.codigo_vendedor != codigo_vendedor:
        return respuesta_error('Cliente no encontrado', 404)

    if turno_id is not None:
        turno = BDTurno.query.filter_by(id=turno_id, codigo_vendedor=codigo_vendedor).first()
        if not turno:
            return respuesta_error('turno_id no valido para el vendedor', 400)

    if visit_id is not None:
        visita = BDVisitaCliente.query.filter_by(
            id=visit_id,
            cliente_id=cliente_id,
            codigo_vendedor=codigo_vendedor,
        ).first()
        if not visita:
            return respuesta_error('visit_id no valido para el cliente/vendedor', 400)

    # Idempotencia: si ya existe un cambio con este uuid, retornar el original.
    if uuid_origen:
        existente = BDCambio.query.filter_by(uuid_origen=uuid_origen).first()
        if existente:
            venta = BDVentaAutoventa.query.filter_by(uuid_origen=uuid_origen).first()
            return respuesta_ok({
                'uuid': uuid_origen,
                'cambio_consecutivo': existente.consecutivo,
                'venta_consecutivo': venta.consecutivo if venta else None,
                'devolucion_consecutivo': None,
                'total_venta': float(existente.total_venta),
                'idempotent': True,
            })

    try:
        items_devolucion = _parse_items(items_devolucion_raw)
        items_venta = _parse_items(items_venta_raw)
    except ValueError as error:
        return respuesta_error(str(error), 400)

    try:
        cambio = BDCambio(
            consecutivo=generar_consecutivo(BDCambio, 'CB'),
            codigo_vendedor=codigo_vendedor,
            cliente_id=cliente_id,
            turno_id=turno_id,
            visit_id=visit_id,
            fecha=date.today(),
            comentarios=data.get('comentarios', ''),
            uuid_origen=uuid_origen,
        )
        db.session.add(cambio)
        db.session.flush()

        total_venta = 0
        venta_items_creados = []

        # Pierna de devolución: productos que regresan DESDE el cliente.
        for item in items_devolucion:
            prod = Producto.query.filter_by(codigo=item['producto_cod']).first()
            if not prod:
                raise ValueError(f"Producto {item['producto_cod']} no existe")
            precio = float(prod.precio or 0)
            db.session.add(BDCambioItem(
                cambio_id=cambio.id,
                tipo='devolucion',
                producto_cod=prod.codigo,
                cantidad=item['cantidad'],
                precio_unit=precio,
                subtotal=precio * item['cantidad'],
            ))

        # Pierna de venta: productos que salen HACIA el cliente.
        for item in items_venta:
            prod = Producto.query.filter_by(codigo=item['producto_cod']).first()
            if not prod:
                raise ValueError(f"Producto {item['producto_cod']} no existe")
            precio = float(prod.precio or 0)
            subtotal = precio * item['cantidad']
            total_venta += subtotal
            venta_items_creados.append((prod, item['cantidad'], subtotal))
            db.session.add(BDCambioItem(
                cambio_id=cambio.id,
                tipo='venta',
                producto_cod=prod.codigo,
                cantidad=item['cantidad'],
                precio_unit=precio,
                subtotal=subtotal,
            ))

        cambio.total_venta = total_venta

        # Registra la venta correspondiente (las unidades que salen del inventario
        # se cuentan en el resumen vía BDVentaAutoventa, igual que una venta normal).
        venta = BDVentaAutoventa(
            consecutivo=generar_consecutivo(BDVentaAutoventa, 'AV'),
            codigo_vendedor=codigo_vendedor,
            cliente_id=cliente_id,
            turno_id=turno_id,
            visit_id=visit_id,
            fecha=date.today(),
            total=total_venta,
            enviada_por_sync=False,
            uuid_origen=uuid_origen,
        )
        db.session.add(venta)
        db.session.flush()

        for prod, cantidad, subtotal in venta_items_creados:
            db.session.add(BDVentaAutoventaItem(
                autoventa_id=venta.id,
                producto_cod=prod.codigo,
                cantidad=cantidad,
                precio_unit=float(prod.precio or 0),
                subtotal=subtotal,
            ))

        db.session.commit()

        return respuesta_ok({
            'uuid': uuid_origen,
            'cambio_consecutivo': cambio.consecutivo,
            'venta_consecutivo': venta.consecutivo,
            'devolucion_consecutivo': None,
            'total_venta': float(venta.total),
            'idempotent': False,
        })

    except ValueError as error:
        db.session.rollback()
        return respuesta_error(str(error), 400)
    except Exception as error:
        db.session.rollback()
        return respuesta_error(f'No se pudo registrar el cambio: {error}', 500)
