# app/routes/despachos.py
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from datetime import date
from app import db
from io import BytesIO
from app.models.despachos import BDDespacho, BDDespachoItem
from app.models.pedidos import BDPedido
from app.models.pedido_item import BDPedidoItem
from app.models.extras import BDExtra
from app.models.extra_item import BDExtraItem
from app.utils.roles import rol_requerido
from app.models.vendedor import Vendedor
from app.models.despachos import BDDespacho
from app.utils.pdf_utils import generate_pdf_despacho
from flask import send_file

despachos_bp = Blueprint('despachos', __name__)

@despachos_bp.route('/despachos/crear/<codigo_origen>', methods=['GET'])
@login_required
@rol_requerido('semiadmin', 'administrador')
def crear_despacho(codigo_origen):
    from app.models.producto import Producto
    from app.models.vendedor import Vendedor
    from app.utils.productos import get_productos_ordenados
    from markupsafe import Markup

    tipo_origen = 'pedido' if codigo_origen.startswith('PD-') else 'extra'
    origen = None
    items = []
    vendedor = None

    # Verificar si ya existe un despacho para este código
    despacho_existente = BDDespacho.query.filter_by(codigo_origen=codigo_origen).first()
    if despacho_existente:
        flash("Ya existe un despacho para este código. Redirigiendo a la edición.", "warning")
        return redirect(url_for("despachos.editar_despacho", did=despacho_existente.id))

    # Buscar origen (pedido o extra)
    if tipo_origen == 'pedido':
        origen = BDPedido.query.filter_by(consecutivo=codigo_origen).first()
        if origen:
            items_origen = BDPedidoItem.query.filter_by(pedido_id=origen.id).all()
    else:
        origen = BDExtra.query.filter_by(consecutivo=codigo_origen).first()
        if origen:
            items_origen = BDExtraItem.query.filter_by(extra_id=origen.id).all()

    if origen:
        vendedor = Vendedor.query.filter_by(codigo_vendedor=origen.codigo_vendedor).first()
        for it in items_origen:
            producto = Producto.query.filter_by(codigo=it.producto_cod).first()
            items.append({
                'producto_cod': it.producto_cod,
                'nombre_producto': producto.nombre if producto else it.producto_cod,
                'cantidad_pedida': it.cantidad,
                'precio_unitario': float(producto.precio) if producto else 0
            })

    productos = [
        {'codigo': p.codigo, 'nombre': p.nombre, 'precio': float(p.precio)}
        for p in get_productos_ordenados()
    ]

    return render_template(
        "despachos/crear.html",
        productos=productos,
        codigo_origen=codigo_origen,
        tipo_origen=tipo_origen,
        vendedor_cod=origen.codigo_vendedor if origen else None,
        nombre_vendedor=vendedor.nombre if vendedor else '',
        fecha=origen.fecha if origen else date.today(),
        comentarios=origen.comentarios if origen else "",
        items=items,
        origen_valido=bool(origen)
    )


@despachos_bp.route('/despachos/guardar', methods=['POST'])
@login_required
@rol_requerido('semiadmin', 'administrador')
def guardar_despacho():
    from decimal import Decimal
    from app.models.pedidos import BDPedido
    from app.models.extras import BDExtra

    codigo_origen = request.form.get('codigo_origen')
    tipo_origen = request.form.get('tipo_origen')  # 'pedido' o 'extra'
    vendedor_cod = request.form.get('vendedor_cod')
    fecha = request.form.get('fecha')
    comentarios = request.form.get('comentarios', '')

    despacho = BDDespacho(
        fecha=fecha,
        vendedor_cod=vendedor_cod,
        codigo_origen=codigo_origen,
        tipo_origen=tipo_origen,
        comentarios=comentarios,
        despachado=True
    )

    cods = request.form.getlist('producto_cod[]')
    peds = request.form.getlist('cantidad_pedida[]')
    desp = request.form.getlist('cantidad_despachada[]')
    lotes = request.form.getlist('lote[]')
    precios = request.form.getlist('precio_unitario[]')

    if tipo_origen == 'pedido':
        origen = BDPedido.query.filter_by(consecutivo=codigo_origen).first()
        origen_id = origen.id if origen else None
    else:
        origen = BDExtra.query.filter_by(consecutivo=codigo_origen).first()
        origen_id = origen.id if origen else None

    for i in range(len(cods)):
        producto_cod = cods[i]
        cantidad_pedida = int(peds[i]) if peds[i].isdigit() else 0
        cantidad = int(desp[i]) if desp[i].isdigit() else 0
        lote = lotes[i]
        precio_unit = Decimal(precios[i]) if precios[i] else Decimal("0.00")
        subtotal = cantidad * precio_unit

        item = BDDespachoItem(
            producto_cod=producto_cod,
            cantidad_pedida=cantidad_pedida,
            cantidad=cantidad,
            lote=lote,
            precio_unitario=precio_unit,
            subtotal=subtotal
        )

        if tipo_origen == 'pedido' and origen_id:
            item.pedido_id = origen_id
        elif tipo_origen == 'extra' and origen_id:
            item.extra_id = origen_id

        despacho.items.append(item)

    db.session.add(despacho)
    db.session.commit()

    flash("Despacho guardado correctamente", "success")
    return redirect(url_for("despachos.listar_despachos"))

@despachos_bp.route('/despachos/editar/<int:did>', methods=['GET', 'POST'])
@login_required
@rol_requerido('administrador')
def editar_despacho(did):
    from decimal import Decimal
    from app.models.pedidos import BDPedido
    from app.models.extras import BDExtra
    from app.utils.productos import get_productos_ordenados
    from app.models.vendedor import Vendedor

    despacho = BDDespacho.query.get_or_404(did)

    if request.method == 'POST':
        despacho.fecha = request.form.get('fecha')
        despacho.vendedor_cod = request.form.get('vendedor_cod')
        despacho.comentarios = request.form.get('comentarios', '')

        cods = request.form.getlist('producto_cod[]')
        peds = request.form.getlist('cantidad_pedida[]')
        desp = request.form.getlist('cantidad_despachada[]')
        lotes = request.form.getlist('lote[]')
        precios = request.form.getlist('precio_unitario[]')

        despacho.items.clear()

        for i in range(len(cods)):
            producto_cod = cods[i]
            cantidad_pedida = int(peds[i]) if peds[i].isdigit() else 0
            cantidad = int(desp[i]) if desp[i].isdigit() else 0
            lote = lotes[i]
            precio_unit = Decimal(precios[i]) if precios[i] else Decimal("0.00")
            subtotal = cantidad * precio_unit

            item = BDDespachoItem(
                producto_cod=producto_cod,
                cantidad_pedida=cantidad_pedida,
                cantidad=cantidad,
                lote=lote,
                precio_unitario=precio_unit,
                subtotal=subtotal
            )

            if despacho.tipo_origen == 'pedido':
                pedido = BDPedido.query.filter_by(consecutivo=despacho.codigo_origen).first()
                item.pedido_id = pedido.id if pedido else None
            elif despacho.tipo_origen == 'extra':
                extra = BDExtra.query.filter_by(consecutivo=despacho.codigo_origen).first()
                item.extra_id = extra.id if extra else None

            despacho.items.append(item)

        db.session.commit()
        flash("Despacho actualizado correctamente.", "success")
        return redirect(url_for("despachos.listar_despachos"))

    # Si es GET: Mostrar los valores para edición
    productos_base = get_productos_ordenados()
    productos = [
        {'codigo': p.codigo, 'nombre': p.nombre, 'precio': float(p.precio)}
        for p in productos_base
    ]

    vendedor = Vendedor.query.filter_by(codigo_vendedor=despacho.vendedor_cod).first()

    items = []
    for it in despacho.items:
        prod = next((p for p in productos if p["codigo"] == it.producto_cod), None)
        items.append({
            'producto_cod': it.producto_cod,
            'nombre_producto': prod['nombre'] if prod else it.producto_cod,
            'precio_unitario': float(it.precio_unitario),
            'cantidad_pedida': it.cantidad_pedida,
            'cantidad_despachada': it.cantidad,
            'lote': it.lote or ""
        })

    return render_template(
        'despachos/editar.html',
        productos=productos,
        codigo_origen=despacho.codigo_origen,
        tipo_origen=despacho.tipo_origen,
        vendedor_cod=despacho.vendedor_cod,
        nombre_vendedor=vendedor.nombre if vendedor else '',
        fecha=despacho.fecha,
        comentarios=despacho.comentarios,
        items=items,
        origen_valido=True,
        modo_edicion=True,
        despacho_id=did
    )


@despachos_bp.route('/despachos/listar', methods=['GET'])
@login_required
@rol_requerido('semiadmin', 'administrador')
def listar_despachos():
    from sqlalchemy import and_
    from app.models.vendedor import Vendedor

    page = request.args.get('page', 1, type=int)
    filtro_fecha = request.args.get('fecha')
    filtro_consecutivo = request.args.get('consecutivo')

    query = BDDespacho.query

    # Filtro por fecha
    if filtro_fecha:
        query = query.filter(BDDespacho.fecha == filtro_fecha)

    # Filtro por consecutivo (codigo_origen)
    if filtro_consecutivo:
        query = query.filter(BDDespacho.codigo_origen.contains(filtro_consecutivo))

    # Orden descendente por fecha
    query = query.order_by(BDDespacho.fecha.desc())

    pagination = query.paginate(page=page, per_page=20)
    despachos = pagination.items

    # Obtener nombres de vendedores
    codigos_vendedores = [d.vendedor_cod for d in despachos]
    vendedores = {
        v.codigo_vendedor: v.nombre
        for v in Vendedor.query.filter(Vendedor.codigo_vendedor.in_(codigos_vendedores)).all()
    }

    # Calcular total de cada despacho sumando subtotales
    totales = {
        d.id: sum(item.subtotal for item in d.items)
        for d in despachos
    }

    return render_template(
        'despachos/listar.html',
        despachos=despachos,
        vendedores=vendedores,
        totales=totales,
        filtro_fecha=filtro_fecha,
        filtro_consecutivo=filtro_consecutivo,
        pagination=pagination
    )

@despachos_bp.route('/despachos/nuevo', methods=['GET', 'POST'])
@login_required
@rol_requerido('semiadmin', 'administrador')
def ingresar_codigo():
    if request.method == 'POST':
        codigo = request.form.get('codigo_origen')
        if codigo and (codigo.startswith("PD-") or codigo.startswith("EX-")):
            return redirect(url_for('despachos.crear_despacho', codigo_origen=codigo))
        else:
            flash("Código inválido. Debe comenzar por PD- o EX-", "danger")
    
    return render_template('despachos/ingresar_codigo.html')

@despachos_bp.route('/despachos/eliminar/<int:did>', methods=['POST'])
@login_required
@rol_requerido('administrador')
def eliminar_despacho(did):
    despacho = BDDespacho.query.get_or_404(did)
    db.session.delete(despacho)
    db.session.commit()
    flash("Despacho eliminado correctamente.", "success")
    return redirect(url_for('despachos.listar_despachos'))

@despachos_bp.route('/despachos/pdf/<int:did>')
@login_required
@rol_requerido('semiadmin', 'administrador')
def export_pdf_despacho(did):
    despacho = BDDespacho.query.get_or_404(did)
    vendedor = Vendedor.query.filter_by(codigo_vendedor=despacho.vendedor_cod).first()

    pdf = generate_pdf_despacho(despacho, vendedor, tipo=despacho.tipo_origen)

    return send_file(
        BytesIO(pdf),
        as_attachment=True,
        download_name=f"{despacho.codigo_origen}_despacho.pdf",
        mimetype='application/pdf'
    )




