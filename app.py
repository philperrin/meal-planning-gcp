"""
Flask Application Factory & Entry Point for the Meal Planning Assistant.
Runs on Google Cloud Run with Gunicorn WSGI.
"""

import os
import logging
from flask import Flask

from config import Config
from routes.views import views_bp
from routes.api import api_bp

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

def create_app() -> Flask:
    """Creates and configures the Flask application."""
    app = Flask(
        __name__,
        static_folder="static",
        template_folder="templates"
    )

    app.config.from_object(Config)
    app.secret_key = Config.SECRET_KEY

    # Register Blueprints
    app.register_blueprint(views_bp)
    app.register_blueprint(api_bp)

    # Enable ProxyFix to correctly handle HTTPS behind Cloud Run's reverse proxy
    from werkzeug.middleware.proxy_fix import ProxyFix
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

    logger.info(f"Initialized Meal Planning Assistant (Project: {Config.PROJECT_ID})")
    return app

app = create_app()

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=Config.DEBUG)
