from flask import Blueprint, render_template, request, redirect, url_for, flash
from app import db
from app.models.producto import Producto
from app.utils.roles import rol_requerido
import csv
from werkzeug.utils import secure_filename
import os
from flask import current_app

productos_bp = Blueprint('productos', __name__, url_prefix='/productos')

# LISTAR PRODUCTOS
@productos_bp.route('/')
@rol_requerido('administrador', 'semiadmin')
def listar_productos():
    """Lista los productos con la posibilidad de elegir el orden."""

    orden = request.args.get('orden', 'personalizado')

    if orden == 'nombre':
        productos = Producto.query.order_by(Producto.nombre).all()
    elif orden == 'codigo':
        productos = Producto.query.order_by(Producto.codigo).all()
    else:
        productos = Producto.query.order_by(Producto.orden, Producto.nombre).all()

    return render_template('productos/listar.html', productos=productos, orden_actual=orden)

# CREAR PRODUCTO
@productos_bp.route('/crear', methods=['GET', 'POST'])
@rol_requerido('administrador')
def crear_producto():
    if request.method == 'POST':
        codigo = request.form['codigo'].strip()
        nombre = request.form['nombre']
        precio = float(request.form['precio'])
        categoria = request.form['categoria']
        activo = 'activo' in request.form

        max_orden = db.session.query(db.func.max(Producto.orden)).scalar() or 0
        nuevo = Producto(codigo=codigo, nombre=nombre, precio=precio, categoria=categoria, activo=activo, orden=max_orden + 1)
        db.session.add(nuevo)
        db.session.commit()
        flash('Producto creado correctamente.', 'success')
        return redirect(url_for('productos.listar_productos'))

    return render_template('productos/crear.html')

# EDITAR PRODUCTO
@productos_bp.route('/editar/<int:id>', methods=['GET', 'POST'])
@rol_requerido('administrador')
def editar_producto(id):
    producto = Producto.query.get_or_404(id)
    if request.method == 'POST':
        producto.nombre = request.form['nombre']
        producto.precio = float(request.form['precio'])
        producto.categoria = request.form['categoria']
        producto.activo = 'activo' in request.form
        db.session.commit()
        flash('Producto actualizado.', 'success')
        return redirect(url_for('productos.listar_productos'))

    return render_template('productos/editar.html', producto=producto)

# ELIMINAR PRODUCTO
@productos_bp.route('/eliminar/<int:id>', methods=['POST'])
@rol_requerido('administrador')
def eliminar_producto(id):
    producto = Producto.query.get_or_404(id)
    db.session.delete(producto)
    db.session.commit()
    flash('Producto eliminado correctamente.', 'success')
    return redirect(url_for('productos.listar_productos'))

@productos_bp.route('/importar', methods=['GET', 'POST'])
@rol_requerido('administrador')
def importar_productos():
    if request.method == 'POST':
        archivo = request.files['archivo']
        if not archivo or not archivo.filename.endswith('.csv'):
            flash("Por favor sube un archivo CSV válido.", 'danger')
            return redirect(url_for('productos.importar_productos'))

        upload_folder = os.path.join(current_app.root_path, 'uploads')
        os.makedirs(upload_folder, exist_ok=True)
        ruta_archivo = os.path.join(upload_folder, secure_filename(archivo.filename))
        archivo.save(ruta_archivo)

        errores = []
        max_orden = db.session.query(db.func.max(Producto.orden)).scalar() or 0
        contador = 1
        with open(ruta_archivo, newline='', encoding='utf-8') as f:
            lector = csv.DictReader(f)
            lector.fieldnames[0] = lector.fieldnames[0].lstrip('\ufeff')

            for fila in lector:
                try:
                    codigo = fila['codigo'].strip()
                    nombre = fila['nombre'].strip()
                    precio = float(fila['precio'])
                    categoria = fila['categoria'].strip().lower()

                    duplicado = Producto.query.filter(
                        (Producto.codigo == codigo) | (Producto.nombre == nombre)
                    ).first()

                    if not duplicado:
                        nuevo = Producto(
                            codigo=codigo,
                            nombre=nombre,
                            precio=precio,
                            categoria=categoria,
                            activo=True,
                            orden=max_orden + contador
                        )
                        contador += 1                        
                        db.session.add(nuevo)
                    else:
                        errores.append({
                            'codigo': codigo,
                            'nombre': nombre,
                            'razon': 'Duplicado'
                        })

                except Exception as e:
                    errores.append({
                        'codigo': fila.get('codigo', ''),
                        'nombre': fila.get('nombre', ''),
                        'razon': f'Error: {str(e)}'
                    })

        db.session.commit()

        if errores:
            ruta_fallos = os.path.join(upload_folder, 'fallos_importacion.csv')
            with open(ruta_fallos, 'w', newline='', encoding='utf-8') as fallo_csv:
                writer = csv.DictWriter(fallo_csv, fieldnames=['codigo', 'nombre', 'razon'])
                writer.writeheader()
                writer.writerows(errores)

            flash("Importación finalizada con advertencias. Puedes revisar los productos no importados:", "warning")
            flash('<a href="/uploads/fallos_importacion.csv" target="_blank">Descargar fallos</a>', "info")
        else:
            flash("Importación completada sin errores.", "success")

        return redirect(url_for('productos.listar_productos'))

    return render_template('productos/importar.html')


# ----- ORDENAR PRODUCTOS -----
@productos_bp.route('/actualizar_orden', methods=['POST'])
@rol_requerido('administrador', 'semiadmin')
def actualizar_orden_productos():
    """Actualiza el orden de los productos desde el frontend via AJAX."""

    orden_lista = request.get_json().get('orden', [])

    for idx, prod_id in enumerate(orden_lista):
        producto = Producto.query.get(int(prod_id))
        if producto:
            producto.orden = idx

    db.session.commit()
    return {'success': True}