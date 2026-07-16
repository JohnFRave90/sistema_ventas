from flask import request, current_app
from flask_jwt_extended import (
    create_access_token, jwt_required, get_jwt_identity
)
from werkzeug.security import check_password_hash
from app.routes.api import api_bp, respuesta_ok, respuesta_error
from app.models.vendedor import Vendedor
from app.models.usuario import Usuario

ROLES_ADMIN = ('administrador', 'semiadmin')


@api_bp.route('/auth/login', methods=['POST'])
def login():
    data = request.get_json(silent=True) or {}
    usuario = data.get('usuario', '').strip()
    contrasena = data.get('contrasena', '').strip()

    if not usuario or not contrasena:
        return respuesta_error('usuario y contrasena son requeridos', 400)

    vendedor = Vendedor.query.filter(
        (Vendedor.nombre_usuario == usuario) |
        (Vendedor.codigo_vendedor == usuario)
    ).first()

    if not vendedor or not check_password_hash(vendedor.contraseña, contrasena):
        return respuesta_error('Usuario o contraseña incorrectos', 401)

    identity = vendedor.codigo_vendedor
    token = create_access_token(identity=identity)

    expira_en = int(current_app.config.get('JWT_ACCESS_TOKEN_EXPIRES', 57600))

    return respuesta_ok({
        'access_token': token,
        'codigo_vendedor': vendedor.codigo_vendedor,
        'nombre': vendedor.nombre,
        'expira_en': expira_en
    })


@api_bp.route('/auth/login-admin', methods=['POST'])
def login_admin():
    """Login separado para administradores/semiadmins (tabla Usuario).

    No comparte tabla ni lógica con el login de vendedores usado por la app
    móvil: mantiene ambos flujos independientes.
    """
    data = request.get_json(silent=True) or {}
    usuario_nombre = data.get('usuario', '').strip()
    contrasena = data.get('contrasena', '').strip()

    if not usuario_nombre or not contrasena:
        return respuesta_error('usuario y contrasena son requeridos', 400)

    usuario = Usuario.query.filter_by(nombre_usuario=usuario_nombre).first()

    if not usuario or not usuario.check_password(contrasena):
        return respuesta_error('Usuario o contraseña incorrectos', 401)

    if usuario.rol not in ROLES_ADMIN:
        return respuesta_error('Este usuario no tiene rol de administración', 403)

    token = create_access_token(
        identity=usuario.nombre_usuario,
        additional_claims={'rol': usuario.rol, 'tipo': 'admin'},
    )

    expira_en = int(current_app.config.get('JWT_ACCESS_TOKEN_EXPIRES', 57600))

    return respuesta_ok({
        'access_token': token,
        'nombre_usuario': usuario.nombre_usuario,
        'rol': usuario.rol,
        'expira_en': expira_en
    })


@api_bp.route('/auth/refresh', methods=['POST'])
@jwt_required()
def refresh():
    identity = get_jwt_identity()
    nuevo_token = create_access_token(identity=identity)
    return respuesta_ok({'access_token': nuevo_token})
