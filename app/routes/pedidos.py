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

pedidos_bp = Blueprint('pedidos', __name__, url_prefix='/pedidos')

@pedidos_bp.route('/crear', methods=['GET','POST'])
@login_required
@rol_requerido('vendedor','administrador')
def crear_pedido():
    # 1) Catálogo de productos
    productos = Producto.query.filter_by(activo=True).all()

    # 2) Sólo admin/semiadmin ven el select de vendedores
    vendedores = None
    if current_user.rol in ['administrador', 'semiadmin']:
        vendedores = Vendedor.query.order_by(Vendedor.nombre).all()

    # 3) Fecha inicial
    hoy_iso   = date.today().isoformat()
    fecha_val = hoy_iso

    # 4) Determinar el código de vendedor
    if current_user.rol in ['administrador', 'semiadmin']:
        # el admin/semiadmin lo elegirá del formulario
        selected_v = None
    else:
        # el vendedor toma su propio código desde la relación `user`
        user_obj = current_user._get_current_object()  # este es el Usuario
        vend_obj = user_obj.user                      # relación a Vendedor
        selected_v = vend_obj.codigo_vendedor

    comentarios = ''
    items_data  = [{'codigo':'','cantidad':1}]
    error_dup   = False

    if request.method == 'POST':
        # — Leer fecha —
        fecha_val = request.form.get('fecha') or hoy_iso
        try:
            fecha_obj = datetime.strptime(fecha_val, '%Y-%m-%d').date()
        except ValueError:
            fecha_obj = date.today()

        # — Si es admin o semiadmin, permitimos elegir vendedor —
        if current_user.rol in ['administrador', 'semiadmin']:
            selected_v = request.form.get('vendedor') or selected_v

        comentarios = request.form.get('comentarios','').strip()

        # — Items dinámicos —
        cods  = request.form.getlist('producto')
        cants = request.form.getlist('cantidad')
        items_data = [
            {'codigo': c, 'cantidad': int(q)}
            for c,q in zip(cods, cants) if c and q
        ]

        # — Validación: 1 pedido/día/vendedor —
        if BDPedido.query.filter_by(
            codigo_vendedor=selected_v,
            fecha=fecha_obj
        ).first():
            error_dup = True
            flash("Ya existe un pedido para ese día y vendedor.", "warning")
        else:
            # — Crear pedido y sus items —
            pedido = BDPedido(
                consecutivo     = generar_consecutivo(BDPedido, 'PD'),
                codigo_vendedor = selected_v,
                fecha           = fecha_obj,
                comentarios     = comentarios,
                usado           = False
            )
            for it in items_data:
                prod = Producto.query.filter_by(codigo=it['codigo']).first()
                pu   = prod.precio if prod else 0
                pedido.items.append(
                    BDPedidoItem(
                        producto_cod = it['codigo'],
                        cantidad     = it['cantidad'],
                        precio_unit  = pu,
                        subtotal     = pu * it['cantidad']
                    )
                )
            db.session.add(pedido)
            db.session.commit()
            flash("Pedido creado correctamente.", "success")
            return redirect(url_for('pedidos.listar_pedidos'))

    # 5) Renderizar formulario (GET o POST con errores)
    return render_template(
        'pedidos/crear.html',
        productos         = productos,
        vendedores        = vendedores,
        fecha_val         = fecha_val,
        selected_vendedor = selected_v,
        comentarios       = comentarios,
        items             = items_data,
        error_dup         = error_dup,
        hoy_iso           = hoy_iso
    )

@pedidos_bp.route('/listar', methods=['GET'])
@login_required
def listar_pedidos():
    filtro_fecha      = request.args.get('fecha','').strip()
    filtro_consecutivo= request.args.get('consecutivo','').strip()

    q = BDPedido.query
    if current_user.rol == 'vendedor':
        q = q.filter_by(codigo_vendedor=current_user.user.codigo_vendedor)
    if filtro_fecha:
        try:
            d = datetime.strptime(filtro_fecha,'%Y-%m-%d').date()
            q = q.filter(BDPedido.fecha==d)
        except ValueError:
            flash("Formato de fecha inválido.","warning")
    if filtro_consecutivo:
        q = q.filter(BDPedido.consecutivo.ilike(f"%{filtro_consecutivo}%"))

    pedidos = q.order_by(BDPedido.fecha.desc()).all()
    # calculo total de cada pedido
    for p in pedidos:
        p.total = sum(item.subtotal for item in p.items)

    vendedores_map = {
      v.codigo_vendedor: v.nombre
      for v in Vendedor.query.all()
    }

    return render_template(
      'pedidos/listar.html',
      pedidos=pedidos,
      vendedores=vendedores_map,
      filtro_fecha=filtro_fecha,
      filtro_consecutivo=filtro_consecutivo
    )

@pedidos_bp.route('/editar/<int:pid>', methods=['GET','POST'])
@login_required
@rol_requerido('administrador')
def editar_pedido(pid):
    pedido     = BDPedido.query.get_or_404(pid)
    productos  = Producto.query.filter_by(activo=True).all()
    vendedores = Vendedor.query.order_by(Vendedor.nombre).all()
    items_data = [{'codigo':it.producto_cod,'cantidad':it.cantidad}
                  for it in pedido.items]

    if request.method=='POST':
        # actualizo campos
        f = request.form.get('fecha')
        try:
            pedido.fecha = datetime.strptime(f,'%Y-%m-%d').date()
        except:
            pass
        pedido.codigo_vendedor = request.form.get('vendedor',pedido.codigo_vendedor)
        pedido.comentarios     = request.form.get('comentarios','').strip()

        # reconstruyo items
        pedido.items.clear()
        cods  = request.form.getlist('producto')
        cants = request.form.getlist('cantidad')
        for c,q in zip(cods,cants):
            if c and q:
                prod = Producto.query.filter_by(codigo=c).first()
                pu   = prod.precio if prod else 0
                pedido.items.append(
                  BDPedidoItem(
                    producto_cod = c,
                    cantidad     = int(q),
                    precio_unit  = pu,
                    subtotal     = pu*int(q)
                  )
                )
        db.session.commit()
        flash("Pedido actualizado.","success")
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
    p = BDPedido.query.get_or_404(pid)
    db.session.delete(p)
    db.session.commit()
    flash("Pedido eliminado.","success")
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
