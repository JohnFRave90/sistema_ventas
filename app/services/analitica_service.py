# app/services/analitica_service.py
"""Recolección de métricas para la analítica diaria (capa con acceso a BD).

La aritmética de inventario vive en ``app.utils.analitica`` (pura/testeable).
Las ventas se toman de ``BDVentaAutoventa`` (la tabla que produce la app móvil),
igual que el resumen de turno, para que los números cuadren entre vistas.
"""

from datetime import date as _date

from sqlalchemy import func

from app import db
from app.models.cliente import Cliente
from app.models.visita_cliente import BDVisitaCliente
from app.models.despachos import BDDespacho, BDDespachoItem
from app.models.devoluciones import BDDevolucion
from app.models.devolucion_item import BDDevolucionItem
from app.models.cambio import BD_CAMBIO
from app.models.venta_autoventa import BDVentaAutoventa, BDVentaAutoventaItem
from app.models.vendedor import Vendedor
from app.models.producto import Producto
from app.utils.analitica import calcular_metricas_inventario

PRE_TURNO_TIPO_ORIGEN = 'PREAPP'


def _sum(query_value):
    return query_value if query_value is not None else 0


def recolectar_resumen(fecha=None, vendedor=None):
    fecha = fecha or _date.today()

    def _vfilter(query, col):
        return query.filter(col == vendedor) if vendedor else query

    # --- Ventas (autoventa) ---
    total_vendido = _sum(
        _vfilter(
            db.session.query(func.coalesce(func.sum(BDVentaAutoventa.total), 0))
            .filter(BDVentaAutoventa.fecha == fecha),
            BDVentaAutoventa.codigo_vendedor,
        ).scalar()
    )

    vendido_unidades = _sum(
        _vfilter(
            db.session.query(func.coalesce(func.sum(BDVentaAutoventaItem.cantidad), 0))
            .join(BDVentaAutoventa, BDVentaAutoventa.id == BDVentaAutoventaItem.autoventa_id)
            .filter(BDVentaAutoventa.fecha == fecha),
            BDVentaAutoventa.codigo_vendedor,
        ).scalar()
    )

    # --- Visitas ---
    visitados = _sum(
        _vfilter(
            db.session.query(func.count(BDVisitaCliente.id)).filter(
                BDVisitaCliente.fecha_visita == fecha,
                BDVisitaCliente.estado == 'completada',
            ),
            BDVisitaCliente.codigo_vendedor,
        ).scalar()
    )
    excepciones = _sum(
        _vfilter(
            db.session.query(func.count(BDVisitaCliente.id)).filter(
                BDVisitaCliente.fecha_visita == fecha,
                BDVisitaCliente.estado == 'excepcion',
            ),
            BDVisitaCliente.codigo_vendedor,
        ).scalar()
    )
    total_clientes = _sum(
        _vfilter(
            db.session.query(func.count(Cliente.id)).filter(Cliente.activo.is_(True)),
            Cliente.codigo_vendedor,
        ).scalar()
    )
    pendientes = max(0, int(total_clientes) - int(visitados) - int(excepciones))

    # --- Devoluciones (unidades y conteo) ---
    devuelto_unidades = _sum(
        _vfilter(
            db.session.query(func.coalesce(func.sum(BDDevolucionItem.cantidad), 0))
            .join(BDDevolucion, BDDevolucion.id == BDDevolucionItem.devolucion_id)
            .filter(BDDevolucion.fecha == fecha),
            BDDevolucion.codigo_vendedor,
        ).scalar()
    )

    # --- Cambios (solo valor monetario; sin granularidad por producto) ---
    total_cambios = _sum(
        _vfilter(
            db.session.query(func.coalesce(func.sum(BD_CAMBIO.valor_cambio), 0))
            .filter(BD_CAMBIO.fecha == fecha),
            BD_CAMBIO.codigo_vendedor,
        ).scalar()
    )

    # --- Inventario despachado (sistema, excluye PREAPP para no doble-contar) ---
    despachado_unidades = _sum(
        _vfilter(
            db.session.query(func.coalesce(func.sum(BDDespachoItem.cantidad), 0))
            .join(BDDespacho, BDDespacho.id == BDDespachoItem.despacho_id)
            .filter(
                BDDespacho.fecha == fecha,
                BDDespacho.tipo_origen != PRE_TURNO_TIPO_ORIGEN,
            ),
            BDDespacho.vendedor_cod,
        ).scalar()
    )

    inventario = calcular_metricas_inventario(
        despachado=int(despachado_unidades),
        vendido=int(vendido_unidades),
        devuelto=int(devuelto_unidades),
        # devolucion_anterior y cambios_entregados no tienen agregado fiable por
        # producto aquí; se documentan como 0 (ver utils/analitica.py).
    )

    return {
        'fecha': str(fecha),
        'vendedor': vendedor or None,
        'total_vendido': float(total_vendido),
        'clientes_visitados': int(visitados),
        'clientes_pendientes': int(pendientes),
        'excepciones': int(excepciones),
        'devoluciones': int(devuelto_unidades),
        'cambios': float(total_cambios),
        'inventario_despachado': inventario['despachado'],
        'inventario_vendido': inventario['vendido'],
        'inventario_devuelto': inventario['devuelto'],
        'inventario_restante_estimado': inventario['restante_estimado'],
    }


def recolectar_breakdown(fecha=None, limite=8):
    """Series para gráficas: ventas por vendedor, top productos vendidos/devueltos."""
    fecha = fecha or _date.today()

    # Ventas por vendedor (autoventa) con nombre del vendedor.
    filas_vend = db.session.query(
        BDVentaAutoventa.codigo_vendedor,
        func.coalesce(func.sum(BDVentaAutoventa.total), 0),
    ).filter(BDVentaAutoventa.fecha == fecha).group_by(
        BDVentaAutoventa.codigo_vendedor
    ).order_by(func.sum(BDVentaAutoventa.total).desc()).all()

    codigos = [cod for cod, _ in filas_vend]
    nombres = {}
    if codigos:
        nombres = {
            v.codigo_vendedor: v.nombre
            for v in Vendedor.query.filter(Vendedor.codigo_vendedor.in_(codigos)).all()
        }
    ventas_por_vendedor = [
        {'vendedor': cod, 'nombre': nombres.get(cod, cod), 'total': float(total or 0)}
        for cod, total in filas_vend
    ]

    # Top productos vendidos (unidades).
    filas_vendidos = db.session.query(
        BDVentaAutoventaItem.producto_cod,
        func.coalesce(func.sum(BDVentaAutoventaItem.cantidad), 0),
    ).join(
        BDVentaAutoventa, BDVentaAutoventa.id == BDVentaAutoventaItem.autoventa_id
    ).filter(BDVentaAutoventa.fecha == fecha).group_by(
        BDVentaAutoventaItem.producto_cod
    ).order_by(func.sum(BDVentaAutoventaItem.cantidad).desc()).limit(limite).all()

    # Top productos devueltos (unidades).
    filas_devueltos = db.session.query(
        BDDevolucionItem.producto_cod,
        func.coalesce(func.sum(BDDevolucionItem.cantidad), 0),
    ).join(
        BDDevolucion, BDDevolucion.id == BDDevolucionItem.devolucion_id
    ).filter(BDDevolucion.fecha == fecha).group_by(
        BDDevolucionItem.producto_cod
    ).order_by(func.sum(BDDevolucionItem.cantidad).desc()).limit(limite).all()

    cods_prod = list({c for c, _ in filas_vendidos} | {c for c, _ in filas_devueltos})
    prod_nombres = {}
    if cods_prod:
        prod_nombres = {
            p.codigo: p.nombre
            for p in Producto.query.filter(Producto.codigo.in_(cods_prod)).all()
        }

    productos_vendidos = [
        {'producto_cod': c, 'nombre': prod_nombres.get(c, c), 'cantidad': int(q or 0)}
        for c, q in filas_vendidos
    ]
    productos_devueltos = [
        {'producto_cod': c, 'nombre': prod_nombres.get(c, c), 'cantidad': int(q or 0)}
        for c, q in filas_devueltos
    ]

    return {
        'ventas_por_vendedor': ventas_por_vendedor,
        'productos_vendidos': productos_vendidos,
        'productos_devueltos': productos_devueltos,
    }
