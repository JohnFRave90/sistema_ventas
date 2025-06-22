# app/routes/ventas.py
from datetime import date, datetime
import json
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from flask import make_response, current_app
from app.utils.pdf_utils import generate_pdf_document

from app import db
from app.models.pedidos      import BDPedido
from app.models.extras       import BDExtra
from app.models.devoluciones import BDDevolucion
from app.models.ventas       import BDVenta
from app.models.venta_item   import BDVentaItem
from app.models.producto     import Producto
from app.models.vendedor     import Vendedor
from app.utils.roles         import rol_requerido
from app.utils.documentos    import generar_consecutivo
from app.utils.notificaciones import notificar_accion
from app.models.despachos    import BDDespacho, BDDespachoItem

ventas_bp = Blueprint('ventas', __name__, url_prefix='/ventas')

@ventas_bp.route('/generar', methods=['GET', 'POST'])
@login_required
@rol_requerido('semiadmin', 'administrador')
def generar_venta():
    from app.utils.notificaciones import notificar_accion

    hoy_iso = date.today().isoformat()
    fecha_val = request.values.get('fecha', hoy_iso)

    try:
        fecha_obj = datetime.strptime(fecha_val, '%Y-%m-%d').date()
    except:
        fecha_obj, fecha_val = date.today(), hoy_iso

    if current_user.rol in ['administrador', 'semiadmin']:
        vendedores_list = Vendedor.query.order_by(Vendedor.nombre).all()
        selected_v = request.values.get('vendedor') or (
            vendedores_list[0].codigo_vendedor if vendedores_list else None
        )
    else:
        vendedores_list = None
        selected_v = current_user.user.codigo_vendedor

    # Obtener pedidos y extras desde despachos
    pedidos = BDDespacho.query.filter_by(
        vendedor_cod=selected_v, fecha=fecha_obj, tipo_origen='pedido'
    ).all()

    extras = BDDespacho.query.filter_by(
        vendedor_cod=selected_v, fecha=fecha_obj, tipo_origen='extra'
    ).all()

    devols = BDDevolucion.query.filter(
        BDDevolucion.codigo_vendedor == selected_v,
        BDDevolucion.usos < 2
    ).all()

    c_dev_ant = request.values.get('codigo_dev_anterior', '').strip()
    c_ped     = request.values.get('codigo_pedido',        '').strip()
    c_ext     = request.values.get('codigo_extra',         '').strip()
    c_dev_d   = request.values.get('codigo_dev_dia',       '').strip()

    def fetch(modelo, code, by_date=True):
        if not code:
            return None
        q = modelo.query.filter_by(consecutivo=code, codigo_vendedor=selected_v)
        if by_date:
            q = q.filter_by(fecha=fecha_obj)
        return q.first()

    d_ant = fetch(BDDevolucion, c_dev_ant, False)
    d_dia = fetch(BDDevolucion, c_dev_d,   False)

    ped = BDDespacho.query.filter_by(codigo_origen=c_ped, vendedor_cod=selected_v).first()
    ext = BDDespacho.query.filter_by(codigo_origen=c_ext, vendedor_cod=selected_v).first()

    prods = Producto.query.with_entities(
        Producto.codigo, Producto.precio,
        Producto.nombre, Producto.categoria
    ).all()

    price = {p.codigo: p.precio for p in prods}
    names = {p.codigo: p.nombre for p in prods}
    cats  = {p.codigo: p.categoria for p in prods}
    vend  = Vendedor.query.filter_by(codigo_vendedor=selected_v).first()

    breakdown = []
    temp = {}

    for doc, key in [
        (d_ant, 'dev_ant'),
        (ped,   'pedido'),
        (ext,   'extra'),
        (d_dia, 'dev_dia')
    ]:
        if doc:
            for item in doc.items:
                code = item.producto_cod
                qty = item.cantidad  
                temp.setdefault(code, {
                    'dev_ant': 0, 'pedido': 0,
                    'extra':   0, 'dev_dia': 0
                })
                temp[code][key] += qty

    for code, vals in temp.items():
        qty = vals['dev_ant'] + vals['pedido'] + vals['extra'] - vals['dev_dia']
        val = price.get(code, 0) * qty

        categoria = cats.get(code, '')
        if categoria == 'panaderia':
            pct = (vend.comision_panaderia or 0) / 100
        elif categoria == 'bizcocheria':
            pct = (vend.comision_bizcocheria or 0) / 100
        else:
            pct = 0.0

        com = val * pct
        pan = val - com

        breakdown.append({
            'codigo': code,
            'nombre': names.get(code, code),
            'dev_ant': vals['dev_ant'],
            'pedido': vals['pedido'],
            'extra': vals['extra'],
            'dev_dia': vals['dev_dia'],
            'total': qty,
            'valor': val,
            'comision': com,
            'pagar_pan': pan
        })

    tot_val = sum(i['valor'] for i in breakdown)
    tot_com = sum(i['comision'] for i in breakdown)
    tot_pan = sum(i['pagar_pan'] for i in breakdown)

    if request.method == 'POST' and 'confirm' in request.form:
        if BDVenta.query.filter_by(
            codigo_vendedor=selected_v, fecha=fecha_obj
        ).first():
            flash('Ya existe venta para este día y vendedor.', 'warning')
            return redirect(url_for('ventas.generar_venta'))

        venta = BDVenta(
            consecutivo         = generar_consecutivo(BDVenta, 'VT'),
            codigo_vendedor     = selected_v,
            codigo_dev_anterior = c_dev_ant or None,
            codigo_pedido       = c_ped     or None,
            codigo_extra        = c_ext     or None,
            codigo_dev_dia      = c_dev_d   or None,
            fecha               = fecha_obj,
            devolucion_anterior = sum(i['dev_ant'] for i in breakdown),
            pedido              = sum(i['pedido']  for i in breakdown),
            extras              = sum(i['extra']   for i in breakdown),
            devolucion_dia      = sum(i['dev_dia'] for i in breakdown),
            total_venta         = tot_val,
            comision            = tot_com,
            pagar_pan           = tot_pan
        )

        for line in breakdown:
            pu = price.get(line['codigo'], 0)
            venta.items.append(
                BDVentaItem(
                    producto_cod = line['codigo'],
                    cantidad     = line['total'],
                    precio_unit  = pu,
                    subtotal     = line['valor'],
                    comision     = line['comision'],
                    pagar_pan    = line['pagar_pan']
                )
            )

        db.session.add(venta)
        if ped:   ped.usado = True
        if ext:   ext.usado = True
        if d_ant: d_ant.usos += 1
        if d_dia: d_dia.usos += 1
        db.session.commit()

        notificar_accion("crear_venta", {
            "vendedor": vend.nombre,
            "fecha": venta.fecha.isoformat(),
            "total": venta.total_venta
        })

        flash('Venta registrada', 'success')
        return redirect(url_for('ventas.listar_ventas'))

    return render_template(
        'ventas/generar.html',
        fecha_val         = fecha_val,
        vendedores        = vendedores_list,
        selected_vendedor = selected_v,
        pedidos_list      = pedidos,
        extras_list       = extras,
        devols_list       = devols,
        code_dev_ant      = c_dev_ant,
        code_pedido       = c_ped,
        code_extra        = c_ext,
        code_dev_dia      = c_dev_d,
        breakdown         = breakdown,
        total_valor       = tot_val,
        total_comision    = tot_com,
        total_pagar       = tot_pan
    )

@ventas_bp.route('/listar', methods=['GET'])
@login_required
def listar_ventas():
    filtro_fecha  = request.args.get('fecha', '').strip()
    filtro_cons   = request.args.get('consecutivo', '').strip()
    page          = request.args.get('page', 1, type=int)

    q = BDVenta.query

    if current_user.rol == 'vendedor':
        q = q.filter_by(codigo_vendedor=current_user.codigo_vendedor)

    if filtro_fecha:
        try:
            d = datetime.strptime(filtro_fecha, '%Y-%m-%d').date()
            q = q.filter(BDVenta.fecha == d)
        except:
            flash('Fecha inválida', 'warning')

    if filtro_cons:
        q = q.filter(BDVenta.consecutivo.ilike(f"%{filtro_cons}%"))

    paginacion = q.order_by(BDVenta.fecha.desc()).paginate(page=page, per_page=30)

    vend_map = {
        v.codigo_vendedor: v.nombre
        for v in Vendedor.query.all()
    }

    return render_template(
        'ventas/listar.html',
        ventas=paginacion.items,
        pagination=paginacion,
        vendedores=vend_map,
        filtro_fecha=filtro_fecha,
        filtro_consecutivo=filtro_cons
    )

@ventas_bp.route('/eliminar/<int:vid>', methods=['POST'])
@login_required
@rol_requerido('administrador')
def eliminar_venta(vid):
    from app.utils.notificaciones import notificar_accion

    v = BDVenta.query.get_or_404(vid)
    consecutivo = v.consecutivo
    fecha = v.fecha.isoformat()
    vendedor = Vendedor.query.filter_by(codigo_vendedor=v.codigo_vendedor).first()
    nombre_vendedor = vendedor.nombre if vendedor else v.codigo_vendedor

    # Revertir flags
    if v.codigo_pedido:
        p = BDPedido.query.filter_by(consecutivo=v.codigo_pedido).first()
        if p: p.usado = False
    if v.codigo_extra:
        e = BDExtra.query.filter_by(consecutivo=v.codigo_extra).first()
        if e: e.usado = False
    if v.codigo_dev_anterior:
        da = BDDevolucion.query.filter_by(consecutivo=v.codigo_dev_anterior).first()
        if da and da.usos > 0: da.usos -= 1
    if v.codigo_dev_dia:
        dd = BDDevolucion.query.filter_by(consecutivo=v.codigo_dev_dia).first()
        if dd and dd.usos > 0: dd.usos -= 1

    db.session.delete(v)
    db.session.commit()

    notificar_accion("eliminar_venta", {
        "consecutivo": consecutivo,
        "fecha": fecha,
        "vendedor": nombre_vendedor
    })

    flash("Venta eliminada.", "success")
    return redirect(url_for('ventas.listar_ventas'))

@ventas_bp.route('/export_pdf/<int:venta_id>', methods=['GET'])
@login_required
def export_pdf_venta(venta_id):
    venta = BDVenta.query.get_or_404(venta_id)
    vendedor = Vendedor.query.filter_by(codigo_vendedor=venta.codigo_vendedor).first()
    logo = current_app.root_path + '/static/logo_incolpan.png'
    pdf_bytes = generate_pdf_document(venta, vendedor, logo, tipo='venta')
    resp = make_response(pdf_bytes)
    resp.headers['Content-Type'] = 'application/pdf'
    resp.headers['Content-Disposition'] = (
        f'attachment; filename=Venta_{venta.consecutivo}.pdf'
    )
    return resp
