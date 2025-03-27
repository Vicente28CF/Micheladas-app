import os

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'micheladas-secret-key')
    MYSQL_HOST = 'localhost'
    MYSQL_USER = 'root'
    MYSQL_PASSWORD = 'flores28'
    MYSQL_DB = 'negocio_micheladas'
    MYSQL_CURSORCLASS = 'DictCursor'