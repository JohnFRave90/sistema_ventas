from flask_jwt_extended import jwt_required
from app.routes.api import api_bp, respuesta_ok
from app.models.producto import Producto


@api_bp.route('/productos', methods=['GET'])
@jwt_required()
def listar_productos():
    productos = Producto.query.filter_by(activo=True).order_by(Producto.orden).all()
    data = [
        {
            'codigo': p.codigo,
            'nombre': p.nombre,
            'precio': float(p.precio),
            'categoria': p.categoria,
            'orden': p.orden,
        }
        for p in productos
    ]
    return respuesta_ok(data)
