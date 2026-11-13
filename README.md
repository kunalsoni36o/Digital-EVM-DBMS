# Digi EVM: E-Voting Management System

## Project Summary

Digi EVM is a coursework web application for managing elections and casting votes online. Voters can register, sign in, access an eligible ballot, cast one vote, and verify a receipt code. Administrators approve voters, manage constituencies, parties, candidates, and election timelines, review audit activity, and publish results. The Flask application uses parameterized SQL with MySQL, while database constraints and triggers enforce election rules and preserve the separation between voter participation and ballot choice. The interface uses responsive HTML, CSS, and vanilla JavaScript. This is a demonstration project, not a certified system for real elections.

A secure, transparent, digital e-voting management web application built for a DBMS coursework mini-project using **MySQL 8**, **Python 3.10+ (Flask)**, and **PyMySQL** with raw parameterized SQL.

---

## 1. Project Overview

**Digi EVM** is an online election management and voting platform engineered with strong **ballot secrecy** and strict database-enforced integrity invariants.

### Key Features
- **Strict Ballot Secrecy**: Who voted (`voter_participation`) is stored completely decoupled from what was cast (`votes`). `votes` has no voter column.
- **Verifiable 16-Character Receipt**: Voters receive a 16-character receipt code (`secrets.token_hex(8).upper()`) immediately after voting. They can independently verify their ballot exists in the system without revealing their identity or vote choice.
- **Role-Based Access Control**: Separate authenticated portals for Voters and System Administrators.
- **Security Protections**: CSRF token protection on every state-changing request, SQL injection immunity via parameterized `%s` queries, XSS auto-escaping in Jinja2, temporary lockout after 5 failed logins, and secure HTTP response headers (`X-Content-Type-Options`, `X-Frame-Options`).
- **Comprehensive Admin Suite**: Constituency and political party management, election lifecycle controls (`draft` → `scheduled` → `active` → `closed`), candidate management with file uploads, live tallies, and audit logging.
- **Pure Native Frontend**: Responsive UI built entirely with vanilla HTML5, custom CSS (CSS variables, flexbox, grid), and vanilla JavaScript. No external CDNs or build tools required.

---

## 2. Architecture Diagram

```
+--------------------------------------------------------------------------+
|                               Browser / Client                           |
+--------------------------------------------------------------------------+
       |                                              ^
       | HTTP / Forms (CSRF Protected)                | HTML5 / CSS / Vanilla JS
       v                                              |
+--------------------------------------------------------------------------+
|                           Flask Web Layer                                |
|  - public_bp       (Home, Verify Receipt, Public Results)                |
|  - auth_bp         (Registration, Login, Lockout, Logout)                |
|  - voter_bp        (Dashboard, Ballot, Cast Vote, Receipt Display)       |
|  - admin_bp        (Voters, Constituencies, Parties, Elections, Tally)   |
+--------------------------------------------------------------------------+
       |                                              ^
       v                                              |
+--------------------------------------------------------------------------+
|                          Service & Utility Layer                         |
|  - vote_service.py       (Transactional atomic ballot casting)           |
|  - election_service.py   (Time-based status auto-synchronization)        |
|  - audit_service.py      (System and actor activity audit logging)       |
|  - security.py           (CSRF tokens, auth decorators, secure uploads)  |
|  - validators.py         (EPIC format, age >= 18, password strength)     |
+--------------------------------------------------------------------------+
       |                                              ^
       v                                              |
+--------------------------------------------------------------------------+
|                      app/db.py (PyMySQL Connector)                       |
|  - DictCursor, autocommit=False, connection per request on flask.g       |
|  - Explicit transactions (%s parameterized SQL, no ORM)                 |
+--------------------------------------------------------------------------+
       |                                              ^
       v                                              |
+--------------------------------------------------------------------------+
|                          MySQL 8 Database Layer                          |
|  Tables: constituencies, parties, admins, voters, elections,             |
|          candidates, voter_participation, votes, audit_logs              |
|  Views:  v_candidate_tally, v_nota_tally, v_turnout                      |
|  Triggers:                                                               |
|   - trg_candidates_bi    : Candidate additions allowed only in 'draft'   |
|   - trg_participation_bi : Only approved voters in active elections      |
|   - trg_votes_bi         : Votes inserted only in active elections       |
|   - trg_votes_bu / bd    : Votes table rows are 100% immutable           |
|   - trg_part_bu / bd     : Participation table rows are immutable        |
+--------------------------------------------------------------------------+
```

---

## 3. Folder Structure

```
digi-evm/
├── run.py                     # Application entry point
├── config.py                  # Flask configuration loaded from .env
├── requirements.txt           # Python dependencies
├── .env.example               # Template environment variables
├── .env                       # Local secrets and MySQL configuration (git-ignored)
├── .gitignore
├── README.md                  # Project documentation
├── database/
│   ├── schema.sql             # MySQL 8 schema, triggers, and views
│   ├── seed.sql               # Demo data (constituencies, parties, admin, voters)
│   └── queries.sql            # Viva/demo sample reporting queries
├── scripts/
│   └── init_db.py             # Database creation script (handles DELIMITER directives)
├── tests/
│   ├── conftest.py            # Pytest fixtures and test DB setup
│   ├── test_auth.py           # Registration, login approval, lockout, CSRF tests
│   ├── test_voting.py         # Ballot casting, double-voting prevention, NOTA, receipt
│   ├── test_triggers.py       # Trigger immutability and invariant enforcement tests
│   └── test_results.py        # Results publishing tests
└── app/
    ├── __init__.py            # Application factory (create_app)
    ├── db.py                  # PyMySQL connection management and transaction helpers
    ├── blueprints/
    │   ├── public.py          # Public routes (/, /verify-receipt, /results)
    │   ├── auth.py            # Registration and login for voter and admin
    │   ├── voter.py           # Voter dashboard, ballot, and receipt routes
    │   └── admin.py           # Admin management routes
    ├── services/
    │   ├── vote_service.py     # cast_vote transactional logic
    │   ├── election_service.py # sync_statuses (scheduled -> active -> closed)
    │   └── audit_service.py   # Immutable audit log recorder
    ├── utils/
    │   ├── security.py        # CSRF token generator, auth decorators, file upload
    │   └── validators.py      # EPIC, age, password format validation
    ├── templates/
    │   ├── base.html          # Base layout template
    │   ├── partials/          # navbar, flash, footer
    │   ├── public/            # home, verify_receipt, results, results_detail, error pages
    │   ├── auth/              # voter_login, register, admin_login
    │   ├── voter/             # dashboard, ballot, receipt
    │   └── admin/             # dashboard, voters, constituencies, parties, elections, etc.
    └── static/
        ├── css/style.css      # Pure CSS with custom responsive layout and CSS variables
        ├── js/app.js          # Progressive enhancement JS (confirm modals, password hint)
        └── uploads/           # Uploaded candidate photos and party logos (.gitkeep)
```

---

## 4. Setup Instructions

### Prerequisites
- Python 3.10 or higher
- MySQL Server 8.0 running locally on port 3306

### Step 1: Clone and Set Up Virtual Environment
```bash
cd digi-evm
python -m venv .venv
# On Windows PowerShell:
.venv\Scripts\Activate.ps1
# On Linux/macOS:
# source .venv/bin/activate
```

### Step 2: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 3: Configure MySQL User & Privileges
Log into MySQL as root and create the application user:
```sql
CREATE USER IF NOT EXISTS 'evm_user'@'localhost' IDENTIFIED BY 'evm_password';
GRANT ALL PRIVILEGES ON digi_evm.* TO 'evm_user'@'localhost';
GRANT ALL PRIVILEGES ON digi_evm_test.* TO 'evm_user'@'localhost';
GRANT SUPER ON *.* TO 'evm_user'@'localhost';
SET GLOBAL log_bin_trust_function_creators = 1;
FLUSH PRIVILEGES;
```

### Step 4: Environment Variables
Copy `.env.example` to `.env` and adjust if needed:
```bash
cp .env.example .env
```
Default `.env` values:
```ini
SECRET_KEY=digi-evm-super-secret-key-2026-production
DB_HOST=localhost
DB_PORT=3306
DB_USER=evm_user
DB_PASSWORD=evm_password
DB_NAME=digi_evm
MAX_UPLOAD_MB=2
FLASK_DEBUG=1
```

### Step 5: Initialize the Database
Run the included database initialization script:
```bash
python scripts/init_db.py --yes
```
To initialize the test database:
```bash
python scripts/init_db.py --test --yes
```

### Step 6: Start the Application
```bash
python run.py
```
Open your browser at: **`http://127.0.0.1:5000`**

---

## 5. Demo Logins

| Role | Username / Identifier | Password | Description |
|---|---|---|---|
| **Admin** | `admin` | `Admin@123` | Full access to elections, voters, parties, audit |
| **Voter** | `ABC1000001` | `Voter@123` | Approved voter (Mumbai North) |
| **Voter** | `ABC1000002` | `Voter@123` | Approved voter (Mumbai North) |
| **Voter** | `ABC1000003` | `Voter@123` | Approved voter (Mumbai South) |
| **Voter** | `ABC1000004` | `Voter@123` | Approved voter (Mumbai South) |
| **Voter** | `ABC1000005` | `Voter@123` | Approved voter (Mumbai North) – has not voted yet |
| **Voter** | `ABC1000006` | `Voter@123` | Pending voter awaiting approval |

---

## 6. Running Tests

Run the full pytest suite:
```bash
python -m pytest -v
```
All 11 automated tests will execute against `digi_evm_test`, validating:
1. CSRF protection (missing CSRF returns 400).
2. Voter registration lifecycle (`pending` cannot login, approved voter can login).
3. Account lockout after 5 consecutive failed attempts.
4. Successful vote recording and second vote refusal.
5. Cross-constituency candidate voting prevention.
6. NOTA count verification in `v_nota_tally`.
7. Non-active election voting rejection.
8. Database-level trigger vote row immutability (`UPDATE`/`DELETE` blocked).
9. Candidate insertion rejection for non-draft elections.
10. Results detail page 404 until published, 200 after publish.
11. Receipt code verification without voter identity leakage.

---

## 7. Database Integrity Rules & Invariants

1. **Decoupled Ballot Architecture**: `voter_participation` tracks *who* participated; `votes` stores *what* choice was cast with a cryptographically random receipt code. No foreign key or join path exists between the voter identity and their ballot choice.
2. **One Vote Per Voter Per Election**: Enforced by composite unique key `uq_one_vote_per_election (election_id, voter_id)`.
3. **Immutability of Votes and Participation**: Triggers `trg_votes_bu`, `trg_votes_bd`, `trg_participation_bu`, and `trg_participation_bd` reject any `UPDATE` or `DELETE` with SQLSTATE `45000`.
4. **Draft-Only Candidate Registration**: Trigger `trg_candidates_bi` ensures candidates cannot be modified or inserted once an election transitions out of `draft`.
5. **Constituency Scope Matching**: Composite foreign key `fk_vote_candidate_scope (candidate_id, election_id, constituency_id)` guarantees the candidate belongs to the exact election and constituency of the vote.
6. **Active-Only Ballot Casting**: Triggers and application logic enforce that votes and participation rows can only be created while the election status is `active`.

---

## 8. Limitations

As a coursework mini-project demonstration, this system has the following deliberate limitations:
1. **Identity Verification**: Uses self-registration with EPIC number and admin approval; does not integrate with real-world identity infrastructure such as Aadhaar OTP or national biometric voter registers.
2. **Local Transport Security**: Runs over plain HTTP in development; production deployment requires TLS/HTTPS configuration.
3. **Trusted Database Administrator**: While application code and database schemas decouple voters from votes, a database administrator with direct binary log and memory access could correlate simultaneous transactions.
4. **Remote Voting Coercion Risk**: Like all remote online voting mechanisms, it cannot physically prevent in-person voter coercion or vote-selling at the browser screen.
5. **Single Server Deployment**: Designed as a monolithic Flask application with single-node MySQL; not configured for multi-region high availability or distributed consensus.
6. **Certification**: This is a coursework demonstration system and is not legally certified or accredited for statutory public elections.

