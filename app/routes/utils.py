from flask_login import UserMixin
from flask import redirect, url_for, flash
from flask_login import current_user
from functools import wraps

class UserWrapper(UserMixin):
    def __init__(self, user, tipo):
        self.user = user
        self.tipo = tipo  # "usuario" o "vendedor"
        self.id = f"{tipo}:{user.id}"  

    def get_id(self):
        return self.id

    @property
    def rol(self):
        return self.user.rol

    @property
    def nombre_usuario(self):
        return self.user.nombre_usuario
