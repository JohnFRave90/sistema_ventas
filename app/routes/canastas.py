from flask import Blueprint, render_template, request, redirect, url_for, flash, session, Response
from flask_login import login_required
from app import db
from app.models.canastas import Canasta, MovimientoCanasta
from app.models.vendedor import Vendedor
from app.utils.roles import rol_requerido
import csv
from io import StringIO

bp_canastas = Blueprint('canastas', __name__, template_folder='../templates')

# Vista principal de canastas
@bp_canastas.route('/canastas')
@login_required
@rol_requerido('semiadmin', 'administrador')
def vista_canastas():
    # Número de página desde la URL, por defecto 1
    page = request.args.get('page', 1, type=int)

    # Obtener 50 canastas por página, ordenadas por fecha
    paginacion = Canasta.query.order_by(Canasta.fecha_registro.desc()).paginate(page=page, per_page=50)

    return render_template(
        'canastas/vista_principal.html',
        canastas=paginacion.items,
        pagination=paginacion
    )

# Registro de canastas
@bp_canastas.route('/canastas/registro', methods=['GET', 'POST'])
@login_required
@rol_requerido('semiadmin', 'administrador')
def registrar_canasta():
    from sqlalchemy import desc  # Para ordenar descendente

    # Datos por defecto para el formulario
    datos_formulario = {
        'codigo_barras': '',
        'tamano': 'Estandar',
        'color': 'Naranja',
        'estado': 'Nuevo',
        'actualidad': 'Disponible'
    }

    # Número de página actual desde los parámetros GET (por defecto 1)
    page = request.args.get('page', 1, type=int)

    # Si el formulario fue enviado (registro de nueva canasta)
    if request.method == 'POST':
        datos_formulario['codigo_barras'] = request.form['codigo_barras'].strip()
        datos_formulario['tamano']        = request.form['tamano']
        datos_formulario['color']         = request.form['color']
        datos_formulario['estado']        = request.form['estado']
        datos_formulario['actualidad']    = request.form['actualidad']

        # Validación de duplicado
        existente = Canasta.query.filter_by(codigo_barras=datos_formulario['codigo_barras']).first()
        if existente:
            flash('Error: Ya existe una canasta con ese código de barras.', 'danger')
        else:
            nueva_canasta = Canasta(
                codigo_barras = datos_formulario['codigo_barras'],
                tamaño         = datos_formulario['tamano'],
                color          = datos_formulario['color'],
                estado         = datos_formulario['estado'],
                actualidad     = datos_formulario['actualidad']
            )
            db.session.add(nueva_canasta)
            db.session.commit()
            flash('Canasta registrada correctamente.', 'success')

        # Después de registrar, redirige a la misma página (evita reenvío de formulario)
        return redirect(url_for('canastas.registrar_canasta'))

    # Obtener canastas paginadas (50 por página)
    paginacion = Canasta.query.order_by(desc(Canasta.fecha_registro)).paginate(page=page, per_page=50)

    return render_template(
        'canastas/registro.html',
        canastas=paginacion.items,
        pagination=paginacion,
        **datos_formulario
    )

# Exportar canastas a CSV
@bp_canastas.route('/canastas/exportar_csv')
@login_required
@rol_requerido('semiadmin', 'administrador')
def exportar_canastas_csv():
    canastas = Canasta.query.all()

    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(['Código de Barras', 'Tamaño', 'Color', 'Estado', 'Actualidad', 'Fecha de Registro'])

    for c in canastas:
        writer.writerow([
            c.codigo_barras,
            c.tamaño or '',
            c.color or '',
            c.estado or '',
            c.actualidad,
            c.fecha_registro.strftime('%Y-%m-%d %H:%M')
        ])

    output.seek(0)
    return Response(output.getvalue(),
                    mimetype='text/csv',
                    headers={"Content-Disposition": "attachment;filename=canastas_export.csv"})

@bp_canastas.route('/informe_canastas', methods=['GET'])
@login_required
@rol_requerido('semiadmin', 'administrador')
def informe_canastas():
    try:
        # Consulta agrupada con SQLAlchemy
        from sqlalchemy import func, case

        canastas_data = (db.session.query(
            Canasta.tamaño,
            Canasta.color,
            func.sum(case((Canasta.actualidad == 'Disponible', 1), else_=0)).label('disponibles'),
            func.sum(case((Canasta.actualidad == 'Prestada', 1), else_=0)).label('prestadas'),
            func.count().label('total')
        )
        .group_by(Canasta.tamaño, Canasta.color)
        .all())

        if not canastas_data:
            flash('No se encontraron canastas en el informe.', 'warning')
            return render_template('canastas/informe.html', canastas=[])

        # Si se solicita exportar a CSV
        if 'export' in request.args:
            output = StringIO()
            writer = csv.writer(output)
            writer.writerow(['Tamaño', 'Color', 'Disponibles', 'Prestadas', 'Total'])

            for row in canastas_data:
                writer.writerow([row.tamaño, row.color, row.disponibles, row.prestadas, row.total])

            output.seek(0)
            return Response(output.getvalue(),
                            mimetype='text/csv',
                            headers={"Content-Disposition": "attachment;filename=informe_canastas.csv"})

        # Render informe en HTML
        return render_template('canastas/informe.html', canastas=canastas_data)

    except Exception as e:
        flash(f'Ocurrió un error al generar el informe: {e}', 'danger')
        return render_template('canastas/informe.html', canastas=[])

@bp_canastas.route('/informe/buscar_canasta', methods=['GET', 'POST'])
@login_required
@rol_requerido('semiadmin', 'administrador')
def informe_buscar_canasta():
    canasta = None
    movimientos = []

    if request.method == 'POST':
        codigo_barras = request.form.get('codigo_barras', '').strip()

        if not codigo_barras:
            flash('Por favor ingrese un código de barras', 'warning')
            return render_template('canastas/informe_buscar.html', canasta=None, movimientos=[])

        # Consultar detalles de la canasta
        canasta = Canasta.query.filter_by(codigo_barras=codigo_barras).first()

        if not canasta:
            flash('Canasta no encontrada', 'danger')
            return render_template('canastas/informe_buscar.html', canasta=None, movimientos=[])

        # Consultar últimos 30 movimientos de esa canasta
        movimientos = (db.session.query(MovimientoCanasta, Vendedor)
            .join(Vendedor, MovimientoCanasta.codigo_vendedor == Vendedor.codigo_vendedor)
            .filter(MovimientoCanasta.codigo_barras == codigo_barras)
            .order_by(MovimientoCanasta.fecha_movimiento.desc())
            .limit(30)
            .all())

    return render_template('canastas/informe_buscar.html', canasta=canasta, movimientos=movimientos)

@bp_canastas.route('/canastas/<codigo_barras>/exportar_csv', methods=['GET'])
@login_required
@rol_requerido('semiadmin', 'administrador')
def exportar_csv_canasta(codigo_barras):
    canasta = Canasta.query.filter_by(codigo_barras=codigo_barras).first()
    if not canasta:
        flash('Canasta no encontrada', 'danger')
        return redirect(url_for('canastas.informe_buscar_canasta'))

    movimientos = (db.session.query(MovimientoCanasta, Vendedor)
                   .join(Vendedor, MovimientoCanasta.codigo_vendedor == Vendedor.codigo_vendedor)
                   .filter(MovimientoCanasta.codigo_barras == codigo_barras)
                   .order_by(MovimientoCanasta.fecha_movimiento.desc())
                   .all())

    from io import StringIO
    import csv

    output = StringIO()
    writer = csv.writer(output)

    writer.writerow(['Tamaño', 'Color'])
    writer.writerow([canasta.tamaño, canasta.color])

    writer.writerow([])  # Línea en blanco
    writer.writerow(['Fecha', 'Vendedor', 'Tipo de Movimiento'])

    for mov, vendedor in movimientos:
        writer.writerow([
            mov.fecha_movimiento.strftime('%Y-%m-%d %H:%M'),
            vendedor.nombre,
            mov.tipo_movimiento
        ])

    output.seek(0)
    return Response(output.getvalue(),
                    mimetype='text/csv',
                    headers={"Content-Disposition": f"attachment;filename=canasta_{codigo_barras}.csv"})

@bp_canastas.route('/canastas_perdidas', methods=['GET'])
@login_required
@rol_requerido('semiadmin', 'administrador')
def canastas_perdidas():
    from datetime import datetime, timedelta
    from sqlalchemy import func

    limite_fecha = datetime.now() - timedelta(days=7)

    # Subconsulta: obtener último movimiento "Sale" de cada canasta
    subq = (db.session.query(
                MovimientoCanasta.codigo_barras,
                func.max(MovimientoCanasta.fecha_movimiento).label('fecha')
            )
            .filter(MovimientoCanasta.tipo_movimiento == 'Sale')
            .group_by(MovimientoCanasta.codigo_barras)
            .subquery())

    # Consulta principal: canastas prestadas hace más de 7 días
    canastas_data = (db.session.query(
                        Canasta.codigo_barras,
                        subq.c.fecha.label('fecha_prestamo'),
                        Vendedor.nombre.label('nombre_vendedor')
                    )
                    .join(subq, Canasta.codigo_barras == subq.c.codigo_barras)
                    .join(MovimientoCanasta, (MovimientoCanasta.codigo_barras == Canasta.codigo_barras) & (MovimientoCanasta.fecha_movimiento == subq.c.fecha))
                    .join(Vendedor, MovimientoCanasta.codigo_vendedor == Vendedor.codigo_vendedor)
                    .filter(Canasta.actualidad == 'Prestada')
                    .filter(subq.c.fecha <= limite_fecha)
                    .all())

    # Calcular días prestada en Python
    canastas = []
    for c in canastas_data:
        dias_prestada = (datetime.now() - c.fecha_prestamo).days
        canastas.append({
            'codigo_barras': c.codigo_barras,
            'fecha_prestamo': c.fecha_prestamo.strftime('%Y-%m-%d'),
            'nombre_vendedor': c.nombre_vendedor,
            'dias_prestada': dias_prestada
        })

    return render_template('canastas/canastas_perdidas.html', canastas=canastas)


