from flask import Blueprint, render_template, flash, session, redirect, url_for, request
from flask_login import login_required, current_user
from app import db
from app.models.pedidos import BDPedido
from app.models.pedido_item import BDPedidoItem
from app.models.vendedor import Vendedor
from app.models.canastas import Canasta, MovimientoCanasta
from app.models.ventas import BDVenta
from app.models.cliente import Cliente
from app.models.visita_cliente import BDVisitaCliente
from app.models.venta_autoventa import BDVentaAutoventa
from app.models.extra_item import BDExtraItem
from app.models.extras import BDExtra
from app.utils.roles import rol_requerido
from datetime import datetime, timedelta, date
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


@dashboard_bp.route("/dashboard/mapa-operativo", methods=['GET'])
@login_required
@rol_requerido('administrador', 'semiadmin')
def dashboard_mapa_operativo():
    fecha_raw = (request.args.get('fecha') or '').strip()
    vendedor_filtro = (request.args.get('vendedor') or '').strip()

    if fecha_raw:
        try:
            fecha_objetivo = date.fromisoformat(fecha_raw)
        except ValueError:
            fecha_objetivo = datetime.now().date()
            flash('Fecha invalida. Se uso la fecha actual.', 'warning')
    else:
        fecha_objetivo = datetime.now().date()

    vendedores = (db.session.query(Vendedor.codigo_vendedor, Vendedor.nombre)
                  .order_by(Vendedor.nombre.asc())
                  .all())
    vendedores_map = {v.codigo_vendedor: v.nombre for v in vendedores}

    clientes_query = Cliente.query.filter(
        Cliente.latitud.isnot(None),
        Cliente.longitud.isnot(None),
    )
    if vendedor_filtro:
        clientes_query = clientes_query.filter(Cliente.codigo_vendedor == vendedor_filtro)
    clientes = clientes_query.all()

    visitas_query = BDVisitaCliente.query.filter(BDVisitaCliente.fecha_visita == fecha_objetivo)
    if vendedor_filtro:
        visitas_query = visitas_query.filter(BDVisitaCliente.codigo_vendedor == vendedor_filtro)
    visitas = visitas_query.order_by(BDVisitaCliente.id.desc()).all()

    ventas_query = BDVentaAutoventa.query.filter(BDVentaAutoventa.fecha == fecha_objetivo)
    if vendedor_filtro:
        ventas_query = ventas_query.filter(BDVentaAutoventa.codigo_vendedor == vendedor_filtro)
    ventas = ventas_query.order_by(BDVentaAutoventa.id.desc()).all()

    clientes_por_id = {c.id: c for c in clientes}

    estado_por_cliente = {}
    for visita in visitas:
        previo = estado_por_cliente.get(visita.cliente_id)
        if previo is None or visita.id > previo['id']:
            estado_por_cliente[visita.cliente_id] = {
                'id': visita.id,
                'estado': (visita.estado or 'pendiente').lower(),
            }

    clientes_payload = []
    total_excepciones = 0
    total_visitados = 0

    for cliente in clientes:
        lat = float(cliente.latitud)
        lng = float(cliente.longitud)

        estado = 'pendiente'
        estado_visita = estado_por_cliente.get(cliente.id)
        if estado_visita:
            if estado_visita['estado'] == 'completada':
                estado = 'visitado'
                total_visitados += 1
            elif estado_visita['estado'] == 'excepcion':
                estado = 'excepcion'
                total_excepciones += 1
            elif estado_visita['estado'] == 'en_progreso':
                estado = 'en_progreso'

        clientes_payload.append({
            'id': cliente.id,
            'codigo_cliente': cliente.codigo_cliente,
            'nombre': cliente.nombre,
            'direccion': cliente.direccion or '',
            'ciudad': cliente.ciudad or '',
            'ruta': cliente.ruta or 'Sin ruta',
            'codigo_vendedor': cliente.codigo_vendedor,
            'vendedor': vendedores_map.get(cliente.codigo_vendedor, cliente.codigo_vendedor),
            'lat': lat,
            'lng': lng,
            'estado': estado,
        })

    visitas_payload = []
    visitas_vistas = set()
    for visita in visitas:
        if visita.id in visitas_vistas:
            continue
        visitas_vistas.add(visita.id)

        cliente = clientes_por_id.get(visita.cliente_id)
        lat = float(visita.lat_checkin) if visita.lat_checkin is not None else (float(cliente.latitud) if cliente and cliente.latitud is not None else None)
        lng = float(visita.lng_checkin) if visita.lng_checkin is not None else (float(cliente.longitud) if cliente and cliente.longitud is not None else None)
        if lat is None or lng is None:
            continue

        visitas_payload.append({
            'id': visita.id,
            'cliente_id': visita.cliente_id,
            'cliente': cliente.nombre if cliente else f'Cliente {visita.cliente_id}',
            'codigo_vendedor': visita.codigo_vendedor,
            'vendedor': vendedores_map.get(visita.codigo_vendedor, visita.codigo_vendedor),
            'estado': (visita.estado or 'pendiente').lower(),
            'lat': lat,
            'lng': lng,
            'checkin_at': visita.checkin_at.isoformat() if visita.checkin_at else None,
            'checkout_at': visita.checkout_at.isoformat() if visita.checkout_at else None,
        })

    ventas_por_cliente = {}
    total_ventas_monto = 0.0
    total_ventas_count = 0
    for venta in ventas:
        total_ventas_count += 1
        total_ventas_monto += float(venta.total or 0)
        item = ventas_por_cliente.get(venta.cliente_id)
        if item is None:
            ventas_por_cliente[venta.cliente_id] = {
                'cantidad': 0,
                'total': 0.0,
                'codigo_vendedor': venta.codigo_vendedor,
            }
            item = ventas_por_cliente[venta.cliente_id]

        item['cantidad'] += 1
        item['total'] += float(venta.total or 0)

    ventas_payload = []
    for cliente_id, data in ventas_por_cliente.items():
        cliente = clientes_por_id.get(cliente_id)
        if not cliente:
            continue
        ventas_payload.append({
            'cliente_id': cliente_id,
            'cliente': cliente.nombre,
            'codigo_vendedor': data['codigo_vendedor'],
            'vendedor': vendedores_map.get(data['codigo_vendedor'], data['codigo_vendedor']),
            'lat': float(cliente.latitud),
            'lng': float(cliente.longitud),
            'cantidad': data['cantidad'],
            'total': round(data['total'], 2),
        })

    return render_template(
        'dashboard/mapa_operativo.html',
        fecha_objetivo=fecha_objetivo,
        vendedor_filtro=vendedor_filtro,
        vendedores=vendedores,
        mapa_payload={
            'clientes': clientes_payload,
            'visitas': visitas_payload,
            'ventas': ventas_payload,
        },
        resumen={
            'clientes': len(clientes_payload),
            'visitados': total_visitados,
            'excepciones': total_excepciones,
            'ventas_cantidad': total_ventas_count,
            'ventas_total': round(total_ventas_monto, 2),
        },
    )

