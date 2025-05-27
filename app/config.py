import os
from dotenv import load_dotenv

# Cargar las variables desde .env
load_dotenv()

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "Incolpan12624+")
    DEBUG = os.getenv("FLASK_DEBUG", "0") == "1"

    DB_USER = os.getenv("DB_USER")
    DB_PASSWORD = os.getenv("DB_PASSWORD")
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = os.getenv("DB_PORT", "3306")
    DB_NAME = os.getenv("DB_NAME")

    SQLALCHEMY_DATABASE_URI = (
        f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    )

    SQLALCHEMY_TRACK_MODIFICATIONS = False
