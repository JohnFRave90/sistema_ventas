import datetime
from datetime import date, datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from flask import make_response, current_app
from app.utils.pdf_utils import generate_pdf_document
from app.utils.notificaciones import notificar_accion


from app import db
from app.models.devoluciones     import BDDevolucion
from app.models.devolucion_item  import BDDevolucionItem
from app.models.producto         import Producto
from app.models.vendedor         import Vendedor
from app.utils.roles             import rol_requerido
from app.utils.documentos        import generar_consecutivo

devoluciones_bp = Blueprint('devoluciones', __name__, url_prefix='/devoluciones')

@devoluciones_bp.route('/crear', methods=['GET', 'POST'])
@login_required
@rol_requerido('administrador', 'semiadmin', 'vendedor')
def crear_devolucion():
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
    items = [{'codigo': '', 'cantidad': 1}]
    error_max_two = False

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
        items = [
            {'codigo': c, 'cantidad': int(q)}
            for c, q in zip(cods, cants) if c and q
        ]

        cnt = BDDevolucion.query.filter_by(
            codigo_vendedor=selected_v,
            fecha=fecha_obj
        ).count()
        if cnt >= 2:
            error_max_two = True
            flash("Ya tiene dos devoluciones para esa fecha.", "warning")
        else:
            dev = BDDevolucion(
                consecutivo=generar_consecutivo(BDDevolucion, 'DV'),
                codigo_vendedor=selected_v,
                fecha=fecha_obj,
                comentarios=comentarios,
                usos=0
            )
            for it in items:
                prod = Producto.query.filter_by(codigo=it['codigo']).first()
                pu = prod.precio if prod else 0
                dev.items.append(
                    BDDevolucionItem(
                        producto_cod=it['codigo'],
                        cantidad=it['cantidad'],
                        precio_unit=pu,
                        subtotal=pu * it['cantidad']
                    )
                )
            db.session.add(dev)
            db.session.commit()

            vendedor = Vendedor.query.filter_by(codigo_vendedor=selected_v).first()
            notificar_accion("crear_devolucion", {
                "consecutivo": dev.consecutivo,
                "vendedor": vendedor.nombre if vendedor else selected_v,
                "fecha": dev.fecha.isoformat()
            })

            flash("Devolución creada correctamente.", "success")
            return redirect(url_for('devoluciones.listar_devoluciones'))

    return render_template(
        'devoluciones/crear.html',
        productos=productos,
        vendedores=vendedores,
        fecha_val=fecha_val,
        selected_vendedor=selected_v,
        comentarios=comentarios,
        items=items,
        error_max_two=error_max_two,
        hoy_iso=hoy_iso
    )

@devoluciones_bp.route('/editar/<int:did>', methods=['GET','POST'])
@login_required
@rol_requerido('administrador')
def editar_devolucion(did):
    from app.utils.productos import get_productos_ordenados
    from app.utils.notificaciones import notificar_accion

    dev = BDDevolucion.query.get_or_404(did)
    productos = get_productos_ordenados()
    vendedores = Vendedor.query.order_by(Vendedor.nombre).all()
    items = [
        {
            'codigo': it.producto_cod,
            'cantidad': it.cantidad,
            'subtotal': it.subtotal
        }
        for it in dev.items
    ]

    if request.method == 'POST':
        f = request.form.get('fecha')
        try:
            dev.fecha = datetime.strptime(f, '%Y-%m-%d').date()
        except:
            pass

        dev.codigo_vendedor = request.form.get('vendedor', dev.codigo_vendedor)
        dev.comentarios = request.form.get('comentarios', '').strip()

        dev.items.clear()
        cods = request.form.getlist('producto')
        cants = request.form.getlist('cantidad')

        for c, q in zip(cods, cants):
            if c and q:
                prod = Producto.query.filter_by(codigo=c).first()
                pu = prod.precio if prod else 0
                dev.items.append(
                    BDDevolucionItem(
                        producto_cod=c,
                        cantidad=int(q),
                        precio_unit=pu,
                        subtotal=pu * int(q)
                    )
                )

        db.session.commit()

        notificar_accion("editar_devolucion", {
            "consecutivo": dev.consecutivo
        })

        flash("Devolución actualizada.", "success")
        return redirect(url_for('devoluciones.listar_devoluciones'))

    return render_template(
        'devoluciones/editar.html',
        devolucion=dev,
        productos=productos,
        vendedores=vendedores,
        items=items
    )

@devoluciones_bp.route('/listar', methods=['GET'])
@login_required
def listar_devoluciones():
    filtro_fecha       = request.args.get('fecha', '').strip()
    filtro_consecutivo = request.args.get('consecutivo', '').strip()
    page               = request.args.get('page', 1, type=int)

    q = BDDevolucion.query
    if current_user.rol == 'vendedor':
        q = q.filter_by(codigo_vendedor=current_user.codigo_vendedor)

    if filtro_fecha:
        try:
            d = datetime.strptime(filtro_fecha, '%Y-%m-%d').date()
            q = q.filter(BDDevolucion.fecha == d)
        except ValueError:
            flash("Formato de fecha inválido.", "warning")

    if filtro_consecutivo:
        q = q.filter(BDDevolucion.consecutivo.ilike(f"%{filtro_consecutivo}%"))

    paginacion = q.order_by(BDDevolucion.fecha.desc()).paginate(page=page, per_page=30)

    for d in paginacion.items:
        d.total = sum(item.subtotal for item in d.items)

    vendedores_map = {
        v.codigo_vendedor: v.nombre
        for v in Vendedor.query.all()
    }

    return render_template(
        'devoluciones/listar.html',
        devoluciones=paginacion.items,
        pagination=paginacion,
        vendedores=vendedores_map,
        filtro_fecha=filtro_fecha,
        filtro_consecutivo=filtro_consecutivo
    )

@devoluciones_bp.route('/eliminar/<int:did>', methods=['POST'])
@login_required
@rol_requerido('administrador')
def eliminar_devolucion(did):
    from app.utils.notificaciones import notificar_accion

    dev = BDDevolucion.query.get_or_404(did)
    consecutivo = dev.consecutivo  # guardar antes de eliminar

    db.session.delete(dev)
    db.session.commit()

    notificar_accion("eliminar_devolucion", {
        "consecutivo": consecutivo
    })

    flash("Devolución eliminada.", "success")
    return redirect(url_for('devoluciones.listar_devoluciones'))

@devoluciones_bp.route('/export_pdf/<int:dev_id>', methods=['GET'])
@login_required
def export_pdf_devolucion(dev_id):
    devol = BDDevolucion.query.get_or_404(dev_id)
    vendedor = Vendedor.query.filter_by(codigo_vendedor=devol.codigo_vendedor).first()
    logo = current_app.root_path + '/static/logo_incolpan.png'
    pdf_bytes = generate_pdf_document(devol, vendedor, logo, tipo='devolucion')
    resp = make_response(pdf_bytes)
    resp.headers['Content-Type'] = 'application/pdf'
    resp.headers['Content-Disposition'] = (
        f'attachment; filename=Devolucion_{devol.consecutivo}.pdf'
    )
    return resp

