## ✅ README.md (copia completa)

# 🥖 Sistema de Ventas – Incolpan

Aplicación web desarrollada en **Flask + MySQL + Bootstrap**, desplegada con **Docker** y protegida por **Cloudflare**.  
Permite gestionar pedidos, extras, devoluciones, vendedores y control administrativo interno.


## 🚀 Características

- Backend en **Python (Flask)** con estructura modular
- Base de datos en **MySQL 8** (contenedorizada)
- Frontend responsive con **Bootstrap 5**
- Panel administrativo por roles
- Control de pedidos diarios
- Soporte para Docker y despliegue en VPS
- Certificado SSL gestionado con Cloudflare (Origin TLS)
- Seguridad por país (solo Colombia)


## 📁 Estructura del proyecto


/sistema\_ventas
├── app/                  # Módulos de la aplicación
├── run.py                # Punto de entrada Flask (usado por Gunicorn)
├── Dockerfile            # Configuración del contenedor Flask
├── docker-compose.yml    # Contenedores web + base de datos
├── requirements.txt      # Dependencias Python
├── .env.example          # Variables de entorno base (sin datos sensibles)
└── README.md


## ⚙️ Requisitos

- Servidor Ubuntu 20.04 o superior
- Docker y Docker Compose
- Puerto 5000 (interno), 80 y 443 (externos)
- Cuenta en [Cloudflare](https://cloudflare.com) (para gestión de DNS y SSL)
- Certificado Origin TLS generado en Cloudflare (modo Full Strict)


## 🔐 Archivo `.env` (ejemplo)

Copia este contenido en un archivo `.env` y ajusta tus credenciales:

FLASK_DEBUG=1
SECRET_KEY=coloca_una_clave_segura

DB_USER=incolpan
DB_PASSWORD=tu_clave_mysql
DB_HOST=mysql
DB_NAME=sistema_ventas
DB_PORT=3306


## 🐳 Despliegue con Docker

1. Clonar el repositorio:


git clone https://github.com/JohnFRave90/sistema_ventas.git
cd sistema_ventas


2. Crear archivo `.env` (basado en `.env.example`)

3. Levantar la aplicación:


docker compose up -d --build


4. Acceder en navegador:


https://ventas.incolpan.com


> Requiere que el subdominio esté configurado en Cloudflare apuntando al VPS



## 🧾 Certificado SSL (Cloudflare Origin)

1. En Cloudflare → SSL/TLS → Origin Server → Create Certificate
2. Pega el `.crt` y `.key` en tu VPS en:


/etc/ssl/cloudflare.crt
/etc/ssl/cloudflare.key


3. Configura tu archivo Nginx:


ssl_certificate     /etc/ssl/cloudflare.crt;
ssl_certificate_key /etc/ssl/cloudflare.key;


## 🔄 Script útil: Actualizar el servidor


#!/bin/bash
cd /srv/sistema_ventas
git pull origin main
docker compose down
docker compose up -d --build


## 🛡️ Seguridad aplicada

* 🔐 Certificado Cloudflare Origin TLS (15 años)
* 🌎 Acceso restringido solo a IPs de **Colombia** (via Cloudflare WAF)
* 🧱 Firewall UFW activo
* 🧠 Monitoreo con [Uptime Kuma](https://github.com/louislam/uptime-kuma)


## 🧠 Mantenimiento recomendado

* Respaldos automáticos de base de datos (`mysqldump`)
* Limpieza mensual de contenedores viejos:


  docker system prune -af

* Monitoreo activo (Uptime Kuma + Telegram)



## 📄 Licencia

Proyecto privado de Incolpan – Todos los derechos reservados.