"""
app/utils/security.py – CSRF helpers, login decorators, upload utilities.
"""
import os
import secrets
from functools import wraps
from flask import session, redirect, url_for, request, abort, current_app
from markupsafe import Markup
from werkzeug.utils import secure_filename


# ------------------------------------------------------------------ #
# CSRF
# ------------------------------------------------------------------ #

def generate_csrf_token() -> str:
    """Return the CSRF token for this session, generating one if needed."""
    if "_csrf_token" not in session:
        session["_csrf_token"] = secrets.token_hex(32)
    return session["_csrf_token"]


def csrf_field() -> Markup:
    """Return a hidden <input> carrying the CSRF token (safe to use in templates)."""
    token = generate_csrf_token()
    return Markup(f'<input type="hidden" name="_csrf_token" value="{token}">')


def validate_csrf():
    """
    Validate the CSRF token on every POST/PUT/PATCH/DELETE request.
    Call this from a before_request hook.  Aborts with 400 on failure.
    """
    if request.method in ("POST", "PUT", "PATCH", "DELETE"):
        token = session.get("_csrf_token")
        form_token = request.form.get("_csrf_token")
        if not token or not form_token or not secrets.compare_digest(token, form_token):
            abort(400)


# ------------------------------------------------------------------ #
# Access-control decorators
# ------------------------------------------------------------------ #

def voter_required(f):
    """Redirect to voter login if no voter is logged in."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get("role") != "voter":
            return redirect(url_for("auth.voter_login"))
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    """Redirect to admin login if no admin is logged in."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get("role") != "admin":
            return redirect(url_for("auth.admin_login"))
        return f(*args, **kwargs)
    return decorated


# ------------------------------------------------------------------ #
# Upload helpers
# ------------------------------------------------------------------ #

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}


def allowed_file(filename: str) -> bool:
    """Return True if the file extension is in the allowed set."""
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS
    )


def save_upload(file_storage, subfolder: str = "") -> str | None:
    """
    Validate, rename, and save an uploaded file.

    Returns the relative path (e.g. ``uploads/ab12_photo.png``) suitable
    for storing in the DB, or None if no file was provided.
    Raises ValueError with a user-friendly message on validation failure.
    """
    if not file_storage or file_storage.filename == "":
        return None

    if not allowed_file(file_storage.filename):
        raise ValueError("Only PNG, JPG, JPEG and WEBP images are allowed.")

    safe_name = secure_filename(file_storage.filename)
    prefix = secrets.token_hex(6)          # 12 random hex chars
    filename = f"{prefix}_{safe_name}"

    upload_dir = current_app.config["UPLOAD_FOLDER"]
    if subfolder:
        upload_dir = os.path.join(upload_dir, subfolder)
    os.makedirs(upload_dir, exist_ok=True)

    file_storage.save(os.path.join(upload_dir, filename))

    # Return path relative to static/ (so url_for('static', filename=...) works)
    rel = os.path.join("uploads", subfolder, filename).replace("\\", "/").lstrip("/")
    return rel


# ------------------------------------------------------------------ #
# Redirect safety
# ------------------------------------------------------------------ #

def safe_next(next_url: str | None) -> str:
    """
    Return *next_url* only if it is a relative path (no scheme/netloc).
    Falls back to '/' to prevent open-redirect attacks.
    """
    if next_url and next_url.startswith("/") and not next_url.startswith("//"):
        return next_url
    return "/"

