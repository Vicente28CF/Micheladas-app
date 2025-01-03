# config.py
import os


class Config:
    SECRET_KEY = os.urandom(24)  # Clave secreta para seguridad
