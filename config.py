from os import environ, path
import os



class Config:

    # General Flask Config
    SECRET_KEY = b'ergergergergegg/'
    USE_PROXYFIX = True

    APPLICATION_ROOT = '/'

    FLASK_APP = 'app.py'
    FLASK_RUN_HOST = '127.0.0.1'
    FLASK_RUN_PORT = 2101

    FLASK_DEBUG = 1
    FLASK_ENV = "development" # production
    # FLASK_ENV = "production"  # production

    DEBUG = True
    TESTING = False

    SESSION_TYPE = 'sqlalchemy'
    SESSION_SQLALCHEMY_TABLE = 'sessions'
    SESSION_COOKIE_NAME = 'my_cookieGetFace'
    SESSION_PERMANENT = False

    # Database

    SQLALCHEMY_DATABASE_URI = "sqlite:///example.sqlite"  # = 'mysql://username:password@localhost/db_name'

    SQLALCHEMY_ECHO = False
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    CACHE_TYPE = "simple"  # Flask-Caching related configs
    CACHE_DEFAULT_TIMEOUT = 100

    UPLOAD_SECRET = "YouCantSeeMee"
    DELETE_SECRET = "DontDeleteMe"



