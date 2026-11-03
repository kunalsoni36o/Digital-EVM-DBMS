"""
app/services/vote_service.py – cast_vote transactional logic.

Ballot-secrecy rules (MUST NOT be violated):
- voter_participation stores WHO voted (voter_id + election_id, no choice).
- votes stores WHAT was cast (candidate_id or NULL for NOTA, no voter_id).
- The receipt code links neither table to a voter.
- audit_log entry contains only voter_id + election_id (no candidate, no receipt).
"""
import secrets
import pymysql
from app.db import get_db, execute, query_one
from app.services import audit_service


class VoteError(Exception):
    """Friendly error raised by cast_vote; message is safe to show the user."""


def cast_vote(voter_id: int, election_id: int, candidate_id: int | None) -> str:
    """
    Cast one ballot inside a single transaction.

    Parameters
    ----------
    voter_id     : authenticated voter's PK
    election_id  : election being voted in
    candidate_id : PK of chosen candidate, or None for NOTA

    Returns
    -------
    str : 16-character uppercase receipt code

    Raises
    ------
    VoteError : on any business-rule violation (shown to the user)
    """
    db = get_db()
    try:
        db.begin()

        # ------------------------------------------------------------------ #
        # 1. Lock the voter row and verify status
        # ------------------------------------------------------------------ #
        with db.cursor() as cur:
            cur.execute(
                "SELECT voter_id, status, constituency_id "
                "FROM voters WHERE voter_id = %s FOR UPDATE",
                (voter_id,),
            )
            voter = cur.fetchone()

        if not voter or voter["status"] != "approved":
            raise VoteError("Your account is not approved for voting.")

        voter_constituency = voter["constituency_id"]

        # ------------------------------------------------------------------ #
        # 2. Re-check election is active and within time window
        # ------------------------------------------------------------------ #
        with db.cursor() as cur:
            cur.execute(
                "SELECT status, start_time, end_time "
                "FROM elections WHERE election_id = %s",
                (election_id,),
            )
            election = cur.fetchone()

        if not election or election["status"] != "active":
            raise VoteError("This election is not currently active.")

        from datetime import datetime, timezone
        now = datetime.now()
        if not (election["start_time"] <= now <= election["end_time"]):
            raise VoteError("Voting is outside the allowed time window for this election.")

        # ------------------------------------------------------------------ #
        # 3. Check the voter has not already voted
        # ------------------------------------------------------------------ #
        with db.cursor() as cur:
            cur.execute(
                "SELECT participation_id FROM voter_participation "
                "WHERE election_id = %s AND voter_id = %s",
                (election_id, voter_id),
            )
            already = cur.fetchone()

        if already:
            raise VoteError("You have already voted in this election.")

        # ------------------------------------------------------------------ #
        # 4. Validate the candidate (if not NOTA)
        # ------------------------------------------------------------------ #
        if candidate_id is not None:
            with db.cursor() as cur:
                cur.execute(
                    "SELECT candidate_id FROM candidates "
                    "WHERE candidate_id = %s "
                    "  AND election_id = %s "
                    "  AND constituency_id = %s",
                    (candidate_id, election_id, voter_constituency),
                )
                cand = cur.fetchone()

            if not cand:
                raise VoteError(
                    "Invalid candidate selection. "
                    "You may only vote for a candidate in your own constituency."
                )

        # ------------------------------------------------------------------ #
        # 5. Insert voter_participation (WHO voted)
        # ------------------------------------------------------------------ #
        with db.cursor() as cur:
            cur.execute(
                "INSERT INTO voter_participation (election_id, voter_id) "
                "VALUES (%s, %s)",
                (election_id, voter_id),
            )

        # ------------------------------------------------------------------ #
        # 6. Generate receipt code and insert vote (WHAT was cast)
        #    Retry once on the rare duplicate receipt collision.
        # ------------------------------------------------------------------ #
        receipt_code = _generate_unique_receipt(db, election_id, voter_constituency, candidate_id)

        # ------------------------------------------------------------------ #
        # 7. Commit
        # ------------------------------------------------------------------ #
        db.commit()

        # ------------------------------------------------------------------ #
        # 8. Audit log (voter_id + election_id only – NO candidate, NO receipt)
        # ------------------------------------------------------------------ #
        with db.cursor() as cur:
            cur.execute(
                """
                INSERT INTO audit_logs
                    (actor_type, actor_id, action, entity, entity_id, ip_address)
                VALUES ('voter', %s, 'vote_cast', 'election', %s, %s)
                """,
                (voter_id, election_id, _get_ip()),
            )
        db.commit()

        return receipt_code

    except VoteError:
        db.rollback()
        raise
    except pymysql.err.IntegrityError as exc:
        db.rollback()
        code = exc.args[0]
        if code == 1062:
            raise VoteError("Duplicate entry – you may have already voted.")
        if code == 1452:
            raise VoteError("Invalid candidate or election reference.")
        raise VoteError(f"Database integrity error ({code}).")
    except pymysql.err.OperationalError as exc:
        db.rollback()
        msg = exc.args[1] if len(exc.args) > 1 else str(exc)
        if "1644" in str(exc.args[0]) or "SIGNAL" in msg or "not approved" in msg or "not active" in msg:
            raise VoteError(msg)
        raise VoteError("A database error occurred. Please try again.")
    except Exception:
        db.rollback()
        raise


def _generate_unique_receipt(db, election_id: int, constituency_id: int, candidate_id: int | None) -> str:
    """
    Insert into votes with a random receipt code.
    Retries once if the code collides (1-in-2^64 chance).
    """
    for _ in range(2):
        code = secrets.token_hex(8).upper()   # 16 uppercase hex chars
        try:
            with db.cursor() as cur:
                cur.execute(
                    "INSERT INTO votes (election_id, constituency_id, candidate_id, receipt_code) "
                    "VALUES (%s, %s, %s, %s)",
                    (election_id, constituency_id, candidate_id, code),
                )
            return code
        except pymysql.err.IntegrityError as exc:
            if exc.args[0] == 1062:
                continue   # retry with a new code
            raise
    raise VoteError("Could not generate a unique receipt code. Please try again.")


def _get_ip() -> str | None:
    """Safely get the remote IP address within a request context."""
    try:
        from flask import request
        return request.remote_addr
    except RuntimeError:
        return None

