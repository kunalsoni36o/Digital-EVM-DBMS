"""
tests/conftest.py – test fixtures configuring test database and client.
"""
import os
import pytest
from app import create_app
from app.db import get_db, close_db
from scripts.init_db import execute_sql_file, PROJECT_ROOT
import pymysql


class TestConfig:
    TESTING = True
    DEBUG = False
    SECRET_KEY = "test-secret-key-12345"
    DB_HOST = os.environ.get("DB_HOST", "localhost")
    DB_PORT = int(os.environ.get("DB_PORT", 3306))
    DB_USER = os.environ.get("DB_USER", "evm_user")
    DB_PASSWORD = os.environ.get("DB_PASSWORD", "evm_password")
    DB_NAME = "digi_evm_test"
    MAX_UPLOAD_MB = 2
    MAX_CONTENT_LENGTH = 2 * 1024 * 1024
    UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), "uploads")
    ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"


@pytest.fixture(scope="session")
def setup_test_db():
    """Ensure digi_evm_test is freshly initialized from schema.sql and seed.sql."""
    conn = pymysql.connect(
        host=TestConfig.DB_HOST,
        port=TestConfig.DB_PORT,
        user=TestConfig.DB_USER,
        password=TestConfig.DB_PASSWORD,
        autocommit=False,
        charset="utf8mb4",
    )
    try:
        execute_sql_file(conn, PROJECT_ROOT / "database" / "schema.sql", "digi_evm_test")
        execute_sql_file(conn, PROJECT_ROOT / "database" / "seed.sql", "digi_evm_test")
    finally:
        conn.close()


@pytest.fixture
def app(setup_test_db):
    app = create_app(TestConfig)
    return app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def runner(app):
    return app.test_cli_runner()


def get_csrf_token(client):
    """Helper to fetch a valid CSRF token from any page rendering {{ csrf_field() }}."""
    resp = client.get("/login")
    import re
    match = re.search(r'name="_csrf_token"\s+value="([a-f0-9]+)"', resp.get_data(as_text=True))
    if match:
        return match.group(1)
    with client.session_transaction() as sess:
        from app.utils.security import generate_csrf_token
        return generate_csrf_token()

