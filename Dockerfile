# Imagen base liviana de Python

FROM python:3.11-slim


# Configura la zona horaria a Colombia

ENV TZ=America/Bogota

RUN apt-get update && apt-get install -y tzdata && \

    ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone && \

    dpkg-reconfigure -f noninteractive tzdata && \

    apt-get clean && rm -rf /var/lib/apt/lists/*


# Establece el directorio de trabajo dentro del contenedor

WORKDIR /app


# Copia los archivos del proyecto al contenedor

COPY . /app


# Instala las dependencias

RUN pip install --no-cache-dir -r requirements.txt


# Expone el puerto 5000 para Flask/Gunicorn

EXPOSE 5000


# Ejecuta la app usando Gunicorn con 4 workers

CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "run:app"]


# Verificación de salud del contenedor

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \

  CMD curl -f http://localhost:5000 || exit 1