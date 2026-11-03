"""
app/blueprints/auth.py – voter and admin authentication.

Routes
------
GET/POST  /register       Voter self-registration
GET/POST  /login          Voter login
POST      /logout         Voter logout
GET/POST  /admin/login    Admin login
POST      /admin/logout   Admin logout
"""
from datetime import datetime, timedelta
from flask import (
    Blueprint, render_template, request, redirect,
    url_for, flash, session,
)
from werkzeug.security import generate_password_hash, check_password_hash

from app.db import query_all, query_one, execute, transaction
from app.utils.security import validate_csrf
from app.utils.validators import validate_epic, validate_age, validate_password
from app.services import audit_service

auth_bp = Blueprint("auth", __name__)

# Maximum failed login attempts before a temporary lockout
MAX_ATTEMPTS = 5
LOCKOUT_MINUTES = 15


@auth_bp.before_request
def _csrf_check():
    validate_csrf()


# ------------------------------------------------------------------ #
# Voter registration
# ------------------------------------------------------------------ #

@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    constituencies = query_all("SELECT constituency_id, name, state FROM constituencies ORDER BY name")

    if request.method == "POST":
        # Collect form fields
        epic_raw      = request.form.get("epic_no", "")
        full_name     = request.form.get("full_name", "").strip()
        dob_str       = request.form.get("dob", "")
        gender        = request.form.get("gender", "")
        email         = request.form.get("email", "").strip().lower()
        phone         = request.form.get("phone", "").strip() or None
        constituency  = request.form.get("constituency_id", "")
        password      = request.form.get("password", "")
        confirm_pw    = request.form.get("confirm_password", "")

        # ---- Validate -------------------------------------------------- #
        errors = []

        try:
            epic_no = validate_epic(epic_raw)
        except ValueError as exc:
            errors.append(str(exc))
            epic_no = epic_raw

        if not full_name:
            errors.append("Full name is required.")

        dob = None
        try:
            dob = datetime.strptime(dob_str, "%Y-%m-%d").date()
            validate_age(dob)
        except ValueError as exc:
            errors.append(str(exc) if "old" in str(exc) else "Please enter a valid date of birth.")

        if gender not in ("male", "female", "other"):
            errors.append("Please select a valid gender.")

        if not email or "@" not in email:
            errors.append("Please enter a valid email address.")

        if not constituency.isdigit():
            errors.append("Please select a constituency.")

        try:
            validate_password(password)
        except ValueError as exc:
            errors.append(str(exc))

        if password != confirm_pw:
            errors.append("Passwords do not match.")

        if errors:
            for e in errors:
                flash(e, "error")
            return render_template("auth/register.html", constituencies=constituencies)

        # ---- Persist --------------------------------------------------- #
        pw_hash = generate_password_hash(password)
        try:
            with transaction():
                voter_id = execute(
                    """
                    INSERT INTO voters
                        (epic_no, full_name, dob, gender, email, phone,
                         password_hash, constituency_id, status)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'pending')
                    """,
                    (epic_no, full_name, dob, gender, email, phone, pw_hash, int(constituency)),
                )
                audit_service.log(
                    actor_type="voter",
                    actor_id=voter_id,
                    action="voter_registered",
                    entity="voter",
                    entity_id=voter_id,
                )
        except Exception as exc:
            import pymysql
            if isinstance(exc, pymysql.err.IntegrityError) and exc.args[0] == 1062:
                flash("An account with that EPIC number or email already exists.", "error")
            else:
                flash("Registration failed due to a database error. Please try again.", "error")
            return render_template("auth/register.html", constituencies=constituencies)

        flash(
            "Registration successful! An administrator must approve your account before you can log in.",
            "success",
        )
        return redirect(url_for("auth.voter_login"))

    return render_template("auth/register.html", constituencies=constituencies)


# ------------------------------------------------------------------ #
# Voter login
# ------------------------------------------------------------------ #

@auth_bp.route("/login", methods=["GET", "POST"])
def voter_login():
    if session.get("role") == "voter":
        return redirect(url_for("voter.dashboard"))

    if request.method == "POST":
        epic_raw = request.form.get("epic_no", "").strip().upper()
        password = request.form.get("password", "")

        # Generic message to avoid EPIC enumeration
        INVALID_MSG = "Invalid EPIC number or password."

        # Fetch voter (always fetch to run check_password_hash even on miss)
        voter = query_one(
            "SELECT * FROM voters WHERE epic_no = %s",
            (epic_raw,),
        )

        # If account is locked
        if voter and voter["locked_until"] and datetime.now() < voter["locked_until"]:
            flash("Your account is temporarily locked due to too many failed attempts. Try again in 15 minutes.", "error")
            return render_template("auth/voter_login.html")

        # Verify password (always call to prevent timing attacks)
        pw_ok = voter and check_password_hash(voter["password_hash"], password)

        if not pw_ok:
            if voter:
                # Increment failed attempts
                new_attempts = voter["failed_attempts"] + 1
                if new_attempts >= MAX_ATTEMPTS:
                    locked_until = datetime.now() + timedelta(minutes=LOCKOUT_MINUTES)
                    execute(
                        "UPDATE voters SET failed_attempts = %s, locked_until = %s WHERE voter_id = %s",
                        (new_attempts, locked_until, voter["voter_id"]),
                    )
                    from app.db import get_db; get_db().commit()
                    flash("Too many failed attempts. Your account is locked for 15 minutes.", "error")
                else:
                    execute(
                        "UPDATE voters SET failed_attempts = %s WHERE voter_id = %s",
                        (new_attempts, voter["voter_id"]),
                    )
                    from app.db import get_db; get_db().commit()
            flash(INVALID_MSG, "error")
            return render_template("auth/voter_login.html")

        # Password matched – now check status
        status = voter["status"]
        if status == "pending":
            flash("Your account is pending admin approval. Please check back later.", "warning")
            return render_template("auth/voter_login.html")
        if status == "rejected":
            flash("Your account registration was rejected. Please contact support.", "error")
            return render_template("auth/voter_login.html")
        if status == "blocked":
            flash("Your account has been blocked. Please contact support.", "error")
            return render_template("auth/voter_login.html")
        if status != "approved":
            flash(INVALID_MSG, "error")
            return render_template("auth/voter_login.html")

        # Reset failed attempts and create session
        execute(
            "UPDATE voters SET failed_attempts = 0, locked_until = NULL WHERE voter_id = %s",
            (voter["voter_id"],),
        )
        from app.db import get_db; get_db().commit()

        session.clear()
        session.regenerate() if hasattr(session, "regenerate") else None
        session["user_id"] = voter["voter_id"]
        session["role"] = "voter"
        session.permanent = True

        audit_service.log(
            actor_type="voter",
            actor_id=voter["voter_id"],
            action="voter_login",
            entity="voter",
            entity_id=voter["voter_id"],
        )
        from app.db import get_db; get_db().commit()

        return redirect(url_for("voter.dashboard"))

    return render_template("auth/voter_login.html")


# ------------------------------------------------------------------ #
# Voter logout
# ------------------------------------------------------------------ #

@auth_bp.route("/logout", methods=["POST"])
def voter_logout():
    voter_id = session.get("user_id")
    session.clear()
    if voter_id:
        audit_service.log(
            actor_type="voter",
            actor_id=voter_id,
            action="voter_logout",
            entity="voter",
            entity_id=voter_id,
        )
        from app.db import get_db; get_db().commit()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.voter_login"))


# ------------------------------------------------------------------ #
# Admin login
# ------------------------------------------------------------------ #

@auth_bp.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if session.get("role") == "admin":
        return redirect(url_for("admin.dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        admin = query_one(
            "SELECT * FROM admins WHERE username = %s AND is_active = 1",
            (username,),
        )

        if not admin or not check_password_hash(admin["password_hash"], password):
            flash("Invalid username or password.", "error")
            return render_template("auth/admin_login.html")

        session.clear()
        session["user_id"] = admin["admin_id"]
        session["role"] = "admin"
        session.permanent = True

        audit_service.log(
            actor_type="admin",
            actor_id=admin["admin_id"],
            action="admin_login",
            entity="admin",
            entity_id=admin["admin_id"],
        )
        from app.db import get_db; get_db().commit()

        return redirect(url_for("admin.dashboard"))

    return render_template("auth/admin_login.html")


# ------------------------------------------------------------------ #
# Admin logout
# ------------------------------------------------------------------ #

@auth_bp.route("/admin/logout", methods=["POST"])
def admin_logout():
    admin_id = session.get("user_id")
    session.clear()
    if admin_id:
        audit_service.log(
            actor_type="admin",
            actor_id=admin_id,
            action="admin_logout",
            entity="admin",
            entity_id=admin_id,
        )
        from app.db import get_db; get_db().commit()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.admin_login"))

