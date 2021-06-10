import os
import flask
from celery import Celery
import psycopg2
from urllib.parse import urlparse
from flask_jwt_extended import JWTManager
from datetime import timedelta

def get_db_connection(host, port, name, user, password):
    return psycopg2.connect(
        host=host,
        port=port,
        database=name,
        user=user,
        password=password,
    )

def create_config():
    redash = urlparse(os.getenv('REDASH_DATABASE_URL'))

    config = {
        "GALVANISER_DATABASE": {
            "NAME": "galvanalyser",
            "PORT": 5433,
            "HOST": "galvanalyser_postgres",
            "USER": "postgres",
            "PASSWORD": os.getenv('POSTGRES_PASSWORD'),
        },
        "REDASH_DATABASE": {
            "NAME": redash.path[1:],
            "PORT": redash.port,
            "HOST": redash.hostname,
            "USER": redash.username,
            "PASSWORD": redash.password,
            "URL": os.getenv('REDASH_DATABASE_URL'),
        },
        "DEFAULT_HARVESTER": {
            "NAME": os.getenv("GALVANALYSER_HARVESTER_NAME"),
            "PASSWORD": os.getenv("GALVANALYSER_HARVESTER_PWD"),
            "MACHINE_ID": "server",
            "BASE_PATH": "/usr/data",
            "INSTITUTION": os.getenv("GALVANALYSER_HARVESTER_INSTITUTION"),
        },
        "DEFAULT_USER": {
            "NAME": os.getenv("GALVANALYSER_USER_NAME"),
            "PASSWORD": os.getenv("GALVANALYSER_USER_PWD"),
        },
        "SECRET_KEY": os.getenv("GALVANALYSER_SECRET_KEY"),
    }

    def get_db_connection_for_superuser():
        return get_db_connection(
            config['GALVANISER_DATABASE']['HOST'],
            config['GALVANISER_DATABASE']['PORT'],
            config['GALVANISER_DATABASE']['NAME'],
            config['GALVANISER_DATABASE']['USER'],
            config['GALVANISER_DATABASE']['PASSWORD']
        )

    def get_db_connection_for_user(username, password):
        return get_db_connection(
            config['GALVANISER_DATABASE']['HOST'],
            config['GALVANISER_DATABASE']['PORT'],
            config['GALVANISER_DATABASE']['NAME'],
            username,
            password
        )

    config["GET_DATABASE_CONN_FOR_SUPERUSER"] = get_db_connection_for_superuser
    config["GET_DATABASE_CONN_FOR_USER"] = get_db_connection_for_user

    # flask-jwt-extended
    config["JWT_TOKEN_LOCATION"] = ["headers", "cookies", "json", "query_string"]

    # change to true in production
    config["JWT_COOKIE_SECURE"] = False

    config["JWT_SECRET_KEY"] = config['SECRET_KEY']
    config["JWT_ACCESS_COOKIE_NAME"] = 'access_token_cookie'
    config["JWT_REFRESH_COOKIE_NAME"] = 'refresh_token_cookie'
    config["JWT_COOKIE_DOMAIN"] = None
    config["JWT_COOKIE_SAMESITE"] = None
    config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(hours=1)
    config["JWT_ACCESS_COOKIE_PATH"] = '/'
    config["JWT_REFRESH_COOKIE_PATH"] = '/'
    config["JWT_SESSION_COOKIE"] = True
    config["JWT_COOKIE_CSRF_PROTECT"] = True

    config["JWT_CSRF_IN_COOKIES"] = True

    # celery config
    config['CELERY_BROKER_URL'] = os.getenv('RABBITMQ_URL')
    config['CELERY_RESULT_BACKEND'] = os.getenv('REDIS_URL')

    return config

def make_celery(app):
    celery = Celery(
        app.import_name,
        backend=app.config['CELERY_RESULT_BACKEND'],
        broker=app.config['CELERY_BROKER_URL']
    )
    celery.conf.update(app.config)

    class ContextTask(celery.Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)

    celery.Task = ContextTask
    return celery


def init_app():
    app = flask.Flask(__name__)

    app.config.from_mapping(
        create_config(),
    )

    JWTManager(app)

    celery = make_celery(app)

    # ensure the instance folder exists
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass



    with app.app_context():
        # Import parts of our core Flask app
        from . import routes

    return app

