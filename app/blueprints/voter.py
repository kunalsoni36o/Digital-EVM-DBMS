"""
app/blueprints/voter.py – voter area (dashboard, ballot, receipt).

All routes require @voter_required.
"""
from flask import (
    Blueprint, render_template, request, redirect,
    url_for, flash, session,
)
from app.db import query_all, query_one
from app.services.election_service import sync_statuses
from app.services.vote_service import cast_vote, VoteError
from app.utils.security import voter_required, validate_csrf

voter_bp = Blueprint("voter", __name__)


@voter_bp.before_request
def _before():
    validate_csrf()
    sync_statuses()


# ------------------------------------------------------------------ #
# Dashboard
# ------------------------------------------------------------------ #

@voter_bp.route("/dashboard")
@voter_required
def dashboard():
    voter_id = session["user_id"]

    voter = query_one(
        """
        SELECT v.voter_id, v.epic_no, v.full_name, v.email,
               c.name AS constituency_name
        FROM voters v
        JOIN constituencies c ON c.constituency_id = v.constituency_id
        WHERE v.voter_id = %s
        """,
        (voter_id,),
    )

    # All elections with participation status for this voter
    elections = query_all(
        """
        SELECT e.election_id, e.title, e.status, e.start_time, e.end_time,
               (SELECT COUNT(*) FROM voter_participation
                WHERE election_id = e.election_id AND voter_id = %s) AS has_voted
        FROM elections e
        ORDER BY e.start_time DESC
        """,
        (voter_id,),
    )

    active    = [el for el in elections if el["status"] == "active"]
    upcoming  = [el for el in elections if el["status"] in ("draft", "scheduled")]
    closed    = [el for el in elections if el["status"] == "closed"]

    return render_template(
        "voter/dashboard.html",
        voter=voter,
        active=active,
        upcoming=upcoming,
        closed=closed,
    )


# ------------------------------------------------------------------ #
# Ballot (GET)
# ------------------------------------------------------------------ #

@voter_bp.route("/elections/<int:election_id>/ballot")
@voter_required
def ballot(election_id: int):
    voter_id = session["user_id"]

    # Get voter's constituency
    voter = query_one(
        "SELECT constituency_id FROM voters WHERE voter_id = %s",
        (voter_id,),
    )

    # Election must be active
    election = query_one(
        "SELECT * FROM elections WHERE election_id = %s AND status = 'active'",
        (election_id,),
    )
    if not election:
        flash("This election is not currently active.", "error")
        return redirect(url_for("voter.dashboard"))

    # Check not already voted
    already = query_one(
        "SELECT participation_id FROM voter_participation "
        "WHERE election_id = %s AND voter_id = %s",
        (election_id, voter_id),
    )
    if already:
        flash("You have already voted in this election.", "info")
        return redirect(url_for("voter.dashboard"))

    # Fetch candidates in voter's constituency only
    candidates = query_all(
        """
        SELECT c.candidate_id, c.full_name, c.photo_path,
               COALESCE(p.name, 'Independent') AS party_name,
               COALESCE(p.short_name, 'IND')   AS party_short,
               p.symbol
        FROM candidates c
        LEFT JOIN parties p ON p.party_id = c.party_id
        WHERE c.election_id = %s AND c.constituency_id = %s
        ORDER BY c.full_name
        """,
        (election_id, voter["constituency_id"]),
    )

    return render_template(
        "voter/ballot.html",
        election=election,
        candidates=candidates,
    )


# ------------------------------------------------------------------ #
# Cast vote (POST)
# ------------------------------------------------------------------ #

@voter_bp.route("/elections/<int:election_id>/vote", methods=["POST"])
@voter_required
def vote(election_id: int):
    voter_id = session["user_id"]

    raw_candidate = request.form.get("candidate_id", "").strip()

    # Determine candidate_id (None = NOTA)
    if raw_candidate == "NOTA" or raw_candidate == "":
        candidate_id = None
    elif raw_candidate.isdigit():
        candidate_id = int(raw_candidate)
    else:
        flash("Invalid selection. Please choose a candidate or NOTA.", "error")
        return redirect(url_for("voter.ballot", election_id=election_id))

    try:
        receipt_code = cast_vote(voter_id, election_id, candidate_id)
    except VoteError as exc:
        flash(str(exc), "error")
        return redirect(url_for("voter.ballot", election_id=election_id))
    except Exception:
        flash("An unexpected error occurred. Please try again.", "error")
        return redirect(url_for("voter.ballot", election_id=election_id))

    # Store receipt in session flash (one-time use only)
    # We NEVER store the receipt persistently linked to the voter.
    session["_receipt_code"] = receipt_code
    session["_receipt_election"] = election_id
    return redirect(url_for("voter.receipt"))


# ------------------------------------------------------------------ #
# Receipt (shown once, from session)
# ------------------------------------------------------------------ #

@voter_bp.route("/receipt")
@voter_required
def receipt():
    code = session.pop("_receipt_code", None)
    election_id = session.pop("_receipt_election", None)

    if not code:
        # If the voter navigates here without just having voted, show nothing
        flash("No receipt to display. Receipts are shown only once, immediately after voting.", "info")
        return redirect(url_for("voter.dashboard"))

    election = None
    if election_id:
        election = query_one(
            "SELECT title FROM elections WHERE election_id = %s",
            (election_id,),
        )

    return render_template("voter/receipt.html", receipt_code=code, election=election)

