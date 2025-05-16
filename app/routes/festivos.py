from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from app import db
from app.models.festivo import Festivo
from app.utils.roles import rol_requerido
from datetime import datetime
from datetime import date

festivos_bp = Blueprint('festivos', __name__, url_prefix='/festivos')

@festivos_bp.route('/listar')
@login_required
@rol_requerido('administrador')
def listar_festivos():
    festivos = Festivo.query.order_by(Festivo.fecha).all()
    return render_template('festivos/listar.html', festivos=festivos)

@festivos_bp.route('/crear', methods=['GET','POST'])
@login_required
@rol_requerido('administrador')
def crear_festivo():
    if request.method == 'POST':
        fecha_str = request.form.get('fecha')
        nota      = request.form.get('nota','').strip()
        try:
            fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()
        except ValueError:
            flash("Fecha inválida.", "danger")
            return redirect(url_for('festivos.crear_festivo'))

        if Festivo.query.filter_by(fecha=fecha).first():
            flash("Ese día ya está marcado como festivo.", "warning")
        else:
            nuevo = Festivo(fecha=fecha, nota=nota)
            db.session.add(nuevo)
            db.session.commit()
            flash("Festivo creado.", "success")
            return redirect(url_for('festivos.listar_festivos'))

    return render_template('festivos/editar.html', festivo=None)

@festivos_bp.route('/editar/<int:id>', methods=['GET','POST'])
@login_required
@rol_requerido('administrador')
def editar_festivo(id):
    festivo = Festivo.query.get_or_404(id)
    if request.method == 'POST':
        fecha_str = request.form.get('fecha')
        nota      = request.form.get('nota','').strip()
        try:
            fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()
        except ValueError:
            flash("Fecha inválida.", "danger")
            return redirect(url_for('festivos.editar_festivo', id=id))

        # Si cambió fecha y ya existe otro registro
        ex = Festivo.query.filter(Festivo.fecha==fecha, Festivo.id!=id).first()
        if ex:
            flash("Ya existe otro festivo con esa fecha.", "warning")
        else:
            festivo.fecha = fecha
            festivo.nota  = nota
            db.session.commit()
            flash("Festivo actualizado.", "success")
            return redirect(url_for('festivos.listar_festivos'))

    return render_template('festivos/editar.html', festivo=festivo)

@festivos_bp.route('/eliminar/<int:id>', methods=['POST'])
@login_required
@rol_requerido('administrador')
def eliminar_festivo(id):
    festivo = Festivo.query.get_or_404(id)
    db.session.delete(festivo)
    db.session.commit()
    flash("Festivo eliminado.", "success")
    return redirect(url_for('festivos.listar_festivos'))

@festivos_bp.route('/sync', methods=['POST'])
@login_required
@rol_requerido('administrador')
def sync_festivos():
    from app.utils.fechas import sync_festivos_oficiales
    # sincroniza solo el año en curso (puedes pasar más años si quieres)
    sync_festivos_oficiales([ date.today().year ])
    flash("🎉 Festivos oficiales sincronizados correctamente.", "success")
    return redirect(url_for('festivos.listar_festivos'))

