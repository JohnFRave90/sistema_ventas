from flask import Blueprint, render_template, request, redirect, url_for, flash
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from app.models.vendedor import Vendedor
from app import db
from flask_login import login_required, current_user
from app.utils.roles import rol_requerido

vendedores_bp = Blueprint('vendedores', __name__, url_prefix='/vendedores')

@vendedores_bp.route('/crear', methods=['GET', 'POST'])
@login_required
@rol_requerido('administrador')
def crear_vendedor():
    if current_user.rol != 'administrador':
        flash("Acceso restringido solo para administradores.", "danger")
        return redirect(url_for('dashboard.dashboard'))

    if request.method == 'POST':
        # Validación explícita: evita 500 por campos ausentes o numéricos inválidos.
        codigo = (request.form.get('codigo') or '').strip()
        nombre = (request.form.get('nombre') or '').strip()
        usuario = (request.form.get('usuario') or '').strip()
        contrasena = request.form.get('contraseña') or ''
        if not codigo or not nombre or not usuario or not contrasena:
            flash("Todos los campos son obligatorios.", "danger")
            return render_template('vendedores/crear.html')

        try:
            comision_panaderia = float(request.form.get('comision_panaderia') or 0)
            comision_bizcocheria = float(request.form.get('comision_bizcocheria') or 0)
        except (ValueError, TypeError):
            flash("Las comisiones deben ser numéricas.", "danger")
            return render_template('vendedores/crear.html')

        # Pre-chequeo de duplicados: mensaje claro en vez de IntegrityError crudo (500).
        if Vendedor.query.filter_by(codigo_vendedor=codigo).first():
            flash(f"Ya existe un vendedor con el código '{codigo}'.", "danger")
            return render_template('vendedores/crear.html')
        if Vendedor.query.filter_by(nombre_usuario=usuario).first():
            flash(f"Ya existe un vendedor con el usuario '{usuario}'.", "danger")
            return render_template('vendedores/crear.html')

        nuevo = Vendedor(
            codigo_vendedor=codigo,
            nombre=nombre,
            nombre_usuario=usuario,
            comision_panaderia=comision_panaderia,
            comision_bizcocheria=comision_bizcocheria,
        )
        nuevo.set_password(contrasena)

        try:
            db.session.add(nuevo)
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash("No se pudo registrar: código o usuario ya existen.", "danger")
            return render_template('vendedores/crear.html')
        except SQLAlchemyError as error:
            db.session.rollback()
            flash(f"Error de base de datos al registrar el vendedor: {error}", "danger")
            return render_template('vendedores/crear.html')

        flash("Vendedor registrado correctamente.", "success")
        return redirect(url_for('vendedores.crear_vendedor'))

    return render_template('vendedores/crear.html')

@vendedores_bp.route('/listar')
@login_required
@rol_requerido('administrador','semiadmin')
def listar_vendedores():
    if current_user.rol not in ['administrador', 'semiadmin']:
        flash("Acceso restringido.", "danger")
        return redirect(url_for('dashboard.dashboard'))

    vendedores = Vendedor.query.all()
    return render_template('vendedores/listar.html', vendedores=vendedores)


@vendedores_bp.route('/editar/<int:id>', methods=['GET', 'POST'])
@login_required
@rol_requerido('administrador')
def editar_vendedor(id):
    if current_user.rol != 'administrador':
        flash("Acceso restringido.", "danger")
        return redirect(url_for('dashboard.dashboard'))

    vendedor = Vendedor.query.get_or_404(id)

    if request.method == 'POST':
        vendedor.nombre = request.form['nombre']
        vendedor.nombre_usuario = request.form['usuario']
        vendedor.codigo_vendedor = request.form['codigo']
        vendedor.comision_panaderia = request.form['comision_panaderia']
        vendedor.comision_bizcocheria = request.form['comision_bizcocheria']
        
        nueva_clave = request.form.get('contraseña')
        if nueva_clave:
            vendedor.set_password(nueva_clave)

        db.session.commit()
        flash("Vendedor actualizado correctamente.", "success")
        return redirect(url_for('vendedores.listar_vendedores'))

    return render_template('vendedores/editar.html', vendedor=vendedor)


@vendedores_bp.route('/eliminar/<int:id>')
@login_required
@rol_requerido('administrador')
def eliminar_vendedor(id):
    if current_user.rol != 'administrador':
        flash("Acceso restringido.", "danger")
        return redirect(url_for('dashboard.dashboard'))

    vendedor = Vendedor.query.get_or_404(id)
    db.session.delete(vendedor)
    db.session.commit()
    flash("Vendedor eliminado.", "success")
    return redirect(url_for('vendedores.listar_vendedores'))
