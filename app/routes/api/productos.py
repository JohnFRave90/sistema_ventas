from flask_jwt_extended import jwt_required
from app.routes.api import api_bp, respuesta_ok
from app.utils.productos import get_productos_ordenados, orden_index


@api_bp.route('/productos', methods=['GET'])
@jwt_required()
def listar_productos():
    # FUENTE DE VERDAD del orden = get_productos_ordenados (lista fija de códigos
    # del sistema de ventas), NO la columna Producto.orden. Se devuelve `orden` =
    # posición canónica (0..N; fuera de la lista = 9999) para que el app reproduzca
    # EXACTAMENTE la misma secuencia aunque la caché o el merge reordenen.
    productos = get_productos_ordenados()
    data = [
        {
            'codigo': p.codigo,
            'nombre': p.nombre,
            'precio': float(p.precio),
            'categoria': p.categoria,
            'orden': orden_index(p.codigo),
        }
        for p in productos
    ]
    return respuesta_ok(data)
