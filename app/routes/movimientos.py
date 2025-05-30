from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_login import login_required, current_user
from flask import send_file, Response
from app import db
from sqlalchemy import text
from app.models.canastas import Canasta, MovimientoCanasta
from app.models.vendedor import Vendedor
from datetime import datetime
from app.utils.roles         import rol_requerido

bp_movimientos = Blueprint('movimientos', __name__, template_folder='../templates')

@bp_movimientos.route('/movimientos', methods=['GET', 'POST'])
@login_required
@rol_requerido('semiadmin','administrador')
def registrar_movimiento():
    if 'contador_registros' not in session:
        session['contador_registros'] = 0

    if request.method == 'POST':
        vendedor_nombre = request.form['vendedor']
        tipo = request.form['tipo']
        codigo_barras = request.form['codigo_barras'].strip()

        if not (vendedor_nombre and tipo and codigo_barras):
            flash('Todos los campos son obligatorios.', 'danger')
        else:
            vendedor = Vendedor.query.filter_by(nombre=vendedor_nombre).first()
            if not vendedor:
                flash('Vendedor no encontrado.', 'danger')
            else:
                canasta = Canasta.query.filter_by(codigo_barras=codigo_barras).first()
                if not canasta:
                    flash('Canasta no encontrada.', 'danger')
                else:
                    # Validar movimientos anteriores
                    ultima = MovimientoCanasta.query.filter_by(codigo_barras=codigo_barras).order_by(MovimientoCanasta.fecha_movimiento.desc()).first()

                    if tipo == 'Entra' and not ultima:
                        flash('No se ha registrado ningún movimiento para esta canasta, no se puede devolver.', 'danger')
                    elif ultima and tipo == 'Entra' and ultima.codigo_vendedor != vendedor.codigo_vendedor:
                        flash('Esta canasta ha sido prestada a otro vendedor. No puedes devolverla.', 'danger')
                    elif tipo == 'Sale' and canasta.actualidad == 'Prestada':
                        flash('Esta canasta ya ha sido prestada.', 'danger')
                    elif tipo == 'Entra' and canasta.actualidad == 'Disponible':
                        flash('Esta canasta no ha sido prestada.', 'danger')
                    else:
                        # Registrar movimiento
                        nuevo_mov = MovimientoCanasta(
                            codigo_vendedor=vendedor.codigo_vendedor,
                            tipo_movimiento=tipo,
                            codigo_barras=codigo_barras,
                            fecha_movimiento=datetime.now()
                        )
                        db.session.add(nuevo_mov)

                        # Actualizar actualidad de la canasta
                        if tipo == 'Sale':
                            canasta.actualidad = 'Prestada'
                        elif tipo == 'Entra':
                            canasta.actualidad = 'Disponible'

                        db.session.commit()

                        flash('Movimiento registrado correctamente.', 'success')

                        # Mantener datos en sesión
                        if vendedor_nombre != session.get('vendedor_seleccionado') or tipo != session.get('tipo_seleccionado'):
                            session['contador_registros'] = 0

                        session['vendedor_seleccionado'] = vendedor_nombre
                        session['tipo_seleccionado'] = tipo
                        session['codigo_barras'] = ''
                        session['contador_registros'] += 1

        return redirect(url_for('movimientos.registrar_movimiento'))

    # Datos para GET
    vendedores = Vendedor.query.order_by(Vendedor.nombre.asc()).all()
    movimientos = (db.session.query(MovimientoCanasta, Vendedor)
                   .join(Vendedor, MovimientoCanasta.codigo_vendedor == Vendedor.codigo_vendedor)
                   .order_by(MovimientoCanasta.fecha_movimiento.desc())
                   .limit(100)
                   .all())

    return render_template('movimientos/registro.html',
                           vendedores=vendedores,
                           vendedor_seleccionado=session.get('vendedor_seleccionado', ''),
                           tipo_seleccionado=session.get('tipo_seleccionado', ''),
                           codigo_barras=session.get('codigo_barras', ''),
                           contador_registros=session['contador_registros'],
                           movimientos=movimientos)

@bp_movimientos.route('/informe_movimientos', methods=['GET'])
@login_required
@rol_requerido('semiadmin', 'administrador')
def informe_movimientos():
    try:
        fecha_inicio = request.args.get('fecha_inicio')
        fecha_fin = request.args.get('fecha_fin')

        if not fecha_inicio or not fecha_fin:
            fecha_inicio = session.get('fecha_inicio')
            fecha_fin = session.get('fecha_fin')

            if not fecha_inicio or not fecha_fin:
                flash('Por favor, selecciona un rango de fechas', 'warning')
                return render_template('movimientos/informe.html', movimientos=[])

        # Guardar en sesión
        session['fecha_inicio'] = fecha_inicio
        session['fecha_fin'] = fecha_fin

        from datetime import datetime

        fecha_inicio_dt = datetime.strptime(f"{fecha_inicio} 00:00:00", "%Y-%m-%d %H:%M:%S")
        fecha_fin_dt = datetime.strptime(f"{fecha_fin} 23:59:59", "%Y-%m-%d %H:%M:%S")

        # Consulta con SQLAlchemy
        movimientos = (db.session.query(MovimientoCanasta, Vendedor)
            .join(Vendedor, MovimientoCanasta.codigo_vendedor == Vendedor.codigo_vendedor)
            .filter(MovimientoCanasta.fecha_movimiento.between(fecha_inicio_dt, fecha_fin_dt))
            .order_by(MovimientoCanasta.fecha_movimiento.desc())
            .all())

        if 'export' in request.args:
            # Exportar CSV
            from io import StringIO
            import csv

            output = StringIO()
            writer = csv.writer(output)
            writer.writerow(['Fecha', 'Vendedor', 'Tipo', 'Código de Barras'])

            for mov, vendedor in movimientos:
                writer.writerow([
                    mov.fecha_movimiento.strftime('%Y-%m-%d %H:%M'),
                    vendedor.nombre,
                    mov.tipo_movimiento,
                    mov.codigo_barras
                ])

            output.seek(0)
            return Response(output.getvalue(),
                            mimetype='text/csv',
                            headers={"Content-Disposition": f"attachment;filename=informe_movimientos_{fecha_inicio}_a_{fecha_fin}.csv"})

        return render_template('movimientos/informe.html', movimientos=movimientos,
                               fecha_inicio=fecha_inicio, fecha_fin=fecha_fin)

    except Exception as e:
        flash(f'Ocurrió un error al generar el informe: {e}', 'danger')
        return render_template('movimientos/informe.html', movimientos=[])

@bp_movimientos.route('/movimientos/informe_vendedores', methods=['GET'])
@login_required
@rol_requerido('semiadmin', 'administrador')
def informe_vendedores():
    try:
        fecha = request.args.get('fecha')

        if not fecha:
            flash('Por favor, selecciona una fecha', 'warning')
            return render_template('vendedores/informe.html', vendedores=[])

        session['fecha'] = fecha  # Guardar fecha en sesión

        from datetime import datetime
        from sqlalchemy import func, case

        fecha_inicio_dt = datetime.strptime(f"{fecha} 00:00:00", "%Y-%m-%d %H:%M:%S")
        fecha_fin_dt = datetime.strptime(f"{fecha} 23:59:59", "%Y-%m-%d %H:%M:%S")

        # Consulta agrupada
        vendedores_data = (db.session.query(
            Vendedor.nombre,
            func.sum(case((MovimientoCanasta.tipo_movimiento == 'Sale', 1), else_=0)).label('canastas_prestadas'),
            func.sum(case((MovimientoCanasta.tipo_movimiento == 'Entra', 1), else_=0)).label('canastas_devueltas')
        )
        .join(Vendedor, MovimientoCanasta.codigo_vendedor == Vendedor.codigo_vendedor)
        .filter(MovimientoCanasta.fecha_movimiento.between(fecha_inicio_dt, fecha_fin_dt))
        .group_by(Vendedor.nombre)
        .all())

        if not vendedores_data:
            flash('No se encontraron movimientos para esta fecha', 'warning')
            return render_template('vendedores/informe.html', vendedores=[])

        if 'export' in request.args:
            # Exportar CSV
            from io import StringIO
            import csv

            output = StringIO()
            writer = csv.writer(output)
            writer.writerow(['Vendedor', 'Canastas Prestadas', 'Canastas Devueltas'])

            for v in vendedores_data:
                writer.writerow([v.nombre, v.canastas_prestadas, v.canastas_devueltas])

            output.seek(0)
            return Response(output.getvalue(),
                            mimetype='text/csv',
                            headers={"Content-Disposition": f"attachment;filename=informe_vendedores_{fecha}.csv"})

        return render_template('vendedores/informe.html', vendedores=vendedores_data, fecha=fecha)

    except Exception as e:
        flash(f'Ocurrió un error al generar el informe: {e}', 'danger')
        return render_template('vendedores/informe.html', vendedores=[])

@bp_movimientos.route('/resumen_canastas_por_vendedor', methods=['GET', 'POST'])
@login_required
@rol_requerido('semiadmin', 'administrador')
def resumen_canastas_vendedor():
    from sqlalchemy import func
    from sqlalchemy.orm import aliased

    # Lista de vendedores para el formulario
    vendedores = Vendedor.query.order_by(Vendedor.nombre.asc()).all()

    canastas = []
    resumen = []

    if request.method == 'POST':
        vendedor_nombre = request.form.get('vendedor')

        vendedor = Vendedor.query.filter_by(nombre=vendedor_nombre).first()

        if not vendedor:
            flash('Vendedor no encontrado', 'danger')
            return render_template('vendedores/resumen_canastas.html', vendedores=vendedores, canastas=[], resumen=[])

        # Aliased para representar el último movimiento por canasta
        UltimoMov = aliased(MovimientoCanasta)

        # Subconsulta: ID del último movimiento por cada canasta
        subconsulta = (
            db.session.query(
                func.max(MovimientoCanasta.id).label('ultimo_id')
            )
            .group_by(MovimientoCanasta.codigo_barras)
            .subquery()
        )

        # Consulta principal: resumen de canastas prestadas actualmente por ese vendedor
        resumen = (
            db.session.query(
                Canasta.tamaño,
                Canasta.color,
                func.count().label('cantidad')
            )
            .join(UltimoMov, Canasta.codigo_barras == UltimoMov.codigo_barras)
            .filter(
                UltimoMov.id.in_(subconsulta),
                UltimoMov.tipo_movimiento == 'Sale',
                UltimoMov.codigo_vendedor == vendedor.codigo_vendedor
            )
            .group_by(Canasta.tamaño, Canasta.color)
            .all()
        )

        # Detalle de canastas prestadas activas por ese vendedor
        canastas = (
            db.session.query(
                Canasta.codigo_barras,
                Canasta.tamaño,
                Canasta.color,
                UltimoMov.fecha_movimiento
            )
            .join(UltimoMov, Canasta.codigo_barras == UltimoMov.codigo_barras)
            .filter(
                UltimoMov.id.in_(subconsulta),
                UltimoMov.tipo_movimiento == 'Sale',
                UltimoMov.codigo_vendedor == vendedor.codigo_vendedor
            )
            .order_by(UltimoMov.fecha_movimiento.desc())
            .all()
        )

    return render_template('vendedores/resumen_canastas.html',
                           vendedores=vendedores,
                           canastas=canastas,
                           resumen=resumen)

@bp_movimientos.route('/informe_canastas_prestadas_por_vendedor', methods=['GET'])
@login_required
@rol_requerido('semiadmin', 'administrador')
def informe_canastas_prestadas_por_vendedor():
    from sqlalchemy import func, case

    try:
        # Consulta para contar canastas prestadas activas por vendedor
        canastas_prestadas = (db.session.query(
            Vendedor.nombre,
            (
                func.sum(case((MovimientoCanasta.tipo_movimiento == 'Sale', 1), else_=0)) -
                func.sum(case((MovimientoCanasta.tipo_movimiento == 'Entra', 1), else_=0))
            ).label('canastas_prestadas_activas')
        )
        .join(MovimientoCanasta, MovimientoCanasta.codigo_vendedor == Vendedor.codigo_vendedor)
        .group_by(Vendedor.nombre)
        .order_by(func.sum(case((MovimientoCanasta.tipo_movimiento == 'Sale', 1), else_=0)) -
                  func.sum(case((MovimientoCanasta.tipo_movimiento == 'Entra', 1), else_=0)).desc())
        .all())

        if 'export' in request.args:
            from io import StringIO
            import csv

            output = StringIO()
            writer = csv.writer(output)
            writer.writerow(['Vendedor', 'Canastas Prestadas Activas'])

            for v in canastas_prestadas:
                writer.writerow([v.nombre, v.canastas_prestadas_activas])

            output.seek(0)
            return Response(output.getvalue(),
                            mimetype='text/csv',
                            headers={"Content-Disposition": "attachment;filename=informe_canastas_prestadas.csv"})

        return render_template('vendedores/informe_canastas_prestadas.html', canastas_prestadas=canastas_prestadas)

    except Exception as e:
        flash(f'Ocurrió un error al generar el informe: {e}', 'danger')
        return render_template('vendedores/informe_canastas_prestadas.html', canastas_prestadas=[])

# Borrar todos los movimientos (solo root)
@bp_movimientos.route('/borrar_movimientos', methods=['POST'])
@login_required
@rol_requerido('root')
def borrar_movimientos():
    try:
        db.session.execute(text('DELETE FROM movimientos'))
        db.session.execute(text('UPDATE canastas SET actualidad = "Disponible"'))
        db.session.commit()
        flash('✔ Todos los movimientos han sido borrados y las canastas se actualizaron a "Disponible".', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'❌ Error al borrar los movimientos: {e}', 'danger')
    return redirect(url_for('dashboard.dashboard'))  # Redirige a dashboard o página principal

# Borrar todas las canastas (solo root)
@bp_movimientos.route('/borrar_canastas', methods=['POST'])
@login_required
@rol_requerido('root')
def borrar_canastas():
    try:
        db.session.execute(text('DELETE FROM canastas'))
        db.session.commit()
        flash('✔ Todas las canastas han sido borradas.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'❌ Error al borrar las canastas: {e}', 'danger')
    return redirect(url_for('dashboard.dashboard'))


