from app import create_app, db
app = create_app()              # o como llames a tu factory
with app.app_context():
     db.create_all()

