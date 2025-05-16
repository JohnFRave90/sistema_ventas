from flask_login import UserMixin
from flask import redirect, url_for, flash
from flask_login import current_user
from functools import wraps

class UserWrapper(UserMixin):
    def __init__(self, user, tipo):
        self.user = user
        self.tipo = tipo  # "usuario" o "vendedor"
        self.id = f"{tipo}:{user.id}"  # Ejemplo: vendedor:5

    def get_id(self):
        return self.id

    @property
    def rol(self):
        return self.user.rol

    @property
    def nombre_usuario(self):
        return self.user.nombre_usuario

# app/utils/roles.py
from functools import wraps
from flask import redirect, url_for, flash
from flask_login import current_user

def rol_requerido(*roles_permitidos):
    """
    Permite el acceso si current_user.rol está en roles_permitidos.
    Uso: @rol_requerido('vendedor', 'administrador')
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Nota: tu UserWrapper expone la propiedad 'rol'
            user_role = getattr(current_user, 'rol', None)
            if user_role not in roles_permitidos:
                flash("Acceso denegado: no tienes permiso para esta acción.", "danger")
                return redirect(url_for('main.index'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# Decoradores “prefabricados” (opcional)
admin_required     = rol_requerido('administrador')
semiadmin_required = rol_requerido('semiadmin')
vendedor_required  = rol_requerido('vendedor')
