# app/routes/liquidaciones.py

from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_required, current_user
from app import db
from app.models.liquidacion import BD_LIQUIDACION
from app.models.ventas import BDVenta
from app.models.vendedor import Vendedor
from app.utils.roles import rol_requerido
from app.utils.pdf_utils import generate_liquidacion_pdf
from datetime import datetime
from flask import send_file
from io import BytesIO
from app.models.cambio import BD_CAMBIO
from app.utils.notificaciones import notificar_accion

liquidaciones_bp = Blueprint('liquidaciones', __name__, url_prefix='/liquidaciones')

@liquidaciones_bp.route('/crear', methods=['GET', 'POST'])
@login_required
@rol_requerido('administrador', 'semiadmin')
def crear_liquidacion():
    from app.utils.notificaciones import notificar_accion

    vendedores = Vendedor.query.order_by(Vendedor.nombre).all()

    fecha = request.form.get('fecha')
    vendedor_codigo = request.form.get('vendedor')

    venta = None
    cambio = None
    descuento_cambios = 0.0

    if fecha and vendedor_codigo:
        fecha_obj = datetime.strptime(fecha, '%Y-%m-%d').date()

        existente = BD_LIQUIDACION.query.filter_by(fecha=fecha_obj, codigo_vendedor=vendedor_codigo).first()
        if existente:
            flash(f"Ya existe una liquidación para este vendedor en esa fecha.", "danger")
            return redirect(url_for('liquidaciones.crear_liquidacion'))

        venta = BDVenta.query.filter_by(fecha=fecha_obj, codigo_vendedor=vendedor_codigo, liquidada=0).first()
        if not venta:
            flash("No hay venta pendiente para liquidar ese día y vendedor.", "warning")
            return render_template('liquidaciones/crear.html', vendedores=vendedores)

        cambio = BD_CAMBIO.query.filter_by(fecha=fecha_obj, codigo_vendedor=vendedor_codigo).first()
        descuento_cambios = float(cambio.valor_cambio) if cambio else 0.0

        if 'pago_banco' in request.form:
            pago_banco = float(request.form.get('pago_banco', 0) or 0)
            pago_efectivo = float(request.form.get('pago_efectivo', 0) or 0)
            pago_otros = float(request.form.get('pago_otros', 0) or 0)
            comentarios = request.form.get('comentarios', '')

            valor_venta = venta.total_venta
            valor_comision = venta.comision
            valor_panaderia = valor_venta - valor_comision
            total_a_pagar = valor_panaderia - descuento_cambios

            codigo = generar_codigo_liquidacion()

            liquidacion = BD_LIQUIDACION(
                codigo=codigo,
                fecha=fecha_obj,
                codigo_vendedor=vendedor_codigo,
                codigo_venta=venta.id,
                valor_venta=valor_venta,
                valor_comision=valor_comision,
                descuento_cambios=descuento_cambios,
                valor_a_pagar=total_a_pagar,
                pago_banco=pago_banco,
                pago_efectivo=pago_efectivo,
                pago_otros=pago_otros,
                comentarios=comentarios,
                usuario_creador=current_user.nombre_usuario
            )
            db.session.add(liquidacion)

            venta.liquidada = 1
            db.session.commit()

            vendedor = Vendedor.query.filter_by(codigo_vendedor=vendedor_codigo).first()
            notificar_accion("crear_liquidacion", {
                "vendedor": vendedor.nombre if vendedor else vendedor_codigo,
                "fecha_inicio": fecha,
                "fecha_fin": fecha
            })

            flash(f"Liquidación {codigo} creada correctamente.", "success")
            return redirect(url_for('liquidaciones.listar_liquidaciones'))

    return render_template('liquidaciones/crear.html',
                           vendedores=vendedores,
                           venta=venta,
                           cambio=cambio,
                           descuento_cambios=descuento_cambios,
                           fecha=fecha,
                           vendedor_codigo=vendedor_codigo)

def generar_codigo_liquidacion():
    last = BD_LIQUIDACION.query.order_by(BD_LIQUIDACION.id.desc()).first()
    next_id = 1 if not last else last.id + 1
    return f"LQ-{str(next_id).zfill(5)}"

@liquidaciones_bp.route('/listar')
@login_required
@rol_requerido('administrador', 'semiadmin')
def listar_liquidaciones():
    query = BD_LIQUIDACION.query

    fecha_inicio = request.args.get('fecha_inicio')
    fecha_fin    = request.args.get('fecha_fin')
    codigo       = request.args.get('codigo', '').strip()
    page         = request.args.get('page', 1, type=int)

    if fecha_inicio:
        query = query.filter(BD_LIQUIDACION.fecha >= fecha_inicio)
    if fecha_fin:
        query = query.filter(BD_LIQUIDACION.fecha <= fecha_fin)
    if codigo:
        query = query.filter(BD_LIQUIDACION.codigo.ilike(f"%{codigo}%"))

    paginacion = query.order_by(
        BD_LIQUIDACION.fecha.desc(),
        BD_LIQUIDACION.id.desc()
    ).paginate(page=page, per_page=30)

    vendedores = Vendedor.query.all()
    vendedores_dict = {v.codigo_vendedor: v for v in vendedores}

    return render_template(
        'liquidaciones/listar.html',
        liquidaciones=paginacion.items,
        pagination=paginacion,
        vendedores_dict=vendedores_dict,
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
        codigo=codigo
    )

@liquidaciones_bp.route('/editar/<int:id>', methods=['GET', 'POST'])
@login_required
@rol_requerido('administrador')
def editar_liquidacion(id):
    from app.utils.notificaciones import notificar_accion

    liquidacion = BD_LIQUIDACION.query.get_or_404(id)

    venta = BDVenta.query.get_or_404(liquidacion.codigo_venta)
    vendedor = Vendedor.query.filter_by(codigo_vendedor=liquidacion.codigo_vendedor).first()
    cambio = BD_CAMBIO.query.filter_by(fecha=liquidacion.fecha, codigo_vendedor=liquidacion.codigo_vendedor).first()
    descuento_cambios = cambio.valor_cambio if cambio else 0

    valor_venta = venta.total_venta
    valor_comision = venta.comision
    valor_panaderia = valor_venta - valor_comision
    total_a_pagar = valor_panaderia - descuento_cambios

    if request.method == 'POST':
        liquidacion.pago_banco = float(request.form.get('pago_banco', 0) or 0)
        liquidacion.pago_efectivo = float(request.form.get('pago_efectivo', 0) or 0)
        liquidacion.pago_otros = float(request.form.get('pago_otros', 0) or 0)
        liquidacion.comentarios = request.form.get('comentarios', '')

        liquidacion.valor_venta = valor_venta
        liquidacion.valor_comision = valor_comision
        liquidacion.descuento_cambios = descuento_cambios
        liquidacion.valor_a_pagar = total_a_pagar

        db.session.commit()

        notificar_accion("editar_liquidacion", {
            "codigo": liquidacion.codigo,
            "vendedor": vendedor.nombre if vendedor else liquidacion.codigo_vendedor,
            "fecha": liquidacion.fecha.isoformat()
        })

        flash(f"Liquidación {liquidacion.codigo} actualizada correctamente.", "success")
        return redirect(url_for('liquidaciones.listar_liquidaciones'))

    return render_template('liquidaciones/editar.html',
                           liquidacion=liquidacion,
                           venta=venta,
                           vendedor=vendedor,
                           cambio=cambio,
                           descuento_cambios=descuento_cambios)

@liquidaciones_bp.route('/eliminar/<int:id>', methods=['POST'])
@login_required
@rol_requerido('administrador')
def eliminar_liquidacion(id):
    from app.utils.notificaciones import notificar_accion

    liquidacion = BD_LIQUIDACION.query.get_or_404(id)

    # Guardar datos antes de eliminar
    codigo = liquidacion.codigo
    fecha = liquidacion.fecha.isoformat()
    vendedor = Vendedor.query.filter_by(codigo_vendedor=liquidacion.codigo_vendedor).first()
    nombre_vendedor = vendedor.nombre if vendedor else liquidacion.codigo_vendedor

    # Revertir venta
    venta = BDVenta.query.get(liquidacion.codigo_venta)
    if venta:
        venta.liquidada = 0

    db.session.delete(liquidacion)
    db.session.commit()

    notificar_accion("eliminar_liquidacion", {
        "codigo": codigo,
        "vendedor": nombre_vendedor,
        "fecha": fecha
    })

    flash(f"Liquidación {codigo} eliminada correctamente.", "success")
    return redirect(url_for('liquidaciones.listar_liquidaciones'))

@liquidaciones_bp.route('/exportar/<int:id>', methods=['GET'])
@login_required
def exportar_liquidacion_pdf(id):
    # Buscar liquidación
    liquidacion = BD_LIQUIDACION.query.get_or_404(id)

    # Buscar venta asociada (recuerda que es por id)
    venta = BDVenta.query.get_or_404(liquidacion.codigo_venta)

    # Buscar vendedor
    vendedor = Vendedor.query.filter_by(codigo_vendedor=liquidacion.codigo_vendedor).first()

    # Buscar cambio si lo hay
    cambio = BD_CAMBIO.query.filter_by(fecha=liquidacion.fecha, codigo_vendedor=liquidacion.codigo_vendedor).first()

    # Generar PDF usando tu función optimizada
    pdf_file = generate_liquidacion_pdf(liquidacion, vendedor, venta, cambio)

    # Retornar archivo PDF
    return send_file(pdf_file,
                     download_name=f"{liquidacion.codigo}.pdf",
                     as_attachment=True,
                     mimetype='application/pdf')
 
    