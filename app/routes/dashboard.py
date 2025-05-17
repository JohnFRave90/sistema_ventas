from flask import Blueprint, render_template, flash, session, redirect, url_for
from flask_login import login_required, current_user
from app import db
from app.models.pedidos import BDPedido
from app.models.pedido_item import BDPedidoItem
from app.models.vendedor import Vendedor
from app.models.canastas import Canasta, MovimientoCanasta
from app.models.ventas import BDVenta
from app.utils.roles import rol_requerido
from datetime import datetime, timedelta
from sqlalchemy import func


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

    # Total acumulado del mes
    total_mes = (db.session.query(func.sum(BDPedidoItem.subtotal))
                 .join(BDPedido, BDPedido.id == BDPedidoItem.pedido_id)
                 .filter(BDPedido.fecha >= inicio_mes)
                 .scalar() or 0)

    # Total acumulado del día
    total_dia = (db.session.query(func.sum(BDPedidoItem.subtotal))
                 .join(BDPedido, BDPedido.id == BDPedidoItem.pedido_id)
                 .filter(BDPedido.fecha == hoy)
                 .scalar() or 0)

    # Pedidos del día por vendedor
    pedidos_dia_vendedores = (db.session.query(
                                Vendedor.nombre,
                                func.sum(BDPedidoItem.subtotal).label('valor_total'))
                              .join(BDPedido, BDPedido.id == BDPedidoItem.pedido_id)
                              .join(Vendedor, BDPedido.codigo_vendedor == Vendedor.codigo_vendedor)
                              .filter(BDPedido.fecha == hoy)
                              .group_by(Vendedor.nombre)
                              .all())

    # Pedidos del mes por vendedor
    pedidos_mes_vendedores = (db.session.query(
                                Vendedor.nombre,
                                func.sum(BDPedidoItem.subtotal).label('valor_total'))
                              .join(BDPedido, BDPedido.id == BDPedidoItem.pedido_id)
                              .join(Vendedor, BDPedido.codigo_vendedor == Vendedor.codigo_vendedor)
                              .filter(BDPedido.fecha >= inicio_mes)
                              .group_by(Vendedor.nombre)
                              .all())

    # Canastas Perdidas (prestadas hace más de 7 días)
    limite_fecha = hoy - timedelta(days=7)

    subq = (db.session.query(
                MovimientoCanasta.codigo_barras,
                func.max(MovimientoCanasta.fecha_movimiento).label('fecha')
            )
            .filter(MovimientoCanasta.tipo_movimiento == 'Sale')
            .group_by(MovimientoCanasta.codigo_barras)
            .subquery())

    canastas_perdidas_count = (db.session.query(func.count())
                            .select_from(Canasta)
                            .join(subq, Canasta.codigo_barras == subq.c.codigo_barras)
                            .filter(Canasta.actualidad == 'Prestada')
                            .filter(subq.c.fecha <= limite_fecha)
                            .scalar() or 0)


    return render_template("dashboard/admin_dashboard.html",
                           total_mes=total_mes,
                           total_dia=total_dia,
                           pedidos_dia_vendedores=pedidos_dia_vendedores,
                           pedidos_mes_vendedores=pedidos_mes_vendedores,
                           canastas_perdidas_count=canastas_perdidas_count)
    
@dashboard_bp.route("/dashboard_semiadmin", methods=['GET'])
@login_required
@rol_requerido('semiadmin')
def dashboard_semiadmin():
    hoy = datetime.now().date()
    inicio_mes = hoy.replace(day=1)

    # Total acumulado del mes
    total_mes = (db.session.query(func.sum(BDPedidoItem.subtotal))
                 .join(BDPedido, BDPedido.id == BDPedidoItem.pedido_id)
                 .filter(BDPedido.fecha >= inicio_mes)
                 .scalar() or 0)

    # Total acumulado del día
    total_dia = (db.session.query(func.sum(BDPedidoItem.subtotal))
                 .join(BDPedido, BDPedido.id == BDPedidoItem.pedido_id)
                 .filter(BDPedido.fecha == hoy)
                 .scalar() or 0)

    # Pedidos del día por vendedor
    pedidos_dia_vendedores = (db.session.query(
                                Vendedor.nombre,
                                func.sum(BDPedidoItem.subtotal).label('valor_total'))
                              .join(BDPedido, BDPedido.id == BDPedidoItem.pedido_id)
                              .join(Vendedor, BDPedido.codigo_vendedor == Vendedor.codigo_vendedor)
                              .filter(BDPedido.fecha == hoy)
                              .group_by(Vendedor.nombre)
                              .all())

    # Pedidos del mes por vendedor
    pedidos_mes_vendedores = (db.session.query(
                                Vendedor.nombre,
                                func.sum(BDPedidoItem.subtotal).label('valor_total'))
                              .join(BDPedido, BDPedido.id == BDPedidoItem.pedido_id)
                              .join(Vendedor, BDPedido.codigo_vendedor == Vendedor.codigo_vendedor)
                              .filter(BDPedido.fecha >= inicio_mes)
                              .group_by(Vendedor.nombre)
                              .all())

    # Canastas Perdidas (prestadas hace más de 7 días)
    limite_fecha = hoy - timedelta(days=7)

    subq = (db.session.query(
                MovimientoCanasta.codigo_barras,
                func.max(MovimientoCanasta.fecha_movimiento).label('fecha')
            )
            .filter(MovimientoCanasta.tipo_movimiento == 'Sale')
            .group_by(MovimientoCanasta.codigo_barras)
            .subquery())

    canastas_perdidas_count = (db.session.query(func.count())
                               .select_from(Canasta)
                               .join(subq, Canasta.codigo_barras == subq.c.codigo_barras)
                               .filter(Canasta.actualidad == 'Prestada')
                               .filter(subq.c.fecha <= limite_fecha)
                               .scalar() or 0)

    return render_template("dashboard/admin_dashboard.html",
                           total_mes=total_mes,
                           total_dia=total_dia,
                           pedidos_dia_vendedores=pedidos_dia_vendedores,
                           pedidos_mes_vendedores=pedidos_mes_vendedores,
                           canastas_perdidas_count=canastas_perdidas_count)

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
                               comision_mes=0, venta_mes=0, canastas_perdidas_count=0)

    # Ventas del mes (valor total)
    venta_mes = (db.session.query(func.sum(BDVenta.total_venta))
                 .filter(BDVenta.codigo_vendedor == codigo_vendedor)
                 .filter(BDVenta.fecha >= inicio_mes)
                 .scalar() or 0)

    # Comisión del mes
    comision_mes = (db.session.query(func.sum(BDVenta.comision))
                    .filter(BDVenta.codigo_vendedor == codigo_vendedor)
                    .filter(BDVenta.fecha >= inicio_mes)
                    .scalar() or 0)

    # Canastas Perdidas (Prestadas hace más de 7 días)
    limite_fecha = hoy - timedelta(days=7)

    subq = (db.session.query(
                MovimientoCanasta.codigo_barras,
                func.max(MovimientoCanasta.fecha_movimiento).label('fecha')
            )
            .filter(MovimientoCanasta.tipo_movimiento == 'Sale')
            .filter(MovimientoCanasta.codigo_vendedor == codigo_vendedor)
            .group_by(MovimientoCanasta.codigo_barras)
            .subquery())

    canastas_perdidas_count = (db.session.query(func.count())
                               .select_from(Canasta)
                               .join(subq, Canasta.codigo_barras == subq.c.codigo_barras)
                               .filter(Canasta.actualidad == 'Prestada')
                               .filter(subq.c.fecha <= limite_fecha)
                               .scalar() or 0)

    return render_template("dashboard/vendedor_dashboard.html",
                           comision_mes=comision_mes,
                           venta_mes=venta_mes,
                           canastas_perdidas_count=canastas_perdidas_count)

