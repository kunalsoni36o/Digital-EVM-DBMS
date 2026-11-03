"""
tests/test_voting.py – Voting service and ballot tests.
"""
import pytest
from app.services.vote_service import cast_vote, VoteError
from app.db import query_one, query_all, execute, transaction
from tests.conftest import get_csrf_token


def test_successful_vote_and_second_vote_refused(app):
    """
    Voter ABC1000005 (voter_id=5, approved, constituency_id=1) has not voted in election 1.
    They should vote successfully and get a 16-character receipt.
    A second attempt must raise VoteError.
    """
    with app.app_context():
        # Candidate 2 belongs to election 1, constituency 1
        receipt = cast_vote(voter_id=5, election_id=1, candidate_id=2)
        assert len(receipt) == 16
        assert receipt.isupper()

        # Second vote attempt must fail
        with pytest.raises(VoteError) as exc_info:
            cast_vote(voter_id=5, election_id=1, candidate_id=2)
        assert "already voted" in str(exc_info.value).lower()


def test_vote_candidate_other_constituency_refused(app):
    """
    Voter in constituency 1 trying to vote for Candidate 4 (who is in constituency 2)
    must be rejected.
    """
    with app.app_context():
        # Create a temporary approved voter in constituency 1
        with transaction():
            voter_id = execute(
                """
                INSERT INTO voters (epic_no, full_name, dob, gender, email, password_hash, constituency_id, status)
                VALUES ('TST1000001', 'Other Const Tester', '1990-01-01', 'male', 'otherconst@test.local', 'hash', 1, 'approved')
                """
            )

        try:
            # Candidate 4 is in constituency 2
            with pytest.raises(VoteError) as exc_info:
                cast_vote(voter_id=voter_id, election_id=1, candidate_id=4)
            assert "own constituency" in str(exc_info.value).lower()
        finally:
            with transaction():
                execute("DELETE FROM voters WHERE voter_id = %s", (voter_id,))


def test_nota_vote_counted_in_v_nota_tally(app):
    """
    Casting a vote with candidate_id=None records a NOTA vote
    which appears in v_nota_tally.
    """
    with app.app_context():
        # Get baseline NOTA count for election 1, constituency 1
        row = query_one("SELECT nota_votes FROM v_nota_tally WHERE election_id = 1 AND constituency_id = 1")
        initial_nota = row["nota_votes"] if row else 0

        # Create temporary approved voter in constituency 1
        with transaction():
            voter_id = execute(
                """
                INSERT INTO voters (epic_no, full_name, dob, gender, email, password_hash, constituency_id, status)
                VALUES ('NOT1000001', 'NOTA Voter Tester', '1990-01-01', 'female', 'nota@test.local', 'hash', 1, 'approved')
                """
            )

        receipt = cast_vote(voter_id=voter_id, election_id=1, candidate_id=None)
        assert len(receipt) == 16

        # Check tally increased by 1
        new_row = query_one("SELECT nota_votes FROM v_nota_tally WHERE election_id = 1 AND constituency_id = 1")
        assert new_row["nota_votes"] == initial_nota + 1


def test_voting_on_non_active_election_refused(app):
    """Election 2 is 'draft' in seed data. Voting in it must fail."""
    with app.app_context():
        with pytest.raises(VoteError) as exc_info:
            cast_vote(voter_id=5, election_id=2, candidate_id=None)
        assert "not currently active" in str(exc_info.value).lower()


def test_receipt_verification_does_not_expose_voter(client):
    """
    Verifying a valid receipt code returns election title and timestamp,
    but NEVER exposes voter name, email, EPIC, or candidate choice.
    """
    # From seed.sql: receipt code RCPT0000000000A1 exists
    token = get_csrf_token(client)
    resp = client.post(
        "/verify-receipt",
        data={
            "_csrf_token": token,
            "receipt_code": "RCPT0000000000A1",
        },
    )
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)

    # Must show election title and valid receipt confirmation
    assert "Valid Receipt" in html
    assert "General Election 2026" in html

    # Must NOT reveal voter identity or choice
    assert "Aarav" not in html
    assert "ABC1000001" not in html
    assert "Anil Kulkarni" not in html

