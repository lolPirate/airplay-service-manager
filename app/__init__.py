from flask import Flask

from .controller import UxPlayController
from .routes import bp


def create_app() -> Flask:
    app = Flask(__name__)
    app.config.from_prefixed_env(prefix="AIRPLAY")

    app.extensions["uxplay_controller"] = UxPlayController()
    app.register_blueprint(bp)

    return app
