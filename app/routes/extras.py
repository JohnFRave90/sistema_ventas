# app/extras.py

import datetime
from datetime import date
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from datetime import date, datetime  # Corregido para usar datetime.strptime
from flask import make_response, current_app
from app.utils.pdf_utils import generate_pdf_document
from app.utils.notificaciones import notificar_accion


from app import db
from app.models.extras import BDExtra
from app.models.extra_item import BDExtraItem
from app.models.producto import Producto
from app.models.vendedor import Vendedor
from app.utils.roles import rol_requerido
from app.utils.documentos import generar_consecutivo

extras_bp = Blueprint('extras', __name__, url_prefix='/extras')

@extras_bp.route('/crear', methods=['GET', 'POST'])
@login_required
@rol_requerido('administrador', 'semiadmin', 'vendedor')
def crear_extra():
    from app.utils.productos import get_productos_ordenados
    from app.utils.notificaciones import notificar_accion

    productos = get_productos_ordenados()
    vendedores = None
    if current_user.rol in ['administrador', 'semiadmin']:
        vendedores = Vendedor.query.order_by(Vendedor.nombre).all()

    hoy_iso = date.today().isoformat()
    fecha_val = hoy_iso

    if current_user.rol in ['administrador', 'semiadmin']:
        selected_vendedor = None
    else:
        selected_vendedor = current_user.codigo_vendedor

    comentarios = ''
    items = [{'codigo': '', 'cantidad': 1}]
    error_max_one = False

    if request.method == 'POST':
        fecha_val = request.form.get('fecha') or hoy_iso
        try:
            fecha_obj = datetime.strptime(fecha_val, '%Y-%m-%d').date()
        except ValueError:
            fecha_obj = date.today()

        if current_user.rol in ['administrador', 'semiadmin']:
            selected_vendedor = request.form.get('vendedor') or selected_vendedor

        comentarios = request.form.get('comentarios', '').strip()

        codigos = request.form.getlist('producto')
        cantidades = request.form.getlist('cantidad')
        items = [
            {'codigo': c, 'cantidad': int(q)}
            for c, q in zip(codigos, cantidades) if c and q
        ]

        existente = BDExtra.query.filter_by(
            codigo_vendedor=selected_vendedor,
            fecha=fecha_obj
        ).first()
        if existente:
            error_max_one = True
            flash("Ya existe un extra para ese vendedor en la fecha indicada.", "warning")
        else:
            nuevo = BDExtra(
                consecutivo=generar_consecutivo(BDExtra, 'EX'),
                codigo_vendedor=selected_vendedor,
                fecha=fecha_obj,
                comentarios=comentarios,
                usado=False
            )
            db.session.add(nuevo)
            db.session.flush()

            for it in items:
                prod = Producto.query.filter_by(codigo=it['codigo']).first()
                pu = prod.precio if prod else 0
                db.session.add(BDExtraItem(
                    extra_id=nuevo.id,
                    producto_cod=it['codigo'],
                    cantidad=it['cantidad'],
                    precio_unit=pu,
                    subtotal=pu * it['cantidad']
                ))

            db.session.commit()

            vendedor = Vendedor.query.filter_by(codigo_vendedor=selected_vendedor).first()
            notificar_accion("crear_extra", {
                "consecutivo": nuevo.consecutivo,
                "vendedor": vendedor.nombre if vendedor else selected_vendedor,
                "fecha": nuevo.fecha.isoformat()
            })

            flash("Extra registrado correctamente.", "success")
            return redirect(url_for('extras.listar_extras'))

    return render_template(
        'extras/crear.html',
        productos=productos,
        vendedores=vendedores,
        fecha_val=fecha_val,
        selected_vendedor=selected_vendedor,
        comentarios=comentarios,
        items=items,
        error_max_one=error_max_one,
        hoy_iso=hoy_iso
    )

@extras_bp.route('/listar', methods=['GET'])
@login_required
def listar_extras():
    filtro_fecha       = request.args.get('fecha')
    filtro_consecutivo = request.args.get('consecutivo', '').strip()
    page               = request.args.get('page', 1, type=int)

    query = BDExtra.query
    if current_user.rol == 'vendedor':
        query = query.filter_by(codigo_vendedor=current_user.codigo_vendedor)

    if filtro_fecha:
        try:
            fecha_obj = datetime.strptime(filtro_fecha, '%Y-%m-%d').date()
            query = query.filter(BDExtra.fecha == fecha_obj)
        except ValueError:
            flash('Formato de fecha inválido.', 'warning')

    if filtro_consecutivo:
        query = query.filter(BDExtra.consecutivo.ilike(f"%{filtro_consecutivo}%"))

    paginacion = query.order_by(BDExtra.fecha.desc()).paginate(page=page, per_page=30)

    vendedores_map = {v.codigo_vendedor: v.nombre for v in Vendedor.query.all()}

    # Calcular total por cada extra mostrado en la página actual
    for ex in paginacion.items:
        ex.total = sum(i.subtotal for i in ex.items)

    return render_template(
        'extras/listar.html',
        extras=paginacion.items,
        pagination=paginacion,
        vendedores=vendedores_map,
        filtro_fecha=filtro_fecha,
        filtro_consecutivo=filtro_consecutivo
    )

@extras_bp.route('/editar/<int:eid>', methods=['GET', 'POST'])
@rol_requerido('administrador')
def editar_extra(eid):
    from app.utils.productos import get_productos_ordenados
    from app.utils.notificaciones import notificar_accion

    extra = BDExtra.query.get_or_404(eid)
    productos = get_productos_ordenados()
    vendedores = Vendedor.query.all()

    if request.method == 'POST':
        extra.codigo_vendedor = request.form['vendedor']
        extra.fecha = datetime.strptime(request.form['fecha'], '%Y-%m-%d').date()
        extra.comentarios = request.form['comentarios']

        BDExtraItem.query.filter_by(extra_id=extra.id).delete()

        codigos = request.form.getlist('producto')
        cantidades = request.form.getlist('cantidad')

        for codigo, cantidad_str in zip(codigos, cantidades):
            producto = Producto.query.filter_by(codigo=codigo).first()
            if producto and cantidad_str:
                cantidad = int(cantidad_str)
                precio_unit = producto.precio
                subtotal = cantidad * precio_unit

                item = BDExtraItem(
                    extra_id=extra.id,
                    producto_cod=codigo,
                    cantidad=cantidad,
                    precio_unit=precio_unit,
                    subtotal=subtotal
                )
                db.session.add(item)

        db.session.commit()

        notificar_accion("editar_extra", {
            "consecutivo": extra.consecutivo
        })

        flash('Extra actualizado correctamente.', 'success')
        return redirect(url_for('extras.listar_extras'))

    items = []
    for i in extra.items:
        producto = Producto.query.filter_by(codigo=i.producto_cod).first()
        if producto:
            items.append({
                'codigo': i.producto_cod,
                'nombre': producto.nombre,
                'cantidad': i.cantidad,
                'precio_unit': i.precio_unit,
                'subtotal': i.subtotal
            })

    return render_template(
        'extras/editar.html',
        extra=extra,
        productos=productos,
        vendedores=vendedores,
        items=items
    )

@extras_bp.route('/eliminar/<int:eid>', methods=['POST'])
@login_required
@rol_requerido('administrador')
def eliminar_extra(eid):
    from app.utils.notificaciones import notificar_accion

    extra = BDExtra.query.get_or_404(eid)
    consecutivo = extra.consecutivo  # Guardar antes de eliminar

    for i in extra.items:
        db.session.delete(i)
    db.session.delete(extra)
    db.session.commit()

    notificar_accion("eliminar_extra", {
        "consecutivo": consecutivo
    })

    flash('Extra eliminado correctamente.', 'success')
    return redirect(url_for('extras.listar_extras'))

@extras_bp.route('/export_pdf/<int:ext_id>', methods=['GET'])
@login_required
def export_pdf_extra(ext_id):
    extra = BDExtra.query.get_or_404(ext_id)
    vendedor = Vendedor.query.filter_by(codigo_vendedor=extra.codigo_vendedor).first()
    logo = current_app.root_path + '/static/logo_incolpan.png'
    pdf_bytes = generate_pdf_document(extra, vendedor, logo, tipo='extra')
    resp = make_response(pdf_bytes)
    resp.headers['Content-Type'] = 'application/pdf'
    resp.headers['Content-Disposition'] = (
        f'attachment; filename=Extra_{extra.consecutivo}.pdf'
    )
    return resp
