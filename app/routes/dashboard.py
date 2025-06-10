from flask import Blueprint, render_template, flash, session, redirect, url_for
from flask_login import login_required, current_user
from app import db
from app.models.pedidos import BDPedido
from app.models.pedido_item import BDPedidoItem
from app.models.vendedor import Vendedor
from app.models.canastas import Canasta, MovimientoCanasta
from app.models.ventas import BDVenta
from app.models.extra_item import BDExtraItem
from app.models.extras import BDExtra
from app.utils.roles import rol_requerido
from datetime import datetime, timedelta
from sqlalchemy import func
from sqlalchemy import not_, exists


dashboard_bp = Blueprint("dashboard", __name__, template_folder="../templates")

@dashboard_bp.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html")

@dashboard_bp.route("/dashboard_admin", methods=['GET'])
@login_required
@rol_requerido('administrador')
def dashboard_admin():
    hoy = datetime.now().date()
    inicio_mes = hoy.replace(day=1)

    # Total acumulado del mes (de BDVenta)
    total_mes = (db.session.query(func.sum(BDVenta.total_venta))
                 .filter(BDVenta.fecha >= inicio_mes)
                 .scalar() or 0)

    # Total del día: pedidos y extras
    total_dia_pedidos = (db.session.query(func.sum(BDPedidoItem.subtotal))
                         .join(BDPedido, BDPedido.id == BDPedidoItem.pedido_id)
                         .filter(BDPedido.fecha == hoy)
                         .scalar() or 0)

    total_dia_extras = (db.session.query(func.sum(BDExtraItem.subtotal))
                        .join(BDExtra, BDExtra.id == BDExtraItem.extra_id)
                        .filter(BDExtra.fecha == hoy)
                        .scalar() or 0)

    total_dia = total_dia_pedidos + total_dia_extras

    # Pedidos del día por vendedor
    pedidos_dia_pedidos = (db.session.query(
                                Vendedor.nombre,
                                func.sum(BDPedidoItem.subtotal).label('valor_total'))
                            .join(BDPedido, BDPedido.id == BDPedidoItem.pedido_id)
                            .join(Vendedor, BDPedido.codigo_vendedor == Vendedor.codigo_vendedor)
                            .filter(BDPedido.fecha == hoy)
                            .group_by(Vendedor.nombre))

    pedidos_dia_extras = (db.session.query(
                                Vendedor.nombre,
                                func.sum(BDExtraItem.subtotal).label('valor_total'))
                            .join(BDExtra, BDExtra.id == BDExtraItem.extra_id)
                            .join(Vendedor, BDExtra.codigo_vendedor == Vendedor.codigo_vendedor)
                            .filter(BDExtra.fecha == hoy)
                            .group_by(Vendedor.nombre))

    pedidos_dia_vendedores = {}
    for nombre, valor in pedidos_dia_pedidos.all():
        pedidos_dia_vendedores[nombre] = valor
    for nombre, valor in pedidos_dia_extras.all():
        pedidos_dia_vendedores[nombre] = pedidos_dia_vendedores.get(nombre, 0) + valor

    pedidos_dia_vendedores = list(pedidos_dia_vendedores.items())

    # Pedidos del mes por vendedor
    pedidos_mes_pedidos = (db.session.query(
                                Vendedor.nombre,
                                func.sum(BDPedidoItem.subtotal).label('valor_total'))
                            .join(BDPedido, BDPedido.id == BDPedidoItem.pedido_id)
                            .join(Vendedor, BDPedido.codigo_vendedor == Vendedor.codigo_vendedor)
                            .filter(BDPedido.fecha >= inicio_mes)
                            .group_by(Vendedor.nombre))

    pedidos_mes_extras = (db.session.query(
                                Vendedor.nombre,
                                func.sum(BDExtraItem.subtotal).label('valor_total'))
                            .join(BDExtra, BDExtra.id == BDExtraItem.extra_id)
                            .join(Vendedor, BDExtra.codigo_vendedor == Vendedor.codigo_vendedor)
                            .filter(BDExtra.fecha >= inicio_mes)
                            .group_by(Vendedor.nombre))

    pedidos_mes_vendedores = {}
    for nombre, valor in pedidos_mes_pedidos.all():
        pedidos_mes_vendedores[nombre] = valor
    for nombre, valor in pedidos_mes_extras.all():
        pedidos_mes_vendedores[nombre] = pedidos_mes_vendedores.get(nombre, 0) + valor

    pedidos_mes_vendedores = list(pedidos_mes_vendedores.items())

    # Canastas Perdidas (prestadas hace 7 días o más)
    limite_fecha = datetime.now() - timedelta(days=7)

    subq = (db.session.query(
                MovimientoCanasta.codigo_barras,
                func.max(MovimientoCanasta.fecha_movimiento).label('fecha')
            )
            .filter(MovimientoCanasta.tipo_movimiento == 'Sale')
            .group_by(MovimientoCanasta.codigo_barras)
            .subquery())

    canastas_data = (db.session.query(
                        Canasta.codigo_barras,
                        subq.c.fecha.label('fecha_prestamo'),
                        Vendedor.nombre.label('nombre_vendedor')
                    )
                    .join(subq, Canasta.codigo_barras == subq.c.codigo_barras)
                    .join(MovimientoCanasta, (MovimientoCanasta.codigo_barras == Canasta.codigo_barras) &
                                              (MovimientoCanasta.fecha_movimiento == subq.c.fecha))
                    .join(Vendedor, MovimientoCanasta.codigo_vendedor == Vendedor.codigo_vendedor)
                    .filter(Canasta.actualidad == 'Prestada')
                    .filter(subq.c.fecha <= limite_fecha)
                    .all())

    canastas_perdidas_count = len(canastas_data)

    canastas_perdidas_list = [{
        'codigo_barras': c.codigo_barras,
        'fecha_prestamo': c.fecha_prestamo,
        'nombre_vendedor': c.nombre_vendedor,
        'dias_prestada': (datetime.now().date() - c.fecha_prestamo.date()).days
    } for c in canastas_data]
    
    # Total del mes: pedidos + extras
    total_mes_pedidos = (db.session.query(func.sum(BDPedidoItem.subtotal))
                        .join(BDPedido, BDPedido.id == BDPedidoItem.pedido_id)
                        .filter(BDPedido.fecha >= inicio_mes)
                        .scalar() or 0)

    total_mes_extras = (db.session.query(func.sum(BDExtraItem.subtotal))
                        .join(BDExtra, BDExtra.id == BDExtraItem.extra_id)
                        .filter(BDExtra.fecha >= inicio_mes)
                        .scalar() or 0)

    total_mes_pedidos_extras = total_mes_pedidos + total_mes_extras
    
    return render_template("dashboard/admin_dashboard.html",
                           total_mes=total_mes,
                           total_dia=total_dia,
                           pedidos_dia_vendedores=pedidos_dia_vendedores,
                           pedidos_mes_vendedores=pedidos_mes_vendedores,
                           canastas_perdidas_count=canastas_perdidas_count,
                           canastas_perdidas_list=canastas_perdidas_list,
                           total_mes_pedidos_extras=total_mes_pedidos_extras)
 
@dashboard_bp.route("/dashboard_semiadmin", methods=['GET'])
@login_required
@rol_requerido('semiadmin')
def dashboard_semiadmin():
    hoy = datetime.now().date()
    inicio_mes = hoy.replace(day=1)

    # Total acumulado del mes (de BDVenta)
    total_mes = (db.session.query(func.sum(BDVenta.total_venta))
                 .filter(BDVenta.fecha >= inicio_mes)
                 .scalar() or 0)

    # Total del día: pedidos y extras
    total_dia_pedidos = (db.session.query(func.sum(BDPedidoItem.subtotal))
                         .join(BDPedido, BDPedido.id == BDPedidoItem.pedido_id)
                         .filter(BDPedido.fecha == hoy)
                         .scalar() or 0)

    total_dia_extras = (db.session.query(func.sum(BDExtraItem.subtotal))
                        .join(BDExtra, BDExtra.id == BDExtraItem.extra_id)
                        .filter(BDExtra.fecha == hoy)
                        .scalar() or 0)

    total_dia = total_dia_pedidos + total_dia_extras

    # Pedidos del día por vendedor
    pedidos_dia_pedidos = (db.session.query(
                                Vendedor.nombre,
                                func.sum(BDPedidoItem.subtotal).label('valor_total'))
                            .join(BDPedido, BDPedido.id == BDPedidoItem.pedido_id)
                            .join(Vendedor, BDPedido.codigo_vendedor == Vendedor.codigo_vendedor)
                            .filter(BDPedido.fecha == hoy)
                            .group_by(Vendedor.nombre))

    pedidos_dia_extras = (db.session.query(
                                Vendedor.nombre,
                                func.sum(BDExtraItem.subtotal).label('valor_total'))
                            .join(BDExtra, BDExtra.id == BDExtraItem.extra_id)
                            .join(Vendedor, BDExtra.codigo_vendedor == Vendedor.codigo_vendedor)
                            .filter(BDExtra.fecha == hoy)
                            .group_by(Vendedor.nombre))

    pedidos_dia_vendedores = {}
    for nombre, valor in pedidos_dia_pedidos.all():
        pedidos_dia_vendedores[nombre] = valor
    for nombre, valor in pedidos_dia_extras.all():
        pedidos_dia_vendedores[nombre] = pedidos_dia_vendedores.get(nombre, 0) + valor

    pedidos_dia_vendedores = list(pedidos_dia_vendedores.items())

    # Pedidos del mes por vendedor
    pedidos_mes_pedidos = (db.session.query(
                                Vendedor.nombre,
                                func.sum(BDPedidoItem.subtotal).label('valor_total'))
                            .join(BDPedido, BDPedido.id == BDPedidoItem.pedido_id)
                            .join(Vendedor, BDPedido.codigo_vendedor == Vendedor.codigo_vendedor)
                            .filter(BDPedido.fecha >= inicio_mes)
                            .group_by(Vendedor.nombre))

    pedidos_mes_extras = (db.session.query(
                                Vendedor.nombre,
                                func.sum(BDExtraItem.subtotal).label('valor_total'))
                            .join(BDExtra, BDExtra.id == BDExtraItem.extra_id)
                            .join(Vendedor, BDExtra.codigo_vendedor == Vendedor.codigo_vendedor)
                            .filter(BDExtra.fecha >= inicio_mes)
                            .group_by(Vendedor.nombre))

    pedidos_mes_vendedores = {}
    for nombre, valor in pedidos_mes_pedidos.all():
        pedidos_mes_vendedores[nombre] = valor
    for nombre, valor in pedidos_mes_extras.all():
        pedidos_mes_vendedores[nombre] = pedidos_mes_vendedores.get(nombre, 0) + valor

    pedidos_mes_vendedores = list(pedidos_mes_vendedores.items())

    # Canastas Perdidas (prestadas hace 7 días o más)
    limite_fecha = datetime.now() - timedelta(days=7)

    subq = (db.session.query(
                MovimientoCanasta.codigo_barras,
                func.max(MovimientoCanasta.fecha_movimiento).label('fecha')
            )
            .filter(MovimientoCanasta.tipo_movimiento == 'Sale')
            .group_by(MovimientoCanasta.codigo_barras)
            .subquery())

    canastas_data = (db.session.query(
                        Canasta.codigo_barras,
                        subq.c.fecha.label('fecha_prestamo'),
                        Vendedor.nombre.label('nombre_vendedor')
                    )
                    .join(subq, Canasta.codigo_barras == subq.c.codigo_barras)
                    .join(MovimientoCanasta, (MovimientoCanasta.codigo_barras == Canasta.codigo_barras) &
                                              (MovimientoCanasta.fecha_movimiento == subq.c.fecha))
                    .join(Vendedor, MovimientoCanasta.codigo_vendedor == Vendedor.codigo_vendedor)
                    .filter(Canasta.actualidad == 'Prestada')
                    .filter(subq.c.fecha <= limite_fecha)
                    .all())

    canastas_perdidas_count = len(canastas_data)

    canastas_perdidas_list = [{
        'codigo_barras': c.codigo_barras,
        'fecha_prestamo': c.fecha_prestamo,
        'nombre_vendedor': c.nombre_vendedor,
        'dias_prestada': (datetime.now().date() - c.fecha_prestamo.date()).days
    } for c in canastas_data]
    
    # Total del mes: pedidos + extras
    total_mes_pedidos = (db.session.query(func.sum(BDPedidoItem.subtotal))
                        .join(BDPedido, BDPedido.id == BDPedidoItem.pedido_id)
                        .filter(BDPedido.fecha >= inicio_mes)
                        .scalar() or 0)

    total_mes_extras = (db.session.query(func.sum(BDExtraItem.subtotal))
                        .join(BDExtra, BDExtra.id == BDExtraItem.extra_id)
                        .filter(BDExtra.fecha >= inicio_mes)
                        .scalar() or 0)

    total_mes_pedidos_extras = total_mes_pedidos + total_mes_extras
    
    return render_template("dashboard/admin_dashboard.html",
                           total_mes=total_mes,
                           total_dia=total_dia,
                           pedidos_dia_vendedores=pedidos_dia_vendedores,
                           pedidos_mes_vendedores=pedidos_mes_vendedores,
                           canastas_perdidas_count=canastas_perdidas_count,
                           canastas_perdidas_list=canastas_perdidas_list,
                           total_mes_pedidos_extras=total_mes_pedidos_extras)

@dashboard_bp.route("/dashboard_vendedor", methods=['GET'])
@login_required
@rol_requerido('vendedor')
def dashboard_vendedor():
    hoy = datetime.now().date()
    inicio_mes = hoy.replace(day=1)

    codigo_vendedor = session.get('codigo_vendedor')

    if not codigo_vendedor:
        flash("No se encontró el código de vendedor en sesión", "danger")
        return render_template("dashboard/vendedor_dashboard.html",
                               comision_mes=0, venta_mes=0, canastas_perdidas_count=0, canastas_prestadas_count=0)

    # Ventas del mes
    venta_mes = (db.session.query(func.sum(BDVenta.total_venta))
                 .filter(BDVenta.codigo_vendedor == codigo_vendedor)
                 .filter(BDVenta.fecha >= inicio_mes)
                 .scalar() or 0)

    # Comisión del mes
    comision_mes = (db.session.query(func.sum(BDVenta.comision))
                    .filter(BDVenta.codigo_vendedor == codigo_vendedor)
                    .filter(BDVenta.fecha >= inicio_mes)
                    .scalar() or 0)

    # Canastas perdidas (mismo enfoque que el reporte)
    limite_fecha = datetime.now() - timedelta(days=7)

    subq = (db.session.query(
                MovimientoCanasta.codigo_barras,
                func.max(MovimientoCanasta.fecha_movimiento).label('fecha')
            )
            .filter(MovimientoCanasta.tipo_movimiento == 'Sale')
            .group_by(MovimientoCanasta.codigo_barras)
            .subquery())

    canastas_data = (db.session.query(
                        Canasta.codigo_barras,
                        subq.c.fecha.label('fecha_prestamo')
                    )
                    .join(subq, Canasta.codigo_barras == subq.c.codigo_barras)
                    .join(MovimientoCanasta, (MovimientoCanasta.codigo_barras == Canasta.codigo_barras) &
                                              (MovimientoCanasta.fecha_movimiento == subq.c.fecha))
                    .filter(Canasta.actualidad == 'Prestada')
                    .filter(MovimientoCanasta.codigo_vendedor == codigo_vendedor)
                    .filter(subq.c.fecha <= limite_fecha)
                    .all())

    canastas_perdidas_count = len(canastas_data)

    canastas_perdidas_list = [{
        'codigo_barras': c.codigo_barras,
        'dias_prestada': (datetime.now().date() - c.fecha_prestamo.date()).days
    } for c in canastas_data]

    # ✅ NUEVO: Canastas prestadas activas (Sale - Entra)
    from sqlalchemy import case

    canastas_prestadas_count = (db.session.query(
        (
            func.sum(case((MovimientoCanasta.tipo_movimiento == 'Sale', 1), else_=0)) -
            func.sum(case((MovimientoCanasta.tipo_movimiento == 'Entra', 1), else_=0))
        ).label('prestadas')
    )
    .filter(MovimientoCanasta.codigo_vendedor == codigo_vendedor)
    .scalar() or 0)

    return render_template("dashboard/vendedor_dashboard.html",
                           comision_mes=comision_mes,
                           venta_mes=venta_mes,
                           canastas_perdidas_count=canastas_perdidas_count,
                           canastas_perdidas_list=canastas_perdidas_list,
                           canastas_prestadas_count=canastas_prestadas_count)

