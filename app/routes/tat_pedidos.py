from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from datetime import date
from app import db
from app.models.venta_autoventa import BDVentaAutoventa, BDVentaAutoventaItem
from app.models.cliente import Cliente
from app.models.vendedor import Vendedor
from app.models.producto import Producto
from app.utils.roles import rol_requerido

tat_pedidos_bp = Blueprint('tat_pedidos', __name__, url_prefix='/tat/pedidos')


@tat_pedidos_bp.route('/')
@login_required
@rol_requerido('administrador')
def listar_tat_pedidos():
    vendedor_filtro = request.args.get('vendedor', '')
    fecha_str = request.args.get('fecha', str(date.today()))
    page = request.args.get('page', 1, type=int)

    try:
        fecha = date.fromisoformat(fecha_str)
    except ValueError:
        fecha = date.today()
        fecha_str = str(fecha)

    query = BDVentaAutoventa.query.filter_by(fecha=fecha)
    if vendedor_filtro:
        query = query.filter_by(codigo_vendedor=vendedor_filtro)

    autoventas = query.order_by(BDVentaAutoventa.id.desc()).paginate(
        page=page, per_page=25, error_out=False
    )
    vendedores = Vendedor.query.order_by(Vendedor.nombre).all()

    return render_template(
        'tat_pedidos/listar.html',
        autoventas=autoventas,
        vendedores=vendedores,
        vendedor_filtro=vendedor_filtro,
        fecha_filtro=fecha_str,
    )


@tat_pedidos_bp.route('/<int:id>')
@login_required
@rol_requerido('administrador')
def detalle_tat_pedido(id):
    autoventa = BDVentaAutoventa.query.get_or_404(id)
    return render_template('tat_pedidos/detalle.html', autoventa=autoventa)


@tat_pedidos_bp.route('/crear', methods=['GET', 'POST'])
@login_required
@rol_requerido('administrador')
def crear_tat_pedido():
    vendedor_sel = request.args.get('vendedor', '') or request.form.get('codigo_vendedor', '')
    vendedores = Vendedor.query.order_by(Vendedor.nombre).all()
    productos = Producto.query.filter_by(activo=True).order_by(Producto.orden, Producto.nombre).all()
    clientes = []
    if vendedor_sel:
        clientes = Cliente.query.filter_by(
            codigo_vendedor=vendedor_sel, activo=True
        ).order_by(Cliente.ruta, Cliente.orden_visita).all()

    if request.method == 'POST':
        codigo_vendedor = (request.form.get('codigo_vendedor') or '').strip()
        cliente_id = request.form.get('cliente_id', type=int)
        fecha_str = request.form.get('fecha', str(date.today()))
        try:
            fecha = date.fromisoformat(fecha_str)
        except ValueError:
            fecha = date.today()

        codigos = request.form.getlist('producto_cod')
        cantidades = request.form.getlist('cantidad')

        if not codigo_vendedor or not cliente_id:
            flash('Vendedor y cliente son requeridos.', 'danger')
            return render_template('tat_pedidos/crear.html',
                                   vendedores=vendedores, productos=productos,
                                   clientes=clientes, vendedor_sel=vendedor_sel,
                                   fecha_hoy=str(date.today()))

        items = []
        total = 0
        for cod, cant_str in zip(codigos, cantidades):
            try:
                cant = int(cant_str)
            except (ValueError, TypeError):
                continue
            if cant <= 0:
                continue
            prod = Producto.query.filter_by(codigo=cod).first()
            if not prod:
                continue
            subtotal = prod.precio * cant
            total += subtotal
            items.append((prod, cant, subtotal))

        if not items:
            flash('Agrega al menos un producto con cantidad válida.', 'danger')
            return render_template('tat_pedidos/crear.html',
                                   vendedores=vendedores, productos=productos,
                                   clientes=clientes, vendedor_sel=vendedor_sel,
                                   fecha_hoy=str(date.today()))

        venta = BDVentaAutoventa(
            consecutivo=BDVentaAutoventa.siguiente_consecutivo(),
            codigo_vendedor=codigo_vendedor,
            cliente_id=cliente_id,
            fecha=fecha,
            total=total,
            enviada_por_sync=False,
        )
        db.session.add(venta)
        db.session.flush()

        for prod, cant, subtotal in items:
            db.session.add(BDVentaAutoventaItem(
                autoventa_id=venta.id,
                producto_cod=prod.codigo,
                cantidad=cant,
                precio_unit=prod.precio,
                subtotal=subtotal,
            ))

        db.session.commit()
        flash(f'Autoventa {venta.consecutivo} creada exitosamente.', 'success')
        return redirect(url_for('tat_pedidos.detalle_tat_pedido', id=venta.id))

    return render_template('tat_pedidos/crear.html',
                           vendedores=vendedores, productos=productos,
                           clientes=clientes, vendedor_sel=vendedor_sel,
                           fecha_hoy=str(date.today()))
