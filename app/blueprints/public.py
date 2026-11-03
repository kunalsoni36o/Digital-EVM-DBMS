"""
app/blueprints/public.py – unauthenticated pages.

Routes
------
GET  /                  Home page
GET  /verify-receipt    Verify a ballot receipt code
POST /verify-receipt
GET  /results           List published elections
GET  /results/<id>      Per-election results detail
"""
from flask import Blueprint, render_template, request, flash, redirect, url_for
from app.db import query_all, query_one
from app.services.election_service import sync_statuses
from app.utils.validators import validate_receipt_code

public_bp = Blueprint("public", __name__)


@public_bp.before_request
def _sync():
    """Keep election statuses up-to-date on every public request."""
    sync_statuses()


# ------------------------------------------------------------------ #
# Home
# ------------------------------------------------------------------ #

@public_bp.route("/")
def home():
    return render_template("public/home.html")


# ------------------------------------------------------------------ #
# Verify receipt
# ------------------------------------------------------------------ #

@public_bp.route("/verify-receipt", methods=["GET", "POST"])
def verify_receipt():
    result = None
    searched = False

    if request.method == "POST":
        raw = request.form.get("receipt_code", "")
        try:
            code = validate_receipt_code(raw)
        except ValueError as exc:
            flash(str(exc), "error")
            return render_template("public/verify_receipt.html", result=None, searched=False)

        # Look up the receipt – reveal ONLY existence + election title + cast time
        # NEVER reveal who voted or what they chose.
        row = query_one(
            """
            SELECT v.receipt_code, v.cast_at, e.title AS election_title
            FROM votes v
            JOIN elections e ON e.election_id = v.election_id
            WHERE v.receipt_code = %s
            """,
            (code,),
        )
        result = row
        searched = True
        if not row:
            flash("No vote found with that receipt code.", "info")

    return render_template("public/verify_receipt.html", result=result, searched=searched)


# ------------------------------------------------------------------ #
# Results list
# ------------------------------------------------------------------ #

@public_bp.route("/results")
def results():
    elections = query_all(
        """
        SELECT election_id, title, description, end_time
        FROM elections
        WHERE results_published = 1
        ORDER BY end_time DESC
        """,
    )
    return render_template("public/results.html", elections=elections)


# ------------------------------------------------------------------ #
# Results detail
# ------------------------------------------------------------------ #

@public_bp.route("/results/<int:election_id>")
def results_detail(election_id: int):
    # Only show published elections
    election = query_one(
        "SELECT * FROM elections WHERE election_id = %s AND results_published = 1",
        (election_id,),
    )
    if not election:
        return render_template("public/404.html"), 404

    # Tally per constituency using the view
    tally = query_all(
        """
        SELECT t.constituency_id, k.name AS constituency_name,
               t.candidate_id, t.candidate_name, t.party, t.votes,
               RANK() OVER (
                   PARTITION BY t.constituency_id
                   ORDER BY t.votes DESC
               ) AS pos
        FROM v_candidate_tally t
        JOIN constituencies k ON k.constituency_id = t.constituency_id
        WHERE t.election_id = %s
        ORDER BY t.constituency_id, t.votes DESC
        """,
        (election_id,),
    )

    # NOTA per constituency
    nota = query_all(
        """
        SELECT n.constituency_id, k.name AS constituency_name, n.nota_votes
        FROM v_nota_tally n
        JOIN constituencies k ON k.constituency_id = n.constituency_id
        WHERE n.election_id = %s
        """,
        (election_id,),
    )
    nota_map = {r["constituency_id"]: r["nota_votes"] for r in nota}

    # Turnout
    turnout = query_one(
        "SELECT * FROM v_turnout WHERE election_id = %s",
        (election_id,),
    )

    # Group tally by constituency
    constituencies = {}
    for row in tally:
        cid = row["constituency_id"]
        if cid not in constituencies:
            constituencies[cid] = {
                "name": row["constituency_name"],
                "candidates": [],
                "nota_votes": nota_map.get(cid, 0),
            }
        constituencies[cid]["candidates"].append(row)

    return render_template(
        "public/results_detail.html",
        election=election,
        constituencies=constituencies,
        turnout=turnout,
    )

