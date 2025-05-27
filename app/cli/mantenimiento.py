# app/cli/mantenimiento.py
import click
from flask.cli import with_appcontext
from app import db
from sqlalchemy import text

@click.command("borrar_movimientos_canastas")
@with_appcontext
def borrar_movimientos_canastas():
    """Borra todos los movimientos de canastas y actualiza su estado a Disponible"""
    if not click.confirm("¿Estás seguro de que deseas borrar TODOS los movimientos de canastas?", default=False):
        click.echo("❌ Operación cancelada.")
        return

    try:
        db.session.execute(text('DELETE FROM movimientos'))
        db.session.execute(text('UPDATE canastas SET actualidad = "Disponible"'))
        db.session.commit()
        click.echo("✅ Movimientos borrados y canastas actualizadas a 'Disponible'.")
    except Exception as e:
        db.session.rollback()
        click.echo(f"❌ Error al borrar movimientos: {e}")

@click.command("borrar_canastas_total")
@with_appcontext
def borrar_canastas_total():
    """Elimina todas las canastas del sistema"""
    if not click.confirm("¿Estás seguro de que deseas ELIMINAR TODAS las canastas?", default=False):
        click.echo("❌ Operación cancelada.")
        return

    try:
        db.session.execute(text('DELETE FROM canastas'))
        db.session.commit()
        click.echo("✅ Todas las canastas han sido eliminadas.")
    except Exception as e:
        db.session.rollback()
        click.echo(f"❌ Error al borrar canastas: {e}")
