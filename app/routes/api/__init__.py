from flask import Blueprint, jsonify

api_bp = Blueprint('api', __name__)

def respuesta_ok(data, status=200):
    return jsonify({"ok": True, "data": data}), status

def respuesta_error(mensaje, status=400):
    return jsonify({"ok": False, "error": mensaje}), status

# Sub-módulos se importan después de que existan los archivos
from app.routes.api import auth       # noqa: F401
from app.routes.api import productos  # noqa: F401
from app.routes.api import inventario  # noqa: F401
from app.routes.api import clientes   # noqa: F401
from app.routes.api import ventas     # noqa: F401
from app.routes.api import pedidos    # noqa: F401
from app.routes.api import extras     # noqa: F401
from app.routes.api import devoluciones # noqa: F401
from app.routes.api import sync       # noqa: F401
