from flask import Blueprint, render_template, request, redirect, url_for, flash
from app import db
from app.models.usuario import Usuario
from app.utils.roles import rol_requerido
from werkzeug.security import generate_password_hash
from flask_login import login_required

usuarios_bp = Blueprint('usuarios', __name__, url_prefix='/usuarios')

# LISTAR USUARIOS
@usuarios_bp.route('/')
@login_required
@rol_requerido('administrador')
def listar_usuarios():
    usuarios = Usuario.query.filter(Usuario.rol != 'root').all()
    return render_template('usuarios/listar.html', usuarios=usuarios)

# CREAR USUARIO
@usuarios_bp.route('/crear', methods=['GET', 'POST'])
@login_required
@rol_requerido('administrador')
def crear_usuario():
    if request.method == 'POST':
        nombre_usuario = request.form['nombre_usuario']
        contraseña = request.form['contraseña']
        rol = request.form['rol']

        # Bloquear la creación de usuarios con rol 'root'
        if rol == 'root':
            flash('No tienes permiso para crear usuarios con este rol.', 'danger')
            return redirect(url_for('usuarios.crear_usuario'))

        usuario_existente = Usuario.query.filter_by(nombre_usuario=nombre_usuario).first()
        if usuario_existente:
            flash('El nombre de usuario ya está en uso.', 'danger')
            return redirect(url_for('usuarios.crear_usuario'))

        nuevo_usuario = Usuario(
            nombre_usuario=nombre_usuario,
            contraseña=generate_password_hash(contraseña),
            rol=rol
        )
        db.session.add(nuevo_usuario)
        db.session.commit()
        flash('Usuario creado correctamente.', 'success')
        return redirect(url_for('usuarios.listar_usuarios'))

    return render_template('usuarios/crear.html')

# EDITAR USUARIO
@usuarios_bp.route('/editar/<int:id>', methods=['GET', 'POST'])
@login_required
@rol_requerido('administrador')
def editar_usuario(id):
    usuario = Usuario.query.get_or_404(id)

    # Proteger al usuario root
    if usuario.rol == 'root':
        flash('No tienes permiso para modificar este usuario.', 'danger')
        return redirect(url_for('usuarios.listar_usuarios'))

    if request.method == 'POST':
        usuario.nombre_usuario = request.form['nombre_usuario']
        usuario.rol = request.form['rol']

        # Evitar cambiar a rol 'root' desde el formulario
        if usuario.rol == 'root':
            flash('No tienes permiso para asignar ese rol.', 'danger')
            return redirect(url_for('usuarios.listar_usuarios'))

        if request.form['contraseña']:
            usuario.contraseña = generate_password_hash(request.form['contraseña'])

        db.session.commit()
        flash('Usuario actualizado correctamente.', 'success')
        return redirect(url_for('usuarios.listar_usuarios'))

    return render_template('usuarios/editar.html', usuario=usuario)

# ELIMINAR USUARIO
@usuarios_bp.route('/eliminar/<int:id>')
@login_required
@rol_requerido('administrador')
def eliminar_usuario(id):
    usuario = Usuario.query.get_or_404(id)

    # Proteger al usuario root
    if usuario.rol == 'root':
        flash('No tienes permiso para eliminar este usuario.', 'danger')
        return redirect(url_for('usuarios.listar_usuarios'))

    db.session.delete(usuario)
    db.session.commit()
    flash('Usuario eliminado correctamente.', 'success')
    return redirect(url_for('usuarios.listar_usuarios'))


