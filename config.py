"""
config.py – reads .env and exposes Flask configuration.
"""
import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()


class Config:
    # ------------------------------------------------------------------ #
    # Flask core
    # ------------------------------------------------------------------ #
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")
    DEBUG = os.environ.get("FLASK_DEBUG", "0") == "1"

    # ------------------------------------------------------------------ #
    # Session security
    # ------------------------------------------------------------------ #
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    PERMANENT_SESSION_LIFETIME = timedelta(minutes=30)

    # ------------------------------------------------------------------ #
    # Database
    # ------------------------------------------------------------------ #
    DB_HOST = os.environ.get("DB_HOST", "localhost")
    DB_PORT = int(os.environ.get("DB_PORT", 3306))
    DB_USER = os.environ.get("DB_USER", "evm_user")
    DB_PASSWORD = os.environ.get("DB_PASSWORD", "")
    DB_NAME = os.environ.get("DB_NAME", "digi_evm")

    # ------------------------------------------------------------------ #
    # Uploads
    # ------------------------------------------------------------------ #
    MAX_UPLOAD_MB = int(os.environ.get("MAX_UPLOAD_MB", 2))
    MAX_CONTENT_LENGTH = MAX_UPLOAD_MB * 1024 * 1024
    UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), "app", "static", "uploads")
    ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}

