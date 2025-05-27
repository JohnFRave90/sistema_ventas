# app/cli/root.py
from flask.cli import with_appcontext
import click
from app import db
from app.models.usuario import Usuario
from werkzeug.security import generate_password_hash

@click.command("crear_root")
@with_appcontext
def crear_root():
    """Crea un superusuario con rol 'root' (oculto)"""
    username = click.prompt("Nombre de usuario", type=str)
    password = click.prompt("Contraseña", hide_input=True, confirmation_prompt=True)

    if Usuario.query.filter_by(nombre_usuario=username).first():
        click.echo("❌ Ya existe un usuario con ese nombre.")
        return

    nuevo_root = Usuario(
        nombre_usuario=username,
        contraseña=generate_password_hash(password),
        rol='root'
    )
    db.session.add(nuevo_root)
    db.session.commit()
    click.echo("✅ Usuario root creado correctamente.")
