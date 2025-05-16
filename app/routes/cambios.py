# app/routes/cambios.py

from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_required, current_user
from app import db
from app.models.cambio import BD_CAMBIO
from app.models.vendedor import Vendedor
from app.utils.roles import rol_requerido
from datetime import datetime

cambios_bp = Blueprint('cambios', __name__, url_prefix='/cambios')

@cambios_bp.route('/crear', methods=['GET', 'POST'])
@login_required
@rol_requerido('administrador', 'semiadmin')
def crear_cambio():
    vendedores = Vendedor.query.all()

    if request.method == 'POST':
        try:
            fecha = datetime.strptime(request.form['fecha'], '%Y-%m-%d').date()
            codigo_vendedor = request.form['vendedor']
            valor_cambio = float(request.form['valor_cambio'])
        except (ValueError, KeyError):
            flash("Datos inválidos.", "danger")
            return redirect(url_for('cambios.crear_cambio'))

        comentarios = request.form.get('comentarios', '')

        cambio = BD_CAMBIO(
            fecha=fecha,
            codigo_vendedor=codigo_vendedor,
            valor_cambio=valor_cambio,
            comentarios=comentarios,
            usuario_creador=current_user.nombre_usuario
        )
        db.session.add(cambio)
        db.session.commit()

        flash("Cambio registrado correctamente.", "success")
        return redirect(url_for('cambios.listar_cambios'))

    return render_template('cambios/crear.html', vendedores=vendedores)

@cambios_bp.route('/listar')
@login_required
@rol_requerido('administrador', 'semiadmin')
def listar_cambios():
    query = BD_CAMBIO.query

    fecha_inicio = request.args.get('fecha_inicio')
    fecha_fin = request.args.get('fecha_fin')
    codigo_vendedor = request.args.get('codigo_vendedor')

    if fecha_inicio:
        query = query.filter(BD_CAMBIO.fecha >= fecha_inicio)
    if fecha_fin:
        query = query.filter(BD_CAMBIO.fecha <= fecha_fin)
    if codigo_vendedor:
        query = query.filter(BD_CAMBIO.codigo_vendedor.like(f"%{codigo_vendedor.strip()}%"))

    cambios = query.order_by(BD_CAMBIO.fecha.desc(), BD_CAMBIO.id.desc()).all()

    # Cargar vendedores para mostrar nombres
    vendedores = Vendedor.query.all()
    vendedores_dict = {v.codigo_vendedor: v for v in vendedores}

    return render_template('cambios/listar.html', cambios=cambios, vendedores_dict=vendedores_dict)

@cambios_bp.route('/editar/<int:id>', methods=['GET', 'POST'])
@login_required
@rol_requerido('administrador')
def editar_cambio(id):
    cambio = BD_CAMBIO.query.get_or_404(id)
    vendedores = Vendedor.query.order_by(Vendedor.nombre).all()

    if request.method == 'POST':
        try:
            fecha = datetime.strptime(request.form['fecha'], '%Y-%m-%d').date()
            codigo_vendedor = request.form['vendedor']
            valor_cambio = float(request.form['valor_cambio'])
            comentarios = request.form.get('comentarios', '')
        except ValueError:
            flash("Datos inválidos.", "danger")
            return redirect(url_for('cambios.editar_cambio', id=id))

        # Validar que no haya duplicados en otra fila
        duplicado = BD_CAMBIO.query.filter(
            BD_CAMBIO.fecha == fecha,
            BD_CAMBIO.codigo_vendedor == codigo_vendedor,
            BD_CAMBIO.id != id
        ).first()
        if duplicado:
            flash("Ya existe un cambio registrado para ese vendedor en esa fecha.", "warning")
            return redirect(url_for('cambios.editar_cambio', id=id))

        cambio.fecha = fecha
        cambio.codigo_vendedor = codigo_vendedor
        cambio.valor_cambio = valor_cambio
        cambio.comentarios = comentarios

        db.session.commit()
        flash("Cambio actualizado correctamente.", "success")
        return redirect(url_for('cambios.listar_cambios'))

    return render_template('cambios/editar.html', cambio=cambio, vendedores=vendedores)

@cambios_bp.route('/eliminar/<int:id>', methods=['POST'])
@login_required
@rol_requerido('administrador')
def eliminar_cambio(id):
    cambio = BD_CAMBIO.query.get_or_404(id)
    db.session.delete(cambio)
    db.session.commit()
    flash(f"Cambio del {cambio.fecha.strftime('%d/%m/%Y')} para {cambio.codigo_vendedor} eliminado correctamente.", "success")
    return redirect(url_for('cambios.listar_cambios'))
