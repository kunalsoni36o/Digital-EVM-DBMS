"""
app/blueprints/admin.py – admin area.

All routes require @admin_required.
All POST actions are CSRF-protected via the before_request hook.
"""
from flask import (
    Blueprint, render_template, request, redirect,
    url_for, flash, session,
)
from datetime import datetime

import pymysql

from app.db import query_all, query_one, execute, transaction
from app.services.election_service import sync_statuses
from app.services import audit_service
from app.utils.security import admin_required, validate_csrf, save_upload

admin_bp = Blueprint("admin", __name__)

AUDIT_PAGE_SIZE = 25


@admin_bp.before_request
def _before():
    validate_csrf()
    sync_statuses()


# ================================================================== #
# Dashboard
# ================================================================== #

@admin_bp.route("/")
@admin_required
def dashboard():
    voter_counts = query_one(
        """
        SELECT
            SUM(status='pending')  AS pending,
            SUM(status='approved') AS approved,
            SUM(status='rejected') AS rejected,
            SUM(status='blocked')  AS blocked
        FROM voters
        """,
    )
    election_counts = query_one(
        """
        SELECT
            SUM(status='draft')     AS draft,
            SUM(status='scheduled') AS scheduled,
            SUM(status='active')    AS active,
            SUM(status='closed')    AS closed
        FROM elections
        """,
    )
    total_votes = query_one("SELECT COUNT(*) AS cnt FROM votes")
    recent_audit = query_all(
        "SELECT * FROM audit_logs ORDER BY log_id DESC LIMIT 10",
    )
    return render_template(
        "admin/dashboard.html",
        voter_counts=voter_counts,
        election_counts=election_counts,
        total_votes=total_votes["cnt"],
        recent_audit=recent_audit,
    )


# ================================================================== #
# Voters
# ================================================================== #

@admin_bp.route("/voters")
@admin_required
def voters():
    status_filter = request.args.get("status", "")
    search = request.args.get("q", "").strip()

    sql = "SELECT v.*, c.name AS constituency_name FROM voters v JOIN constituencies c ON c.constituency_id = v.constituency_id WHERE 1=1"
    params = []

    if status_filter:
        sql += " AND v.status = %s"
        params.append(status_filter)
    if search:
        sql += " AND (v.epic_no LIKE %s OR v.full_name LIKE %s)"
        like = f"%{search}%"
        params.extend([like, like])

    sql += " ORDER BY v.created_at DESC"
    voters_list = query_all(sql, params)

    return render_template("admin/voters.html", voters=voters_list, status_filter=status_filter, search=search)


@admin_bp.route("/voters/<int:voter_id>/action", methods=["POST"])
@admin_required
def voter_action(voter_id: int):
    action = request.form.get("action", "")
    admin_id = session["user_id"]

    allowed = {"approve", "reject", "block", "unblock"}
    if action not in allowed:
        flash("Invalid action.", "error")
        return redirect(url_for("admin.voters"))

    voter = query_one("SELECT * FROM voters WHERE voter_id = %s", (voter_id,))
    if not voter:
        flash("Voter not found.", "error")
        return redirect(url_for("admin.voters"))

    if action == "approve":
        with transaction():
            execute(
                "UPDATE voters SET status='approved', approved_by=%s, approved_at=NOW() WHERE voter_id=%s",
                (admin_id, voter_id),
            )
            audit_service.log("admin", admin_id, "voter_approved", "voter", voter_id, voter["epic_no"])
    elif action == "reject":
        with transaction():
            execute("UPDATE voters SET status='rejected' WHERE voter_id=%s", (voter_id,))
            audit_service.log("admin", admin_id, "voter_rejected", "voter", voter_id, voter["epic_no"])
    elif action == "block":
        with transaction():
            execute("UPDATE voters SET status='blocked' WHERE voter_id=%s", (voter_id,))
            audit_service.log("admin", admin_id, "voter_blocked", "voter", voter_id, voter["epic_no"])
    elif action == "unblock":
        with transaction():
            execute("UPDATE voters SET status='approved', failed_attempts=0, locked_until=NULL WHERE voter_id=%s", (voter_id,))
            audit_service.log("admin", admin_id, "voter_unblocked", "voter", voter_id, voter["epic_no"])

    flash(f"Voter {action}d successfully.", "success")
    return redirect(url_for("admin.voters"))


# ================================================================== #
# Constituencies
# ================================================================== #

@admin_bp.route("/constituencies")
@admin_required
def constituencies():
    rows = query_all("SELECT * FROM constituencies ORDER BY name")
    return render_template("admin/constituencies.html", constituencies=rows)


@admin_bp.route("/constituencies/add", methods=["POST"])
@admin_required
def constituency_add():
    code  = request.form.get("code", "").strip().upper()
    name  = request.form.get("name", "").strip()
    state = request.form.get("state", "").strip()
    if not (code and name and state):
        flash("All fields are required.", "error")
        return redirect(url_for("admin.constituencies"))
    try:
        with transaction():
            cid = execute(
                "INSERT INTO constituencies (code, name, state) VALUES (%s, %s, %s)",
                (code, name, state),
            )
            audit_service.log("admin", session["user_id"], "constituency_added", "constituency", cid, name)
        flash("Constituency added.", "success")
    except pymysql.err.IntegrityError:
        flash("A constituency with that code or name already exists.", "error")
    return redirect(url_for("admin.constituencies"))


@admin_bp.route("/constituencies/<int:cid>/edit", methods=["POST"])
@admin_required
def constituency_edit(cid: int):
    name  = request.form.get("name", "").strip()
    state = request.form.get("state", "").strip()
    if not (name and state):
        flash("Name and state are required.", "error")
        return redirect(url_for("admin.constituencies"))
    try:
        with transaction():
            execute("UPDATE constituencies SET name=%s, state=%s WHERE constituency_id=%s", (name, state, cid))
            audit_service.log("admin", session["user_id"], "constituency_edited", "constituency", cid, name)
        flash("Constituency updated.", "success")
    except pymysql.err.IntegrityError:
        flash("A constituency with that name already exists.", "error")
    return redirect(url_for("admin.constituencies"))


@admin_bp.route("/constituencies/<int:cid>/delete", methods=["POST"])
@admin_required
def constituency_delete(cid: int):
    # Refuse if voters or candidates reference it
    in_use = query_one(
        "SELECT 1 FROM voters WHERE constituency_id=%s LIMIT 1", (cid,)
    ) or query_one(
        "SELECT 1 FROM candidates WHERE constituency_id=%s LIMIT 1", (cid,)
    )
    if in_use:
        flash("Cannot delete: voters or candidates are linked to this constituency.", "error")
        return redirect(url_for("admin.constituencies"))
    with transaction():
        execute("DELETE FROM constituencies WHERE constituency_id=%s", (cid,))
        audit_service.log("admin", session["user_id"], "constituency_deleted", "constituency", cid)
    flash("Constituency deleted.", "success")
    return redirect(url_for("admin.constituencies"))


# ================================================================== #
# Parties
# ================================================================== #

@admin_bp.route("/parties")
@admin_required
def parties():
    rows = query_all("SELECT * FROM parties ORDER BY name")
    return render_template("admin/parties.html", parties=rows)


@admin_bp.route("/parties/add", methods=["POST"])
@admin_required
def party_add():
    name       = request.form.get("name", "").strip()
    short_name = request.form.get("short_name", "").strip().upper()
    symbol     = request.form.get("symbol", "").strip() or None
    logo_path  = None

    if not (name and short_name):
        flash("Name and short name are required.", "error")
        return redirect(url_for("admin.parties"))

    try:
        logo_path = save_upload(request.files.get("logo"), subfolder="logos")
    except ValueError as exc:
        flash(str(exc), "error")
        return redirect(url_for("admin.parties"))

    try:
        with transaction():
            pid = execute(
                "INSERT INTO parties (name, short_name, symbol, logo_path) VALUES (%s,%s,%s,%s)",
                (name, short_name, symbol, logo_path),
            )
            audit_service.log("admin", session["user_id"], "party_added", "party", pid, name)
        flash("Party added.", "success")
    except pymysql.err.IntegrityError:
        flash("A party with that name or short name already exists.", "error")
    return redirect(url_for("admin.parties"))


@admin_bp.route("/parties/<int:pid>/edit", methods=["POST"])
@admin_required
def party_edit(pid: int):
    name       = request.form.get("name", "").strip()
    short_name = request.form.get("short_name", "").strip().upper()
    symbol     = request.form.get("symbol", "").strip() or None
    logo_path  = None

    try:
        logo_path = save_upload(request.files.get("logo"), subfolder="logos")
    except ValueError as exc:
        flash(str(exc), "error")
        return redirect(url_for("admin.parties"))

    update_sql = "UPDATE parties SET name=%s, short_name=%s, symbol=%s"
    params = [name, short_name, symbol]
    if logo_path:
        update_sql += ", logo_path=%s"
        params.append(logo_path)
    update_sql += " WHERE party_id=%s"
    params.append(pid)

    try:
        with transaction():
            execute(update_sql, params)
            audit_service.log("admin", session["user_id"], "party_edited", "party", pid, name)
        flash("Party updated.", "success")
    except pymysql.err.IntegrityError:
        flash("A party with that name or short name already exists.", "error")
    return redirect(url_for("admin.parties"))


@admin_bp.route("/parties/<int:pid>/delete", methods=["POST"])
@admin_required
def party_delete(pid: int):
    with transaction():
        execute("DELETE FROM parties WHERE party_id=%s", (pid,))
        audit_service.log("admin", session["user_id"], "party_deleted", "party", pid)
    flash("Party deleted.", "success")
    return redirect(url_for("admin.parties"))


# ================================================================== #
# Elections
# ================================================================== #

@admin_bp.route("/elections")
@admin_required
def elections():
    rows = query_all("SELECT * FROM elections ORDER BY created_at DESC")
    return render_template("admin/elections.html", elections=rows)


@admin_bp.route("/elections/new", methods=["GET", "POST"])
@admin_required
def election_new():
    if request.method == "POST":
        title       = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip() or None
        start_str   = request.form.get("start_time", "")
        end_str     = request.form.get("end_time", "")

        errors = []
        start_time = end_time = None
        if not title:
            errors.append("Title is required.")
        try:
            start_time = datetime.strptime(start_str, "%Y-%m-%dT%H:%M")
        except ValueError:
            errors.append("Invalid start time.")
        try:
            end_time = datetime.strptime(end_str, "%Y-%m-%dT%H:%M")
        except ValueError:
            errors.append("Invalid end time.")
        if start_time and end_time and end_time <= start_time:
            errors.append("End time must be after start time.")

        if errors:
            for e in errors: flash(e, "error")
            return render_template("admin/election_form.html", election=None)

        with transaction():
            eid = execute(
                "INSERT INTO elections (title, description, start_time, end_time, created_by) VALUES (%s,%s,%s,%s,%s)",
                (title, description, start_time, end_time, session["user_id"]),
            )
            audit_service.log("admin", session["user_id"], "election_created", "election", eid, title)
        flash("Election created.", "success")
        return redirect(url_for("admin.election_detail", election_id=eid))

    return render_template("admin/election_form.html", election=None)


@admin_bp.route("/elections/<int:election_id>")
@admin_required
def election_detail(election_id: int):
    election = query_one("SELECT * FROM elections WHERE election_id=%s", (election_id,))
    if not election:
        flash("Election not found.", "error")
        return redirect(url_for("admin.elections"))

    candidates = query_all(
        """
        SELECT c.*, k.name AS constituency_name,
               COALESCE(p.name,'Independent') AS party_name
        FROM candidates c
        JOIN constituencies k ON k.constituency_id = c.constituency_id
        LEFT JOIN parties p ON p.party_id = c.party_id
        WHERE c.election_id = %s
        ORDER BY k.name, c.full_name
        """,
        (election_id,),
    )

    # Group by constituency
    grouped = {}
    for cand in candidates:
        cid = cand["constituency_id"]
        grouped.setdefault(cid, {"name": cand["constituency_name"], "candidates": []})
        grouped[cid]["candidates"].append(cand)

    return render_template(
        "admin/election_detail.html",
        election=election,
        grouped=grouped,
    )


@admin_bp.route("/elections/<int:election_id>/edit", methods=["GET", "POST"])
@admin_required
def election_edit(election_id: int):
    election = query_one("SELECT * FROM elections WHERE election_id=%s AND status='draft'", (election_id,))
    if not election:
        flash("Election not found or not in draft status.", "error")
        return redirect(url_for("admin.elections"))

    if request.method == "POST":
        title       = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip() or None
        start_str   = request.form.get("start_time", "")
        end_str     = request.form.get("end_time", "")

        errors = []
        start_time = end_time = None
        if not title:
            errors.append("Title is required.")
        try:
            start_time = datetime.strptime(start_str, "%Y-%m-%dT%H:%M")
        except ValueError:
            errors.append("Invalid start time.")
        try:
            end_time = datetime.strptime(end_str, "%Y-%m-%dT%H:%M")
        except ValueError:
            errors.append("Invalid end time.")
        if start_time and end_time and end_time <= start_time:
            errors.append("End time must be after start time.")

        if errors:
            for e in errors: flash(e, "error")
            return render_template("admin/election_form.html", election=election)

        with transaction():
            execute(
                "UPDATE elections SET title=%s, description=%s, start_time=%s, end_time=%s WHERE election_id=%s",
                (title, description, start_time, end_time, election_id),
            )
            audit_service.log("admin", session["user_id"], "election_edited", "election", election_id, title)
        flash("Election updated.", "success")
        return redirect(url_for("admin.election_detail", election_id=election_id))

    return render_template("admin/election_form.html", election=election)


@admin_bp.route("/elections/<int:election_id>/status", methods=["POST"])
@admin_required
def election_status(election_id: int):
    """Handle manual status transitions."""
    new_status = request.form.get("new_status", "")
    admin_id   = session["user_id"]

    election = query_one("SELECT * FROM elections WHERE election_id=%s", (election_id,))
    if not election:
        flash("Election not found.", "error")
        return redirect(url_for("admin.elections"))

    current = election["status"]
    valid_transitions = {
        "draft": "scheduled",
        "scheduled": "active",
        "active": "closed",
    }

    if valid_transitions.get(current) != new_status:
        flash(f"Invalid status transition from '{current}' to '{new_status}'.", "error")
        return redirect(url_for("admin.election_detail", election_id=election_id))

    # Extra check: draft -> scheduled requires >= 2 candidates in >= 1 constituency
    if current == "draft" and new_status == "scheduled":
        cand_check = query_one(
            """
            SELECT COUNT(*) AS cnt FROM (
                SELECT constituency_id
                FROM candidates
                WHERE election_id = %s
                GROUP BY constituency_id
                HAVING COUNT(*) >= 2
            ) sub
            """,
            (election_id,),
        )
        if not cand_check or cand_check["cnt"] == 0:
            flash("Cannot schedule: at least one constituency must have 2 or more candidates.", "error")
            return redirect(url_for("admin.election_detail", election_id=election_id))

    with transaction():
        execute(
            "UPDATE elections SET status=%s WHERE election_id=%s",
            (new_status, election_id),
        )
        audit_service.log(
            "admin", admin_id, f"election_{new_status}",
            "election", election_id, election["title"],
        )

    flash(f"Election status changed to '{new_status}'.", "success")
    return redirect(url_for("admin.election_detail", election_id=election_id))


@admin_bp.route("/elections/<int:election_id>/publish", methods=["POST"])
@admin_required
def election_publish(election_id: int):
    election = query_one("SELECT * FROM elections WHERE election_id=%s", (election_id,))
    if not election or election["status"] != "closed":
        flash("Results can only be published for closed elections.", "error")
        return redirect(url_for("admin.election_detail", election_id=election_id))

    with transaction():
        execute(
            "UPDATE elections SET results_published=1 WHERE election_id=%s",
            (election_id,),
        )
        audit_service.log(
            "admin", session["user_id"], "results_published",
            "election", election_id, election["title"],
        )
    flash("Results published successfully.", "success")
    return redirect(url_for("admin.election_detail", election_id=election_id))


# ================================================================== #
# Candidates
# ================================================================== #

@admin_bp.route("/elections/<int:election_id>/candidates/add", methods=["GET", "POST"])
@admin_required
def candidate_add(election_id: int):
    election = query_one("SELECT * FROM elections WHERE election_id=%s AND status='draft'", (election_id,))
    if not election:
        flash("Candidates can only be added to draft elections.", "error")
        return redirect(url_for("admin.election_detail", election_id=election_id))

    constituencies = query_all("SELECT constituency_id, name FROM constituencies ORDER BY name")
    parties        = query_all("SELECT party_id, name FROM parties ORDER BY name")

    if request.method == "POST":
        full_name       = request.form.get("full_name", "").strip()
        constituency_id = request.form.get("constituency_id", "")
        party_id_raw    = request.form.get("party_id", "").strip()
        party_id        = int(party_id_raw) if party_id_raw.isdigit() else None
        photo_path      = None

        if not full_name or not constituency_id.isdigit():
            flash("Full name and constituency are required.", "error")
            return render_template(
                "admin/candidate_form.html",
                election=election,
                constituencies=constituencies,
                parties=parties,
            )

        try:
            photo_path = save_upload(request.files.get("photo"), subfolder="candidates")
        except ValueError as exc:
            flash(str(exc), "error")
            return render_template(
                "admin/candidate_form.html",
                election=election,
                constituencies=constituencies,
                parties=parties,
            )

        try:
            with transaction():
                cid = execute(
                    """
                    INSERT INTO candidates
                        (election_id, constituency_id, party_id, full_name, photo_path)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (election_id, int(constituency_id), party_id, full_name, photo_path),
                )
                audit_service.log(
                    "admin", session["user_id"], "candidate_added",
                    "candidate", cid, f"{full_name} (election {election_id})",
                )
            flash("Candidate added.", "success")
            return redirect(url_for("admin.election_detail", election_id=election_id))
        except pymysql.err.IntegrityError as exc:
            if exc.args[0] == 1062:
                flash("A candidate with that name already exists in this constituency/election.", "error")
            else:
                flash(f"Database error: {exc.args[1]}", "error")
        except pymysql.err.OperationalError as exc:
            # Catch trigger signal (election not draft)
            flash(str(exc.args[1]) if len(exc.args) > 1 else "Database error.", "error")

    return render_template(
        "admin/candidate_form.html",
        election=election,
        constituencies=constituencies,
        parties=parties,
    )


@admin_bp.route("/elections/<int:election_id>/candidates/<int:candidate_id>/delete", methods=["POST"])
@admin_required
def candidate_delete(election_id: int, candidate_id: int):
    election = query_one("SELECT status FROM elections WHERE election_id=%s", (election_id,))
    if not election or election["status"] != "draft":
        flash("Candidates can only be deleted from draft elections.", "error")
        return redirect(url_for("admin.election_detail", election_id=election_id))

    with transaction():
        execute("DELETE FROM candidates WHERE candidate_id=%s AND election_id=%s", (candidate_id, election_id))
        audit_service.log(
            "admin", session["user_id"], "candidate_deleted",
            "candidate", candidate_id, f"election {election_id}",
        )
    flash("Candidate deleted.", "success")
    return redirect(url_for("admin.election_detail", election_id=election_id))


# ================================================================== #
# Live tally
# ================================================================== #

@admin_bp.route("/elections/<int:election_id>/tally")
@admin_required
def tally(election_id: int):
    election = query_one("SELECT * FROM elections WHERE election_id=%s", (election_id,))
    if not election:
        flash("Election not found.", "error")
        return redirect(url_for("admin.elections"))

    tally_rows = query_all(
        """
        SELECT t.constituency_id, k.name AS constituency_name,
               t.candidate_name, t.party, t.votes
        FROM v_candidate_tally t
        JOIN constituencies k ON k.constituency_id = t.constituency_id
        WHERE t.election_id = %s
        ORDER BY t.constituency_id, t.votes DESC
        """,
        (election_id,),
    )

    nota_rows = query_all(
        """
        SELECT n.constituency_id, k.name AS constituency_name, n.nota_votes
        FROM v_nota_tally n
        JOIN constituencies k ON k.constituency_id = n.constituency_id
        WHERE n.election_id = %s
        """,
        (election_id,),
    )
    nota_map = {r["constituency_id"]: r["nota_votes"] for r in nota_rows}

    turnout = query_one("SELECT * FROM v_turnout WHERE election_id=%s", (election_id,))

    # Group by constituency
    grouped = {}
    for row in tally_rows:
        cid = row["constituency_id"]
        grouped.setdefault(cid, {"name": row["constituency_name"], "candidates": [], "nota_votes": nota_map.get(cid, 0)})
        grouped[cid]["candidates"].append(row)

    return render_template(
        "admin/tally.html",
        election=election,
        grouped=grouped,
        turnout=turnout,
    )


# ================================================================== #
# Audit log
# ================================================================== #

@admin_bp.route("/audit")
@admin_required
def audit_log():
    page       = max(1, int(request.args.get("page", 1)))
    actor_type = request.args.get("actor_type", "")
    offset     = (page - 1) * AUDIT_PAGE_SIZE

    sql    = "SELECT * FROM audit_logs WHERE 1=1"
    params = []
    if actor_type:
        sql += " AND actor_type = %s"
        params.append(actor_type)
    sql += " ORDER BY log_id DESC LIMIT %s OFFSET %s"
    params.extend([AUDIT_PAGE_SIZE, offset])

    logs = query_all(sql, params)

    # Total count for pagination
    count_sql    = "SELECT COUNT(*) AS cnt FROM audit_logs WHERE 1=1"
    count_params = []
    if actor_type:
        count_sql += " AND actor_type = %s"
        count_params.append(actor_type)
    total = query_one(count_sql, count_params)["cnt"]
    total_pages = (total + AUDIT_PAGE_SIZE - 1) // AUDIT_PAGE_SIZE

    return render_template(
        "admin/audit_log.html",
        logs=logs,
        page=page,
        total_pages=total_pages,
        actor_type=actor_type,
    )

