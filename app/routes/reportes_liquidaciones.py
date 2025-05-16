from flask import Blueprint, request, send_file, flash, redirect, url_for, render_template
from app.models import BD_LIQUIDACION, Vendedor
from app.utils.roles import rol_requerido
from flask_login import login_required
from io import BytesIO
import pandas as pd

reportes_liquidaciones_bp = Blueprint('reportes_liquidaciones', __name__)

# Vista de formulario de filtros
@reportes_liquidaciones_bp.route('/reporte')
@login_required
@rol_requerido('administrador', 'semiadmin')
def reporte_liquidaciones_form():
    return render_template('reportes/liquidaciones_reportes.html')

# Exportación Excel optimizada
@reportes_liquidaciones_bp.route('/export', methods=['GET'])
@login_required
@rol_requerido('administrador', 'semiadmin')
def export_liquidaciones_excel():
    fecha_inicio = request.args.get('fecha_inicio')
    fecha_fin = request.args.get('fecha_fin')
    vendedor_codigo = request.args.get('codigo_vendedor')

    if not fecha_inicio or not fecha_fin:
        flash("Debe seleccionar rango de fechas.", "danger")
        return redirect(url_for('reportes_liquidaciones.reporte_liquidaciones_form'))

    query = BD_LIQUIDACION.query.filter(
        BD_LIQUIDACION.fecha >= fecha_inicio,
        BD_LIQUIDACION.fecha <= fecha_fin
    )

    if vendedor_codigo:
        query = query.filter(BD_LIQUIDACION.codigo_vendedor == vendedor_codigo)

    liquidaciones = query.order_by(BD_LIQUIDACION.fecha.desc()).all()

    vendedores = Vendedor.query.all()
    vendedores_dict = {v.codigo_vendedor: v.nombre for v in vendedores}

    data = []
    for l in liquidaciones:
        total_pagado = l.pago_banco + l.pago_efectivo + l.pago_otros
        data.append({
            'Fecha': l.fecha.strftime('%Y-%m-%d'),
            'Código Liquidación': l.codigo,
            'Cod Vendedor': l.codigo_vendedor,
            'Nombre Vendedor': vendedores_dict.get(l.codigo_vendedor, '-'),
            'Venta Total': float(l.valor_venta),
            'Comisión': float(l.valor_comision),
            'A Panadería': float(l.valor_venta - l.valor_comision),
            'Descuento Cambios': float(l.descuento_cambios),
            'Total a Pagar': float(l.valor_a_pagar),
            'Pago Banco': float(l.pago_banco),
            'Pago Efectivo': float(l.pago_efectivo),
            'Pago Otros': float(l.pago_otros),
            'Total Pagado': float(total_pagado),
            'Comentarios': l.comentarios or ''
        })

    df = pd.DataFrame(data)

    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Liquidaciones')

        workbook = writer.book
        worksheet = writer.sheets['Liquidaciones']

        # Ajustar columnas automáticamente
        for i, column in enumerate(df.columns):
            column_width = max(df[column].astype(str).map(len).max(), len(column)) + 2
            worksheet.set_column(i, i, column_width)

    output.seek(0)
    filename = f"Liquidaciones_{fecha_inicio}_al_{fecha_fin}.xlsx"

    return send_file(output, download_name=filename, as_attachment=True)

@reportes_liquidaciones_bp.route('/export_diario', methods=['GET'])
@login_required
@rol_requerido('administrador', 'semiadmin')
def export_liquidaciones_diario_excel():
    fecha_inicio = request.args.get('fecha_inicio')
    fecha_fin = request.args.get('fecha_fin')

    if not fecha_inicio or not fecha_fin:
        flash("Debe seleccionar rango de fechas.", "danger")
        return redirect(url_for('reportes_liquidaciones.reporte_liquidaciones_form'))

    # Consulta agrupada por fecha y vendedor
    liquidaciones = BD_LIQUIDACION.query.filter(
        BD_LIQUIDACION.fecha >= fecha_inicio,
        BD_LIQUIDACION.fecha <= fecha_fin
    ).order_by(BD_LIQUIDACION.fecha, BD_LIQUIDACION.codigo_vendedor).all()

    vendedores = Vendedor.query.all()
    vendedores_dict = {v.codigo_vendedor: v.nombre for v in vendedores}

    data = []
    for l in liquidaciones:
        data.append({
            'Fecha': l.fecha.strftime('%Y-%m-%d'),
            'Cod Vendedor': l.codigo_vendedor,
            'Nombre Vendedor': vendedores_dict.get(l.codigo_vendedor, '-'),
            'Ventas del Día': float(l.valor_venta),
            'Comisión del Día': float(l.valor_comision),
            'A Panadería (sin cambios)': float(l.valor_venta - l.valor_comision),
            'Descuento Cambios': float(l.descuento_cambios),
            'Total a Pagar': float(l.valor_a_pagar),
        })

    df = pd.DataFrame(data)

    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Resumen Diario')

        workbook = writer.book
        worksheet = writer.sheets['Resumen Diario']

        # Ajuste columnas
        for i, column in enumerate(df.columns):
            column_width = max(df[column].astype(str).map(len).max(), len(column)) + 2
            worksheet.set_column(i, i, column_width)

    output.seek(0)
    filename = f"Liquidaciones_Consolidado_Diario_{fecha_inicio}_al_{fecha_fin}.xlsx"

    return send_file(output, download_name=filename, as_attachment=True)

@reportes_liquidaciones_bp.route('/api/resumen', methods=['GET'])
@login_required
@rol_requerido('administrador', 'semiadmin')
def api_resumen_liquidaciones():
    fecha_inicio = request.args.get('fecha_inicio')
    fecha_fin = request.args.get('fecha_fin')

    query = BD_LIQUIDACION.query.filter(
        BD_LIQUIDACION.fecha >= fecha_inicio,
        BD_LIQUIDACION.fecha <= fecha_fin
    )

    vendedores = Vendedor.query.all()
    vendedores_dict = {v.codigo_vendedor: v.nombre for v in vendedores}

    resumen_vendedores = {}
    resumen_pagos = {'Banco': 0, 'Efectivo': 0, 'Otros': 0}

    for l in query:
        vend = vendedores_dict.get(l.codigo_vendedor, 'Desconocido')
        if vend not in resumen_vendedores:
            resumen_vendedores[vend] = {'ventas': 0, 'panaderia': 0, 'pagado': 0}

        resumen_vendedores[vend]['ventas'] += float(l.valor_venta)
        resumen_vendedores[vend]['panaderia'] += float(l.valor_venta - l.valor_comision)
        resumen_vendedores[vend]['pagado'] += float(l.pago_banco + l.pago_efectivo + l.pago_otros)

        resumen_pagos['Banco'] += float(l.pago_banco)
        resumen_pagos['Efectivo'] += float(l.pago_efectivo)
        resumen_pagos['Otros'] += float(l.pago_otros)

    return {
        'vendedores': resumen_vendedores,
        'formas_pago': resumen_pagos
    }
