from flask import Flask


def create_app() -> Flask:
    app = Flask(__name__)

    from .routes import api

    app.register_blueprint(api)
    return app