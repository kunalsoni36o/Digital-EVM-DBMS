"""
tests/test_results.py – Public election results visibility tests.
"""
from app.db import execute, transaction


def test_results_404_until_published_then_200(client, app):
    """
    Results detail returns 404 while results_published = 0,
    and 200 once results_published = 1.
    """
    # In seed data, election 1 has results_published = 0
    resp_unpub = client.get("/results/1")
    assert resp_unpub.status_code == 404

    # Publish results
    with app.app_context():
        with transaction():
            execute("UPDATE elections SET results_published = 1 WHERE election_id = 1")

    try:
        resp_pub = client.get("/results/1")
        assert resp_pub.status_code == 200
        html = resp_pub.get_data(as_text=True)
        assert "General Election 2026" in html
        assert "Turnout" in html
        assert "Mumbai North" in html
    finally:
        # Reset back to unpublished
        with app.app_context():
            with transaction():
                execute("UPDATE elections SET results_published = 0 WHERE election_id = 1")

