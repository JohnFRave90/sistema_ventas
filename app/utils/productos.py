from app.models import Producto


def get_productos_ordenados():
    """Obtiene los productos ordenados por el campo ``orden``
    Si no hay valores personalizados, simplemente los ordena por nombre."""

    productos = (
        Producto.query
        .filter_by(activo=True)
        .order_by(Producto.orden, Producto.nombre)
        .all()
    )
    return productos
