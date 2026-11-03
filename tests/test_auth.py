"""
tests/test_auth.py – Authentication and authorization tests.
"""
from tests.conftest import get_csrf_token
from app.db import query_one, execute, transaction


def test_csrf_missing_returns_400(client):
    """POST request without CSRF token must return 400 Bad Request."""
    resp = client.post("/login", data={"epic_no": "ABC1000001", "password": "Voter@123"})
    assert resp.status_code == 400


def test_register_pending_approve_login_flow(client, app):
    """
    Test full lifecycle:
    1. Register new voter -> status is 'pending'
    2. Pending voter cannot log in
    3. Admin approves voter
    4. Voter can now log in successfully
    """
    token = get_csrf_token(client)
    new_epic = "XYZ9876543"

    # 1. Register voter
    reg_resp = client.post(
        "/register",
        data={
            "_csrf_token": token,
            "epic_no": new_epic,
            "full_name": "Test Candidate Flow",
            "dob": "1995-05-15",
            "gender": "male",
            "email": "testflow@example.com",
            "phone": "9998887770",
            "constituency_id": "1",
            "password": "Password@123",
            "confirm_password": "Password@123",
        },
        follow_redirects=True,
    )
    assert reg_resp.status_code == 200
    assert "Registration successful" in reg_resp.get_data(as_text=True)

    with app.app_context():
        voter = query_one("SELECT * FROM voters WHERE epic_no = %s", (new_epic,))
        assert voter is not None
        assert voter["status"] == "pending"

    # 2. Pending voter cannot log in
    login_fail = client.post(
        "/login",
        data={
            "_csrf_token": token,
            "epic_no": new_epic,
            "password": "Password@123",
        },
        follow_redirects=True,
    )
    assert login_fail.status_code == 200
    assert "pending admin approval" in login_fail.get_data(as_text=True)

    # 3. Admin approves voter
    with app.app_context():
        with transaction():
            execute("UPDATE voters SET status = 'approved', approved_by = 1, approved_at = NOW() WHERE epic_no = %s", (new_epic,))

    # 4. Voter can now log in
    login_ok = client.post(
        "/login",
        data={
            "_csrf_token": token,
            "epic_no": new_epic,
            "password": "Password@123",
        },
        follow_redirects=True,
    )
    assert login_ok.status_code == 200
    assert "Welcome, Test Candidate Flow" in login_ok.get_data(as_text=True)


def test_lockout_after_5_failed_logins(client, app):
    """Account is locked for 15 minutes after 5 consecutive failed login attempts."""
    token = get_csrf_token(client)
    epic = "ABC1000004"  # Approved demo voter

    # Send 5 incorrect passwords
    for i in range(5):
        resp = client.post(
            "/login",
            data={
                "_csrf_token": token,
                "epic_no": epic,
                "password": "WrongPassword!999",
            },
            follow_redirects=True,
        )
        assert resp.status_code == 200

    # 6th attempt even with correct password should be rejected due to lockout
    locked_resp = client.post(
        "/login",
        data={
            "_csrf_token": token,
            "epic_no": epic,
            "password": "Voter@123",
        },
        follow_redirects=True,
    )
    assert locked_resp.status_code == 200
    assert "temporarily locked" in locked_resp.get_data(as_text=True)

    # Reset lockout for other tests
    with app.app_context():
        with transaction():
            execute("UPDATE voters SET failed_attempts = 0, locked_until = NULL WHERE epic_no = %s", (epic,))

