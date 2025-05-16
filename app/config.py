import os
from dotenv import load_dotenv

# Cargar las variables desde .env
load_dotenv()

class Config:
    # Clave secreta de Flask
    SECRET_KEY = os.getenv("SECRET_KEY", "Incolpan12624+")

    # Debug en modo booleano (1 = True, otro valor = False)
    DEBUG = os.getenv("FLASK_DEBUG", "0") == "1"

    # Configuración de base de datos
    DB_USER = os.getenv("DB_USER", "incolpan")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "Incolpan12624+")
    DB_HOST = os.getenv("DB_HOST", "mysql")  # 🔴 Aquí aseguramos que use el nombre del servicio docker
    DB_PORT = os.getenv("DB_PORT", "3306")
    DB_NAME = os.getenv("DB_NAME", "sistema_ventas")

    # URI para SQLAlchemy
    SQLALCHEMY_DATABASE_URI = (
        f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    )

    # Para evitar warnings de SQLAlchemy
    SQLALCHEMY_TRACK_MODIFICATIONS = False
