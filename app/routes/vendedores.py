from flask import Blueprint, render_template, request, redirect, url_for, flash
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
        nuevo = Vendedor(
            codigo_vendedor=request.form['codigo'],
            nombre=request.form['nombre'],
            nombre_usuario=request.form['usuario'],
            comision_panaderia=request.form['comision_panaderia'],
            comision_bizcocheria=request.form['comision_bizcocheria']
        )
        nuevo.set_password(request.form['contraseña'])

        db.session.add(nuevo)
        db.session.commit()
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
