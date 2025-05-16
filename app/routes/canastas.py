# app/routes/canastas.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_login import login_required, current_user
from app import db
from app.models.canastas import Canasta, MovimientoCanasta
from flask import Response
import csv
from io import StringIO

bp_canastas = Blueprint('canastas', __name__, template_folder='../templates')

# Vista principal de canastas
@bp_canastas.route('/canastas')
@login_required
def vista_canastas():
    if current_user.rol not in ['administrador', 'semiadmin']:
        flash('Acceso restringido a canastas.', 'danger')
        return redirect(url_for('dashboard.dashboard'))
    canastas = Canasta.query.all()
    return render_template('canastas/vista_principal.html', canastas=canastas)

@bp_canastas.route('/canastas/registro', methods=['GET', 'POST'])
@login_required
def registrar_canasta():
    if current_user.rol not in ['administrador', 'semiadmin']:
        flash('Acceso restringido a este módulo.', 'danger')
        return redirect(url_for('dashboard.dashboard'))

    # Valores por defecto para cargar en el formulario
    datos_formulario = {
        'codigo_barras': '',
        'tamano': 'Estandar',
        'color': 'Naranja',
        'estado': 'Nuevo',
        'actualidad': 'Disponible'
    }

    if request.method == 'POST':
        datos_formulario['codigo_barras'] = request.form['codigo_barras'].strip()
        datos_formulario['tamano'] = request.form['tamano']
        datos_formulario['color'] = request.form['color']
        datos_formulario['estado'] = request.form['estado']
        datos_formulario['actualidad'] = request.form['actualidad']

        existente = Canasta.query.filter_by(codigo_barras=datos_formulario['codigo_barras']).first()
        if existente:
            flash('Error: Ya existe una canasta con ese código de barras.', 'danger')
        else:
            nueva_canasta = Canasta(
                codigo_barras=datos_formulario['codigo_barras'],
                tamaño=datos_formulario['tamano'],
                color=datos_formulario['color'],
                estado=datos_formulario['estado'],
                actualidad=datos_formulario['actualidad']
            )
            db.session.add(nueva_canasta)
            db.session.commit()
            flash('Canasta registrada correctamente.', 'success')

        # Mostrar nuevamente el formulario con las últimas opciones seleccionadas
        canastas = Canasta.query.order_by(Canasta.fecha_registro.desc()).all()
        return render_template('canastas/registro.html', canastas=canastas, **datos_formulario)

    # En GET inicial
    canastas = Canasta.query.order_by(Canasta.fecha_registro.desc()).all()
    return render_template('canastas/registro.html', canastas=canastas, **datos_formulario)

@bp_canastas.route('/canastas/exportar_csv')
@login_required
def exportar_canastas_csv():
    if current_user.rol not in ['Administrador', 'Semiadmin']:
        flash('Acceso restringido a este módulo.', 'danger')
        return redirect(url_for('main.dashboard'))

    # Consulta todas las canastas
    canastas = Canasta.query.all()

    # Creamos el buffer en memoria
    output = StringIO()
    writer = csv.writer(output)

    # Escribimos la cabecera
    writer.writerow(['Código de Barras', 'Tamaño', 'Color', 'Estado', 'Actualidad', 'Fecha de Registro'])

    # Escribimos cada fila
    for c in canastas:
        writer.writerow([
            c.codigo_barras,
            c.tamaño or '',
            c.color or '',
            c.estado or '',
            c.actualidad,
            c.fecha_registro.strftime('%Y-%m-%d %H:%M')
        ])

    # Retornamos el CSV como archivo descargable
    output.seek(0)
    return Response(output.getvalue(),
                    mimetype='text/csv',
                    headers={"Content-Disposition": "attachment;filename=canastas_export.csv"})
