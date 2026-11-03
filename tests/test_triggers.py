"""
tests/test_triggers.py – Tests for database-level triggers enforcing business invariants.
"""
import pytest
import pymysql
from app.db import execute, transaction, query_one


def test_vote_rows_immutable_trigger(app):
    """
    Triggers trg_votes_bu and trg_votes_bd must raise SQLSTATE 45000
    when attempting to UPDATE or DELETE rows in the votes table.
    """
    with app.app_context():
        vote = query_one("SELECT vote_id FROM votes LIMIT 1")
        assert vote is not None
        vote_id = vote["vote_id"]

        # Attempt UPDATE -> trigger must abort with OperationalError / SQLSTATE 45000
        with pytest.raises(pymysql.err.OperationalError) as exc_update:
            with transaction():
                execute("UPDATE votes SET receipt_code = 'MODIFIED00000000' WHERE vote_id = %s", (vote_id,))
        assert "cannot be modified" in str(exc_update.value).lower()

        # Attempt DELETE -> trigger must abort with OperationalError / SQLSTATE 45000
        with pytest.raises(pymysql.err.OperationalError) as exc_delete:
            with transaction():
                execute("DELETE FROM votes WHERE vote_id = %s", (vote_id,))
        assert "cannot be deleted" in str(exc_delete.value).lower()


def test_candidate_cannot_be_added_to_non_draft_election_trigger(app):
    """
    Trigger trg_candidates_bi must raise SQLSTATE 45000 when attempting to
    insert a candidate into an active or closed election.
    """
    with app.app_context():
        # Election 1 is 'active'
        with pytest.raises(pymysql.err.OperationalError) as exc:
            with transaction():
                execute(
                    """
                    INSERT INTO candidates (election_id, constituency_id, party_id, full_name)
                    VALUES (1, 1, 1, 'Late Candidate')
                    """
                )
        assert "draft" in str(exc.value).lower()

