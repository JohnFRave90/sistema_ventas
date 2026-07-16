from functools import wraps

from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required, get_jwt

api_bp = Blueprint('api', __name__)

def respuesta_ok(data, status=200):
    return jsonify({"ok": True, "data": data}), status

def respuesta_error(mensaje, status=400):
    return jsonify({"ok": False, "error": mensaje}), status

def admin_jwt_required(fn):
    """Equivalente a rol_requerido('semiadmin','administrador') pero para JWT.

    Exige un token emitido por /auth/login-admin (claim 'rol' en
    ('administrador', 'semiadmin')), no uno de vendedor.
    """
    @wraps(fn)
    @jwt_required()
    def wrapper(*args, **kwargs):
        rol = get_jwt().get('rol')
        if rol not in ('administrador', 'semiadmin'):
            return respuesta_error('Acceso denegado', 403)
        return fn(*args, **kwargs)
    return wrapper

# Sub-módulos se importan después de que existan los archivos
from app.routes.api import auth       # noqa: F401
from app.routes.api import productos  # noqa: F401
from app.routes.api import inventario  # noqa: F401
from app.routes.api import clientes   # noqa: F401
from app.routes.api import ventas     # noqa: F401
from app.routes.api import pedidos    # noqa: F401
from app.routes.api import extras     # noqa: F401
from app.routes.api import devoluciones # noqa: F401
from app.routes.api import cambios      # noqa: F401
from app.routes.api import sync       # noqa: F401
from app.routes.api import rutas      # noqa: F401
from app.routes.api import turnos     # noqa: F401
from app.routes.api import visitas    # noqa: F401
from app.routes.api import ubicaciones # noqa: F401
from app.routes.api import despachos   # noqa: F401
from app.routes.api import mapa        # noqa: F401
from app.routes.api import analitica   # noqa: F401
from app.routes.api import admin       # noqa: F401
