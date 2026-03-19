from datetime import date
from flask import request
from flask_jwt_extended import jwt_required, get_jwt_identity
from app import db
from app.routes.api import api_bp, respuesta_ok, respuesta_error
from app.models.devoluciones import BDDevolucion
from app.models.devolucion_item import BDDevolucionItem
from app.models.producto import Producto
from app.utils.documentos import generar_consecutivo


@api_bp.route('/devoluciones', methods=['POST'])
@jwt_required()
def crear_devolucion():
    codigo_vendedor = get_jwt_identity()
    data = request.get_json(silent=True) or {}
    items_data = data.get('items', [])

    if not items_data:
        return respuesta_error('items es requerido', 400)

    # Validar que ningún ítem tenga cantidad negativa
    for it in items_data:
        if it.get('cantidad', 0) < 0:
            return respuesta_error(
                f"Ítem {it.get('producto_cod')} tiene cantidad negativa. "
                "La devolución no puede contener cantidades negativas.", 400
            )

    devolucion = BDDevolucion(
        consecutivo=generar_consecutivo(BDDevolucion, 'DV'),
        codigo_vendedor=codigo_vendedor,
        fecha=date.today(),
        comentarios=data.get('comentarios', ''),
        usos=0
    )
    db.session.add(devolucion)
    db.session.flush()

    for it in items_data:
        prod = Producto.query.filter_by(codigo=it['producto_cod']).first()
        if not prod:
            db.session.rollback()
            return respuesta_error(f"Producto {it['producto_cod']} no existe", 400)
        cantidad = it['cantidad']
        subtotal = prod.precio * cantidad
        db.session.add(BDDevolucionItem(
            devolucion_id=devolucion.id,
            producto_cod=prod.codigo,
            cantidad=cantidad,
            precio_unit=prod.precio,
            subtotal=subtotal
        ))

    db.session.commit()
    return respuesta_ok({'consecutivo': devolucion.consecutivo})
