"""
app/db.py – PyMySQL connector + per-request helpers.

Rules:
- One connection per request, stored on flask.g.
- DictCursor so every row is a dict.
- autocommit=False – callers must use the transaction() context manager.
- Every query uses %s parameters.  No f-strings or string concatenation in SQL.
"""
import pymysql
import pymysql.cursors
from contextlib import contextmanager
from flask import g, current_app


def get_db():
    """Return the PyMySQL connection for the current request, creating it lazily."""
    if "db" not in g:
        cfg = current_app.config
        g.db = pymysql.connect(
            host=cfg["DB_HOST"],
            port=cfg["DB_PORT"],
            user=cfg["DB_USER"],
            password=cfg["DB_PASSWORD"],
            database=cfg["DB_NAME"],
            charset="utf8mb4",
            cursorclass=pymysql.cursors.DictCursor,
            autocommit=False,
        )
    return g.db


def close_db(exc=None):
    """Roll back any uncommitted work and close the connection at request end."""
    db = g.pop("db", None)
    if db is not None:
        try:
            db.rollback()
        except Exception:
            pass
        db.close()


# ------------------------------------------------------------------ #
# Query helpers
# ------------------------------------------------------------------ #

def query_all(sql: str, params=None) -> list:
    """Execute *sql* and return all rows as a list of dicts."""
    db = get_db()
    with db.cursor() as cur:
        cur.execute(sql, params or ())
        return cur.fetchall()


def query_one(sql: str, params=None) -> dict | None:
    """Execute *sql* and return the first row as a dict, or None."""
    db = get_db()
    with db.cursor() as cur:
        cur.execute(sql, params or ())
        return cur.fetchone()


def execute(sql: str, params=None) -> int:
    """Execute an INSERT/UPDATE/DELETE and return lastrowid."""
    db = get_db()
    with db.cursor() as cur:
        cur.execute(sql, params or ())
        return cur.lastrowid


@contextmanager
def transaction():
    """
    Context manager that commits on success and rolls back on any exception.

    Usage::

        with transaction():
            execute(...)
            execute(...)
    """
    db = get_db()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise

