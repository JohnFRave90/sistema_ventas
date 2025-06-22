# app/utils/pdf_utils.py

from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, Spacer, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from app.models.producto import Producto

# Media carta en retrato (5.5"×8.5")
MEDIA_CARTA = (letter[1] / 2, letter[0])

# Títulos según tipo de documento
titles = {
    'pedido':     'ORDEN DE PEDIDO INCOLPAN - DISTRIBUIDORES',
    'extra':      'ORDEN DE EXTRA INCOLPAN - DISTRIBUIDORES',
    'devolucion': 'ORDEN DE DEVOLUCIÓN INCOLPAN - DISTRIBUIDORES',
    'venta':      'VENTAS INCOLPAN - DISTRIBUIDORES'
}

# Etiqueta de documento
label_doc = {
    'pedido': 'Pedido', 'extra': 'Extra',
    'devolucion': 'Devolución', 'venta': 'Venta'
}

def generate_pdf_document(modelo, vendedor, logo_path, tipo):
    """
    Genera un PDF media carta en retrato con el formato:
      - 'pedido', 'extra', 'devolucion': columnas Producto, Cant., V. Unit., Subtotal
      - 'venta': cuadro de información + columnas Cód., Producto, Cant., Subtotal, Comisión, Pagar Pan.
    - Tamaño de letra de tabla: 8 pts, con ajuste automático de alto de filas.
    - Metadata en una sola línea debajo del título.
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=MEDIA_CARTA,
        leftMargin=15, rightMargin=15,
        topMargin=15, bottomMargin=15
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'Title', parent=styles['Heading1'], alignment=1,
        fontSize=14, spaceAfter=6
    )
    meta_style = ParagraphStyle(
        'Meta', parent=styles['Normal'], fontSize=12, leading=11
    )
    cell_style = ParagraphStyle(
        'Cell', parent=styles['Normal'], fontSize=6.5, leading=8
    )
    header_cell = ParagraphStyle(
        'HeaderCell', parent=styles['Normal'], fontSize=8, leading=9,
        alignment=1, fontName='Helvetica-Bold'
    )

    elements = []

    # — Título —
    elements.append(Paragraph(titles[tipo], title_style))

    # — Metadata en una sola línea —
    header_text = (
        f"Vendedor: {vendedor.nombre}    Fecha: {modelo.fecha.strftime('%d/%m/%Y')}    "
        f"{label_doc[tipo]}: {modelo.consecutivo}"
    )
    elements.append(Paragraph(header_text, meta_style))
    elements.append(Spacer(1, 6))

    # Precarga nombres de productos
    cods = [it.producto_cod for it in modelo.items]
    productos = {
        p.codigo: p.nombre
        for p in Producto.query.filter(Producto.codigo.in_(cods)).all()
    }

    # — Cuadro de información para venta (igual al formulario) —
    if tipo == 'venta':
        info_data = [
            [
                Paragraph('Dev. Ant.', header_cell),
                Paragraph(modelo.codigo_dev_anterior or '-', cell_style),
                Paragraph('Pedido',    header_cell),
                Paragraph(modelo.codigo_pedido     or '-', cell_style)
            ],
            [
                Paragraph('Extra',     header_cell),
                Paragraph(modelo.codigo_extra      or '-', cell_style),
                Paragraph('Dev. Día',  header_cell),
                Paragraph(modelo.codigo_dev_dia    or '-', cell_style)
            ]
        ]
        info_col_ws = [
            doc.width * 0.15, doc.width * 0.35,
            doc.width * 0.15, doc.width * 0.35
        ]
        info_tbl = Table(info_data, colWidths=info_col_ws, hAlign='LEFT')
        info_tbl.setStyle(TableStyle([
            ('GRID',        (0,0), (-1,-1),      0.5, colors.black),
            ('BACKGROUND',  (0,0), (-1,0),       colors.lightgrey),
            ('VALIGN',      (0,0), (-1,-1),      'MIDDLE'),
            ('ALIGN',       (1,0), (-1,-1),      'LEFT'),
            ('LEFTPADDING', (0,0), (-1,-1),      4),
            ('RIGHTPADDING',(0,0), (-1,-1),      4),
        ]))
        elements.append(info_tbl)
        elements.append(Spacer(1, 6))

    # — Tabla de contenido según tipo —
    if tipo == 'venta':
        # Tabla de ventas con fila de totales integrada :contentReference[oaicite:1]{index=1}:contentReference[oaicite:2]{index=2}
        data = [[
            Paragraph('Cód.',      header_cell),
            Paragraph('Producto',  header_cell),
            Paragraph('Cant.',     header_cell),
            Paragraph('Subtotal',  header_cell),
            Paragraph('Comisión',  header_cell),
            Paragraph('Pagar Pan.',header_cell)
        ]]
        tot_cant = tot_sub = tot_com = tot_pan = 0
        col_ws = [
            doc.width*0.10, doc.width*0.35, doc.width*0.10,
            doc.width*0.15, doc.width*0.15, doc.width*0.15
        ]
        for it in modelo.items:
            if it.cantidad == 0:
                continue
            nombre = productos.get(it.producto_cod, it.producto_cod)
            cant = it.cantidad
            sub  = it.precio_unit * cant
            com  = it.comision
            pan  = it.pagar_pan
            data.append([
                Paragraph(it.producto_cod,          cell_style),
                Paragraph(nombre,                   cell_style),
                Paragraph(str(cant),                cell_style),
                Paragraph(f"${sub:,.0f}",           cell_style),
                Paragraph(f"${com:,.0f}",           cell_style),
                Paragraph(f"${pan:,.0f}",           cell_style)
            ])
            tot_cant += cant
            tot_sub  += sub
            tot_com  += com
            tot_pan  += pan

        # Fila de totales
        data.append([
            Paragraph('Totales',           header_cell),
            Paragraph('',                  cell_style),
            Paragraph(str(tot_cant),       cell_style),
            Paragraph(f"${tot_sub:,.0f}",  cell_style),
            Paragraph(f"${tot_com:,.0f}",  cell_style),
            Paragraph(f"${tot_pan:,.0f}",  cell_style)
        ])

        table = Table(data, colWidths=col_ws, hAlign='LEFT')
        table.setStyle(TableStyle([
            ('GRID',       (0,0), (-1,-1), 0.5, colors.black),
            ('BACKGROUND',(0,0), (-1,0),   colors.lightgrey),
            ('VALIGN',     (0,0), (-1,-1), 'MIDDLE'),
            ('ALIGN',      (2,1), (-1,-1), 'RIGHT'),
            ('LEFTPADDING',(0,0), (-1,-1), 4),
            ('RIGHTPADDING',(0,0),(-1,-1), 4),
        ]))
        elements.append(table)

    else:
        # Tabla de pedidos/extras/devoluciones con subtotales :contentReference[oaicite:3]{index=3}:contentReference[oaicite:4]{index=4}
        data = [[
            Paragraph('Producto',  header_cell),
            Paragraph('Cant.',      header_cell),
            Paragraph('Lote',header_cell),
            Paragraph('Subtotal',   header_cell)
        ]]
        tot_val = 0
        col_ws = [
            doc.width*0.55, doc.width*0.15,
            doc.width*0.15, doc.width*0.15
        ]
        for it in modelo.items:
            if it.cantidad <= 0:
                continue
            nombre = productos.get(it.producto_cod, it.producto_cod)
            cant = it.cantidad
            lote = ""
            vu   = it.precio_unit
            sub  = vu * cant
            data.append([
                Paragraph(f"{it.producto_cod} {nombre}", cell_style),
                Paragraph(str(cant),                     cell_style),
                Paragraph(f"{lote}",                     cell_style),
                Paragraph(f"${sub:,.0f}",                cell_style)
            ])
            tot_val += sub

        data.append([
            Paragraph('Totales',      header_cell),
            Paragraph('',             cell_style),
            Paragraph('',             cell_style),
            Paragraph(f"${tot_val:,.0f}", cell_style)
        ])

        table = Table(data, colWidths=col_ws, hAlign='LEFT')
        table.setStyle(TableStyle([
            ('GRID',       (0,0), (-1,-1), 0.5, colors.black),
            ('BACKGROUND',(0,0), (-1,0),    colors.lightgrey),
            ('VALIGN',     (0,0), (-1,-1),  'MIDDLE'),
            ('ALIGN',      (1,1), (-1,-1),  'RIGHT'),
            ('LEFTPADDING',(0,0), (-1,-1),   4),
            ('RIGHTPADDING',(0,0),(-1,-1),   4),
        ]))
        elements.append(table)

    # — Generar y devolver PDF —
    doc.build(elements)
    pdf = buffer.getvalue()
    buffer.close()
    return pdf

def generate_liquidacion_pdf(liquidacion, vendedor, venta, cambio):
    from reportlab.lib.pagesizes import inch
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet
    from io import BytesIO

    MEDIA_CARTA = (5.5 * inch, 8.5 * inch)  # Media carta vertical

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=MEDIA_CARTA,
                            leftMargin=15, rightMargin=15, topMargin=15, bottomMargin=15)

    elements = []
    styles = getSampleStyleSheet()

    # Cabecera
    data_header = [
        ["Liquidación:", liquidacion.codigo, "Fecha:", liquidacion.fecha.strftime('%d/%m/%Y')],
        ["Vendedor:", f"{vendedor.codigo_vendedor} - {vendedor.nombre}", "", ""],
        ["Venta:", f"VT-{venta.id:04d}", "", ""]
    ]
    table_header = Table(data_header, colWidths=[50, 130, 40, 100])
    table_header.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    elements.append(table_header)
    elements.append(Spacer(1, 8))

    # Resumen financiero
    a_panaderia = venta.total_venta - venta.comision
    descuento_cambios = cambio.valor_cambio if cambio else 0
    total_a_pagar = a_panaderia - descuento_cambios

    data_finance = [
        ["Concepto", "Valor"],
        ["Venta Total", f"${venta.total_venta:,.0f}"],
        ["Comisión", f"${venta.comision:,.0f}"],
        ["A Panadería", f"${a_panaderia:,.0f}"],
        ["Descuento Cambios", f"${descuento_cambios:,.0f}"],
        ["TOTAL A PAGAR", f"${total_a_pagar:,.0f}"],
    ]
    table_finance = Table(data_finance, colWidths=[120, 150])
    table_finance.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 0.4, colors.grey),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ALIGN', (1, 1), (-1, -1), 'RIGHT'),
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('BACKGROUND', (0, -1), (-1, -1), colors.lightgrey),
    ]))
    elements.append(table_finance)
    elements.append(Spacer(1, 10))

    # Detalle pagos
    data_pagos = [
        ["Pago Banco", f"${liquidacion.pago_banco:,.0f}"],
        ["Pago Efectivo", f"${liquidacion.pago_efectivo:,.0f}"],
        ["Pago Otros", f"${liquidacion.pago_otros:,.0f}"],
    ]
    table_pagos = Table(data_pagos, colWidths=[120, 150])
    table_pagos.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 0.4, colors.grey),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
    ]))
    elements.append(table_pagos)
    elements.append(Spacer(1, 8))

    # Comentarios (si hay)
    if liquidacion.comentarios:
        elements.append(Paragraph(f"<b>Comentarios:</b> {liquidacion.comentarios}", styles['Normal']))
        elements.append(Spacer(1, 8))

    # Firmas
    elements.append(Spacer(1, 20))
    elements.append(Paragraph("Firma Vendedor: ___________________________", styles['Normal']))
    elements.append(Spacer(1, 8))
    elements.append(Paragraph("Firma Recaudo: ____________________________", styles['Normal']))

    doc.build(elements)
    buffer.seek(0)
    return buffer

def generate_pdf_despacho(despacho, vendedor, tipo="pedido"):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=MEDIA_CARTA, rightMargin=25, leftMargin=25, topMargin=20, bottomMargin=20)
    elements = []
    styles = getSampleStyleSheet()

    # Título
    title_style = styles['Title']
    title_style.alignment = 1  # Centrado

    label_doc = {
        "pedido": "ORDEN DE PEDIDO",
        "extra": "ORDEN DE EXTRA"
    }

    title = Paragraph(label_doc.get(tipo, "ORDEN DE DESPACHO"), title_style)
    elements.append(title)
    elements.append(Spacer(1, 10))

    # Datos generales
    vendedor_nombre = vendedor.nombre if vendedor else despacho.vendedor_cod
    info_data = [
        [f"Código origen: {despacho.codigo_origen}", f"Fecha: {despacho.fecha.strftime('%Y-%m-%d')}"],
        [f"Vendedor: {vendedor_nombre}", f"Comentarios: {despacho.comentarios or '-'}"]
    ]
    info_table = Table(info_data, colWidths=[200, 200])
    info_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 10))

    # Tabla de productos
    data = [["Código", "Producto", "Pedido", "Desp.", "Lote", "Subtotal"]]
    total = 0

    for item in despacho.items:
        producto_obj = Producto.query.filter_by(codigo=item.producto_cod).first()
        nombre_prod = producto_obj.nombre if producto_obj else item.producto_cod
        subtotal = float(item.subtotal or 0)
        total += subtotal
        data.append([
            item.producto_cod,
            nombre_prod,
            str(item.cantidad_pedida),
            str(item.cantidad_despachada),
            item.lote or "-",
            f"${subtotal:,.0f}"
        ])

    table = Table(data, colWidths=[40, 145, 35, 35, 35, 65])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#eeeeee")),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
        ('ALIGN', (2, 1), (-1, -1), 'CENTER'),
        ('ALIGN', (1, 1), (1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 5),
        ('GRID', (0, 0), (-1, -1), 0.25, colors.grey),
    ]))
    elements.append(table)
    elements.append(Spacer(1, 10))

    # Total
    total_paragraph = Paragraph(
        f"<b>Total del despacho: ${total:,.0f}</b>",
        styles["Heading4"]
    )
    elements.append(total_paragraph)

    # Construir PDF
    doc.build(elements)
    pdf = buffer.getvalue()
    buffer.close()
    return pdf
