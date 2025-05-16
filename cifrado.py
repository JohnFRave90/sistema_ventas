from app import create_app, db
from app.models.usuario import Usuario
from werkzeug.security import generate_password_hash

app = create_app()

with app.app_context():
    usuarios = Usuario.query.all()
    for u in usuarios:
        # Solo si no es hash (detectar si no contiene pbkdf2)
        if not u.contraseña.startswith("pbkdf2:"):
            print(f"Actualizando {u.nombre_usuario}")
            u.contraseña = generate_password_hash(u.contraseña)
    db.session.commit()
    print("✅ Todas las contraseñas fueron actualizadas.")

