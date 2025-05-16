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
                return redirect(url_for('dashboard.dashboard'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# Decoradores “prefabricados” (opcional)
admin_required     = rol_requerido('administrador')
semiadmin_required = rol_requerido('semiadmin')
vendedor_required  = rol_requerido('vendedor')
