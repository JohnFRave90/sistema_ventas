from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_user, logout_user, login_required
from werkzeug.security import check_password_hash, generate_password_hash
from app.models.usuario import Usuario
from app.models.vendedor import Vendedor  # Asegúrate de tener este modelo importado
from app import db
from app.routes.utils import UserWrapper

auth_bp = Blueprint("auth", __name__)

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        if not username or not password:
            flash("Por favor completa todos los campos.", "danger")
            return render_template("login.html")

        # 1. Buscar en tabla de usuarios
        usuario = Usuario.query.filter_by(nombre_usuario=username).first()
        if usuario and check_password_hash(usuario.contraseña, password):
            login_user(UserWrapper(usuario, "usuario"))
            return redirect(url_for("dashboard.dashboard"))

        # 2. Buscar en tabla de vendedores (por código o usuario)
        vendedor = Vendedor.query.filter(
            (Vendedor.nombre_usuario == username) |
            (Vendedor.codigo_vendedor == username)
        ).first()
        if vendedor and check_password_hash(vendedor.contraseña, password):
            login_user(UserWrapper(vendedor, "vendedor"))
            return redirect(url_for("dashboard.dashboard"))

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
