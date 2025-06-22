from datetime import date, datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from flask import make_response, current_app
from app.utils.pdf_utils import generate_pdf_document

from app import db
from app.models.pedidos     import BDPedido
from app.models.pedido_item import BDPedidoItem
from app.models.producto    import Producto
from app.models.vendedor    import Vendedor
from app.utils.roles        import rol_requerido
from app.utils.documentos   import generar_consecutivo
from app.utils.notificaciones import notificar_accion
from app.utils.productos import get_productos_ordenados

pedidos_bp = Blueprint('pedidos', __name__, url_prefix='/pedidos')

@pedidos_bp.route('/crear', methods=['GET', 'POST'])
@login_required
@rol_requerido('vendedor', 'administrador')
def crear_pedido():
    from app.utils.productos import get_productos_ordenados
    from app.utils.notificaciones import notificar_accion

    productos = get_productos_ordenados()

    vendedores = None
    if current_user.rol in ['administrador', 'semiadmin']:
        vendedores = Vendedor.query.order_by(Vendedor.nombre).all()

    hoy_iso = date.today().isoformat()
    fecha_val = hoy_iso

    if current_user.rol in ['administrador', 'semiadmin']:
        selected_v = None
    else:
        selected_v = current_user.codigo_vendedor

    comentarios = ''
    items_data = [{'codigo': '', 'cantidad': 1}]
    error_dup = False

    if request.method == 'POST':
        fecha_val = request.form.get('fecha') or hoy_iso
        try:
            fecha_obj = datetime.strptime(fecha_val, '%Y-%m-%d').date()
        except ValueError:
            fecha_obj = date.today()

        if current_user.rol in ['administrador', 'semiadmin']:
            selected_v = request.form.get('vendedor') or selected_v

        comentarios = request.form.get('comentarios', '').strip()

        cods = request.form.getlist('producto')
        cants = request.form.getlist('cantidad')
        items_data = [
            {'codigo': c, 'cantidad': int(q)}
            for c, q in zip(cods, cants) if c and q
        ]

        if BDPedido.query.filter_by(
            codigo_vendedor=selected_v,
            fecha=fecha_obj
        ).first():
            error_dup = True
            flash("Ya existe un pedido para ese día y vendedor.", "warning")
        else:
            pedido = BDPedido(
                consecutivo=generar_consecutivo(BDPedido, 'PD'),
                codigo_vendedor=selected_v,
                fecha=fecha_obj,
                comentarios=comentarios,
                usado=False
            )
            for it in items_data:
                prod = Producto.query.filter_by(codigo=it['codigo']).first()
                pu = prod.precio if prod else 0
                pedido.items.append(
                    BDPedidoItem(
                        producto_cod=it['codigo'],
                        cantidad=it['cantidad'],
                        precio_unit=pu,
                        subtotal=pu * it['cantidad']
                    )
                )
            db.session.add(pedido)
            db.session.commit()

            vendedor = Vendedor.query.filter_by(codigo_vendedor=selected_v).first()
            notificar_accion("crear_pedido", {
                "consecutivo": pedido.consecutivo,
                "vendedor": vendedor.nombre if vendedor else selected_v,
                "fecha": pedido.fecha.isoformat()
            })

            flash("Pedido creado correctamente.", "success")
            return redirect(url_for('pedidos.listar_pedidos'))

    return render_template(
        'pedidos/crear.html',
        productos=productos,
        vendedores=vendedores,
        fecha_val=fecha_val,
        selected_vendedor=selected_v,
        comentarios=comentarios,
        items=items_data,
        error_dup=error_dup,
        hoy_iso=hoy_iso
    )

@pedidos_bp.route('/listar', methods=['GET'])
@login_required
def listar_pedidos():
    filtro_fecha       = request.args.get('fecha', '').strip()
    filtro_consecutivo = request.args.get('consecutivo', '').strip()
    page               = request.args.get('page', 1, type=int)

    q = BDPedido.query
    if current_user.rol == 'vendedor':
        q = q.filter_by(codigo_vendedor=current_user.codigo_vendedor)

    if filtro_fecha:
        try:
            d = datetime.strptime(filtro_fecha, '%Y-%m-%d').date()
            q = q.filter(BDPedido.fecha == d)
        except ValueError:
            flash("Formato de fecha inválido.", "warning")

    if filtro_consecutivo:
        q = q.filter(BDPedido.consecutivo.ilike(f"%{filtro_consecutivo}%"))

    paginacion = q.order_by(BDPedido.fecha.desc()).paginate(page=page, per_page=30)

    # Calcular total de cada pedido en la página actual
    for p in paginacion.items:
        p.total = sum(item.subtotal for item in p.items)

    vendedores_map = {
        v.codigo_vendedor: v.nombre
        for v in Vendedor.query.all()
    }

    return render_template(
        'pedidos/listar.html',
        pedidos=paginacion.items,
        pagination=paginacion,
        vendedores=vendedores_map,
        filtro_fecha=filtro_fecha,
        filtro_consecutivo=filtro_consecutivo
    )

@pedidos_bp.route('/editar/<int:pid>', methods=['GET','POST'])
@login_required
@rol_requerido('administrador')
def editar_pedido(pid):
    from app.utils.productos import get_productos_ordenados
    from app.utils.notificaciones import notificar_accion

    pedido     = BDPedido.query.get_or_404(pid)
    productos  = get_productos_ordenados()
    vendedores = Vendedor.query.order_by(Vendedor.nombre).all()
    items_data = [{'codigo': it.producto_cod, 'cantidad': it.cantidad}
                  for it in pedido.items]

    if request.method == 'POST':
        f = request.form.get('fecha')
        try:
            pedido.fecha = datetime.strptime(f, '%Y-%m-%d').date()
        except:
            pass

        pedido.codigo_vendedor = request.form.get('vendedor', pedido.codigo_vendedor)
        pedido.comentarios     = request.form.get('comentarios', '').strip()

        pedido.items.clear()
        cods  = request.form.getlist('producto')
        cants = request.form.getlist('cantidad')

        for c, q in zip(cods, cants):
            if c and q:
                prod = Producto.query.filter_by(codigo=c).first()
                pu   = prod.precio if prod else 0
                pedido.items.append(
                    BDPedidoItem(
                        producto_cod = c,
                        cantidad     = int(q),
                        precio_unit  = pu,
                        subtotal     = pu * int(q)
                    )
                )

        db.session.commit()

        notificar_accion("editar_pedido", {
            "consecutivo": pedido.consecutivo
        })

        flash("Pedido actualizado.", "success")
        return redirect(url_for('pedidos.listar_pedidos'))

    return render_template(
        'pedidos/editar.html',
        pedido=pedido,
        productos=productos,
        vendedores=vendedores,
        items=items_data
    )

@pedidos_bp.route('/eliminar/<int:pid>', methods=['POST'])
@login_required
@rol_requerido('administrador')
def eliminar_pedido(pid):
    from app.utils.notificaciones import notificar_accion

    p = BDPedido.query.get_or_404(pid)
    consecutivo = p.consecutivo  # Guardar antes de eliminar

    db.session.delete(p)
    db.session.commit()

    notificar_accion("eliminar_pedido", {
        "consecutivo": consecutivo
    })

    flash("Pedido eliminado.", "success")
    return redirect(url_for('pedidos.listar_pedidos'))

@pedidos_bp.route('/export_pdf/<int:pid>', methods=['GET'])
@login_required
def export_pdf_pedido(pid):
    pedido = BDPedido.query.get_or_404(pid)
    vendedor_obj = Vendedor.query.filter_by(codigo_vendedor=pedido.codigo_vendedor).first()
    logo = current_app.root_path + '/static/logo_incolpan.png'
    pdf_bytes = generate_pdf_document(pedido, vendedor_obj, logo, tipo='pedido')
    resp = make_response(pdf_bytes)
    resp.headers['Content-Type'] = 'application/pdf'
    resp.headers['Content-Disposition'] = f'attachment; filename=Pedido_{pedido.consecutivo}.pdf'
    return resp
