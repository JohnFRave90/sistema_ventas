# Crear el script SQL para MySQL con las tablas definidas
sql_script = """
-- Base de datos: sistema_ventas

CREATE DATABASE IF NOT EXISTS sistema_ventas;
USE sistema_ventas;

-- Tabla de usuarios
CREATE TABLE usuarios (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nombre_usuario VARCHAR(100) NOT NULL UNIQUE,
    contraseña VARCHAR(255) NOT NULL,
    rol ENUM('administrador', 'semiadmin', 'vendedor') NOT NULL
);

-- Tabla de vendedores
CREATE TABLE vendedores (
    id INT AUTO_INCREMENT PRIMARY KEY,
    codigo VARCHAR(50) NOT NULL UNIQUE,
    nombre VARCHAR(100) NOT NULL,
    comision_pan DECIMAL(5,2) NOT NULL,
    comision_bizcocheria DECIMAL(5,2) NOT NULL
);

-- Tabla de productos
CREATE TABLE productos (
    id INT AUTO_INCREMENT PRIMARY KEY,
    codigo VARCHAR(50) NOT NULL UNIQUE,
    nombre VARCHAR(100) NOT NULL,
    precio DECIMAL(10,2) NOT NULL,
    categoria ENUM('panaderia', 'bizcocheria') NOT NULL,
    estado BOOLEAN DEFAULT TRUE
);

-- Tabla de documentos (pedidos, extras, devoluciones)
CREATE TABLE documentos (
    id INT AUTO_INCREMENT PRIMARY KEY,
    codigo VARCHAR(50) NOT NULL UNIQUE,
    tipo ENUM('pedido', 'extra', 'devolucion') NOT NULL,
    fecha DATE NOT NULL,
    vendedor_id INT,
    comentarios TEXT,
    estado ENUM('pendiente', 'usado', 'anulado') DEFAULT 'pendiente',
    FOREIGN KEY (vendedor_id) REFERENCES vendedores(id)
);

-- Detalle de cada documento
CREATE TABLE documento_detalle (
    id INT AUTO_INCREMENT PRIMARY KEY,
    documento_id INT,
    producto_id INT,
    cantidad INT NOT NULL,
    FOREIGN KEY (documento_id) REFERENCES documentos(id),
    FOREIGN KEY (producto_id) REFERENCES productos(id)
);

-- Tabla de ventas
CREATE TABLE ventas (
    id INT AUTO_INCREMENT PRIMARY KEY,
    codigo VARCHAR(50) NOT NULL UNIQUE,
    fecha DATE NOT NULL,
    vendedor_id INT,
    pedido_id INT,
    devolucion_anterior_id INT,
    extra_id INT,
    devolucion_dia_id INT,
    venta_total DECIMAL(12,2),
    comision_total DECIMAL(12,2),
    FOREIGN KEY (vendedor_id) REFERENCES vendedores(id),
    FOREIGN KEY (pedido_id) REFERENCES documentos(id),
    FOREIGN KEY (devolucion_anterior_id) REFERENCES documentos(id),
    FOREIGN KEY (extra_id) REFERENCES documentos(id),
    FOREIGN KEY (devolucion_dia_id) REFERENCES documentos(id)
);

-- Detalle de cada venta
CREATE TABLE venta_detalle (
    id INT AUTO_INCREMENT PRIMARY KEY,
    venta_id INT,
    producto_id INT,
    categoria ENUM('panaderia', 'bizcocheria') NOT NULL,
    subtotal DECIMAL(10,2),
    porcentaje_comision DECIMAL(5,2),
    valor_comision DECIMAL(10,2),
    FOREIGN KEY (venta_id) REFERENCES ventas(id),
    FOREIGN KEY (producto_id) REFERENCES productos(id)
);

-- Tabla de canastas
CREATE TABLE canastas (
    id INT AUTO_INCREMENT PRIMARY KEY,
    codigo_barras VARCHAR(100) NOT NULL UNIQUE,
    estado ENUM('prestada', 'devuelta') DEFAULT 'devuelta'
);

-- Movimientos de canastas
CREATE TABLE movimientos_canastas (
    id INT AUTO_INCREMENT PRIMARY KEY,
    canasta_id INT,
    vendedor_id INT,
    tipo ENUM('prestamo', 'devolucion') NOT NULL,
    fecha DATE NOT NULL,
    FOREIGN KEY (canasta_id) REFERENCES canastas(id),
    FOREIGN KEY (vendedor_id) REFERENCES vendedores(id)
);

-- Tabla de auditoría
CREATE TABLE auditoria (
    id INT AUTO_INCREMENT PRIMARY KEY,
    usuario_id INT,
    tabla_afectada VARCHAR(100),
    registro_id INT,
    cambio TEXT,
    fecha DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
);
"""

# Guardar el script como archivo .sql
output_sql_path = "/mnt/data/sistema_ventas.sql"
with open(output_sql_path, "w") as f:
    f.write(sql_script)

output_sql_path
