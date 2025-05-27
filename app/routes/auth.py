from flask import Blueprint, render_template, redirect, url_for, request, flash, session
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash, generate_password_hash
from app.models.usuario import Usuario
from app.models.vendedor import Vendedor  
from app import db
from app.routes.utils import UserWrapper
from app.utils.roles        import rol_requerido

auth_bp = Blueprint("auth", __name__)

def redirigir_dashboard(usuario):
    if usuario.rol == 'administrador':
        return redirect(url_for('dashboard.dashboard_admin'))
    elif usuario.rol == 'semiadmin':
        return redirect(url_for('dashboard.dashboard_semiadmin'))
    elif usuario.rol == 'vendedor':
        return redirect(url_for('dashboard.dashboard_vendedor'))
    else:
        return redirect(url_for('dashboard.dashboard'))  # Default

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        if not username or not password:
            flash("Por favor completa todos los campos.", "danger")
            return render_template("login.html")

        # 1. Buscar en tabla de usuarios (administradores y semiadmins)
        usuario = Usuario.query.filter_by(nombre_usuario=username).first()
        if usuario and usuario.check_password(password):
            login_user(usuario)
            flash('Bienvenido', 'success')
            return redirigir_dashboard(usuario)

        # 2. Buscar en tabla de vendedores (por nombre_usuario o código)
        vendedor = Vendedor.query.filter(
            (Vendedor.nombre_usuario == username) |
            (Vendedor.codigo_vendedor == username)
        ).first()
        if vendedor and check_password_hash(vendedor.contraseña, password):
            login_user(UserWrapper(vendedor, "vendedor"))
            # Guardar el código de vendedor en sesión
            session['codigo_vendedor'] = vendedor.codigo_vendedor
            return redirect(url_for("dashboard.dashboard_vendedor"))

        flash("Usuario o contraseña incorrectos.", "danger")
        return render_template("login.html")

    return render_template("login.html")

@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Sesión cerrada exitosamente.", "success")
    return redirect(url_for("auth.login"))

@auth_bp.route("/register", methods=["GET", "POST"])
@rol_requerido('administrador')
def register():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        rol = request.form.get("rol")

        if not username or not password or not rol:
            flash("Todos los campos son obligatorios.", "danger")
            return render_template("register.html")

        if Usuario.query.filter_by(nombre_usuario=username).first():
            flash("El usuario ya existe.", "danger")
            return redirect(url_for("auth.register"))

        nuevo_usuario = Usuario(
            nombre_usuario=username,
            contraseña=generate_password_hash(password),
            rol=rol
        )
        db.session.add(nuevo_usuario)
        db.session.commit()
        flash("Usuario registrado correctamente. Ya puedes iniciar sesión.", "success")
        return redirect(url_for("auth.login"))

    return render_template("register.html")

# CAMBIAR CONTRASEÑA
@auth_bp.route('/cambiar_contrasena', methods=['GET', 'POST'])
@login_required
def cambiar_contrasena():
    if request.method == 'POST':
        actual = request.form.get('actual', '').strip()
        nueva = request.form.get('nueva', '').strip()
        confirmar = request.form.get('confirmar', '').strip()

        print(f"DEBUG: Contraseña actual ingresada: '{actual}'")
        print(f"DEBUG: Contraseña nueva: '{nueva}', Confirmar: '{confirmar}'")

        if nueva != confirmar:
            flash('Las contraseñas no coinciden', 'danger')
            return redirect(url_for('auth.cambiar_contrasena'))
        
        print(f"DEBUG: current_user: {current_user}")
        print(f"DEBUG: current_user.id: {current_user.id}")
        usuario = Usuario.query.get(current_user.id)

        if not usuario:
            flash('Usuario no encontrado', 'danger')
            return redirect(url_for('auth.cambiar_contrasena'))

        print(f"DEBUG: Hash almacenado en BD: {usuario.contraseña}")
        print(f"DEBUG: Resultado check_password: {usuario.check_password(actual)}")

        if not usuario.check_password(actual):
            flash('La contraseña actual es incorrecta', 'danger')
            return redirect(url_for('auth.cambiar_contrasena'))

        usuario.set_password(nueva)
        db.session.commit()

        flash('Contraseña actualizada correctamente', 'success')
        return redirigir_dashboard(usuario)

    return render_template('auth/cambiar_contrasena.html')


