"""
app/__init__.py – application factory.
"""
import os
from flask import Flask, render_template, session, request
from config import Config
from app.db import close_db


def create_app(config_class=Config):
    app = Flask(__name__, instance_relative_config=False)
    app.config.from_object(config_class)

    # Ensure the upload folder exists
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    # ------------------------------------------------------------------ #
    # Teardown: close DB connection after every request
    # ------------------------------------------------------------------ #
    app.teardown_appcontext(close_db)

    # ------------------------------------------------------------------ #
    # Security headers on every response
    # ------------------------------------------------------------------ #
    @app.after_request
    def set_security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        return response

    # ------------------------------------------------------------------ #
    # Jinja globals
    # ------------------------------------------------------------------ #
    from app.utils.security import csrf_field, generate_csrf_token
    app.jinja_env.globals["csrf_field"] = csrf_field
    app.jinja_env.globals["csrf_token"] = generate_csrf_token

    # ------------------------------------------------------------------ #
    # Register blueprints
    # ------------------------------------------------------------------ #
    from app.blueprints.public import public_bp
    from app.blueprints.auth import auth_bp
    from app.blueprints.voter import voter_bp
    from app.blueprints.admin import admin_bp

    app.register_blueprint(public_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(voter_bp, url_prefix="/voter")
    app.register_blueprint(admin_bp, url_prefix="/admin")

    # ------------------------------------------------------------------ #
    # Error handlers
    # ------------------------------------------------------------------ #
    @app.errorhandler(404)
    def not_found(e):
        return render_template("public/404.html"), 404

    @app.errorhandler(500)
    def server_error(e):
        return render_template("public/500.html"), 500

    @app.errorhandler(400)
    def bad_request(e):
        return render_template("public/400.html"), 400

    return app

