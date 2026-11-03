-- =====================================================================
-- Digi EVM : E-Voting Management System  |  MySQL 8.x schema
-- Run in the mysql client (it uses DELIMITER for the triggers):
--   mysql -u evm_user -p < schema.sql
-- =====================================================================

DROP DATABASE IF EXISTS digi_evm;
CREATE DATABASE digi_evm CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE digi_evm;

-- ---------------------------------------------------------------------
-- 1. constituencies
-- ---------------------------------------------------------------------
CREATE TABLE constituencies (
    constituency_id INT UNSIGNED NOT NULL AUTO_INCREMENT,
    code            VARCHAR(10)  NOT NULL,
    name            VARCHAR(100) NOT NULL,
    state           VARCHAR(60)  NOT NULL,
    created_at      TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (constituency_id),
    UNIQUE KEY uq_constituency_code (code),
    UNIQUE KEY uq_constituency_name_state (name, state)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- 2. parties
-- ---------------------------------------------------------------------
CREATE TABLE parties (
    party_id    INT UNSIGNED NOT NULL AUTO_INCREMENT,
    name        VARCHAR(100) NOT NULL,
    short_name  VARCHAR(15)  NOT NULL,
    symbol      VARCHAR(60)  NULL,
    logo_path   VARCHAR(255) NULL,
    created_at  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (party_id),
    UNIQUE KEY uq_party_name (name),
    UNIQUE KEY uq_party_short (short_name)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- 3. admins
-- ---------------------------------------------------------------------
CREATE TABLE admins (
    admin_id      INT UNSIGNED NOT NULL AUTO_INCREMENT,
    username      VARCHAR(50)  NOT NULL,
    full_name     VARCHAR(100) NOT NULL,
    email         VARCHAR(120) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    is_active     TINYINT(1)   NOT NULL DEFAULT 1,
    created_at    TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (admin_id),
    UNIQUE KEY uq_admin_username (username),
    UNIQUE KEY uq_admin_email (email)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- 4. voters
-- ---------------------------------------------------------------------
CREATE TABLE voters (
    voter_id        INT UNSIGNED NOT NULL AUTO_INCREMENT,
    epic_no         CHAR(10)     NOT NULL,                 -- Voter ID card number
    full_name       VARCHAR(100) NOT NULL,
    dob             DATE         NOT NULL,
    gender          ENUM('male','female','other') NOT NULL,
    email           VARCHAR(120) NOT NULL,
    phone           VARCHAR(15)  NULL,
    password_hash   VARCHAR(255) NOT NULL,
    constituency_id INT UNSIGNED NOT NULL,
    status          ENUM('pending','approved','rejected','blocked')
                    NOT NULL DEFAULT 'pending',
    failed_attempts TINYINT UNSIGNED NOT NULL DEFAULT 0,
    locked_until    DATETIME     NULL,
    approved_by     INT UNSIGNED NULL,
    approved_at     DATETIME     NULL,
    created_at      TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (voter_id),
    UNIQUE KEY uq_voter_epic (epic_no),
    UNIQUE KEY uq_voter_email (email),
    KEY idx_voter_constituency (constituency_id),
    KEY idx_voter_status (status),
    CONSTRAINT fk_voter_constituency FOREIGN KEY (constituency_id)
        REFERENCES constituencies (constituency_id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_voter_approved_by FOREIGN KEY (approved_by)
        REFERENCES admins (admin_id)
        ON UPDATE CASCADE ON DELETE SET NULL
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- 5. elections
-- ---------------------------------------------------------------------
CREATE TABLE elections (
    election_id       INT UNSIGNED NOT NULL AUTO_INCREMENT,
    title             VARCHAR(150) NOT NULL,
    description       TEXT         NULL,
    start_time        DATETIME     NOT NULL,
    end_time          DATETIME     NOT NULL,
    status            ENUM('draft','scheduled','active','closed')
                      NOT NULL DEFAULT 'draft',
    results_published TINYINT(1)   NOT NULL DEFAULT 0,
    created_by        INT UNSIGNED NULL,
    created_at        TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (election_id),
    KEY idx_election_status (status),
    CONSTRAINT chk_election_time CHECK (end_time > start_time),
    CONSTRAINT fk_election_admin FOREIGN KEY (created_by)
        REFERENCES admins (admin_id)
        ON UPDATE CASCADE ON DELETE SET NULL
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- 6. candidates   (party_id NULL = independent)
-- ---------------------------------------------------------------------
CREATE TABLE candidates (
    candidate_id    INT UNSIGNED NOT NULL AUTO_INCREMENT,
    election_id     INT UNSIGNED NOT NULL,
    constituency_id INT UNSIGNED NOT NULL,
    party_id        INT UNSIGNED NULL,
    full_name       VARCHAR(100) NOT NULL,
    photo_path      VARCHAR(255) NULL,
    created_at      TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (candidate_id),
    UNIQUE KEY uq_candidate_scope (candidate_id, election_id, constituency_id),
    UNIQUE KEY uq_candidate_name (election_id, constituency_id, full_name),
    KEY idx_candidate_party (party_id),
    CONSTRAINT fk_candidate_election FOREIGN KEY (election_id)
        REFERENCES elections (election_id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_candidate_constituency FOREIGN KEY (constituency_id)
        REFERENCES constituencies (constituency_id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_candidate_party FOREIGN KEY (party_id)
        REFERENCES parties (party_id)
        ON UPDATE CASCADE ON DELETE SET NULL
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- 7. voter_participation  (WHO voted - never WHAT they voted)
-- ---------------------------------------------------------------------
CREATE TABLE voter_participation (
    participation_id INT UNSIGNED NOT NULL AUTO_INCREMENT,
    election_id      INT UNSIGNED NOT NULL,
    voter_id         INT UNSIGNED NOT NULL,
    voted_at         TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (participation_id),
    UNIQUE KEY uq_one_vote_per_election (election_id, voter_id),
    KEY idx_participation_voter (voter_id),
    CONSTRAINT fk_part_election FOREIGN KEY (election_id)
        REFERENCES elections (election_id) ON DELETE RESTRICT,
    CONSTRAINT fk_part_voter FOREIGN KEY (voter_id)
        REFERENCES voters (voter_id) ON DELETE RESTRICT
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- 8. votes  (WHAT was cast - deliberately has NO voter column)
--    candidate_id NULL = NOTA.
--    The composite FK guarantees the candidate belongs to the same
--    election and constituency as the ballot (skipped for NOTA).
-- ---------------------------------------------------------------------
CREATE TABLE votes (
    vote_id         BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    election_id     INT UNSIGNED NOT NULL,
    constituency_id INT UNSIGNED NOT NULL,
    candidate_id    INT UNSIGNED NULL,
    receipt_code    CHAR(16)     NOT NULL,
    cast_at         TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (vote_id),
    UNIQUE KEY uq_receipt (receipt_code),
    KEY idx_vote_tally (election_id, constituency_id, candidate_id),
    CONSTRAINT fk_vote_candidate_scope FOREIGN KEY
        (candidate_id, election_id, constituency_id)
        REFERENCES candidates (candidate_id, election_id, constituency_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_vote_election FOREIGN KEY (election_id)
        REFERENCES elections (election_id) ON DELETE RESTRICT,
    CONSTRAINT fk_vote_constituency FOREIGN KEY (constituency_id)
        REFERENCES constituencies (constituency_id) ON DELETE RESTRICT
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- 9. audit_logs
-- ---------------------------------------------------------------------
CREATE TABLE audit_logs (
    log_id      BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    actor_type  ENUM('admin','voter','system') NOT NULL,
    actor_id    INT UNSIGNED NULL,
    action      VARCHAR(60)  NOT NULL,
    entity      VARCHAR(40)  NULL,
    entity_id   INT UNSIGNED NULL,
    details     VARCHAR(500) NULL,
    ip_address  VARCHAR(45)  NULL,
    created_at  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (log_id),
    KEY idx_audit_actor (actor_type, actor_id),
    KEY idx_audit_created (created_at)
) ENGINE=InnoDB;

-- =====================================================================
-- TRIGGERS : rules enforced by the database itself
-- =====================================================================
DELIMITER $$

-- Candidates can only be added while the election is a draft
CREATE TRIGGER trg_candidates_bi BEFORE INSERT ON candidates
FOR EACH ROW
BEGIN
    DECLARE v_status VARCHAR(10);
    SELECT status INTO v_status FROM elections WHERE election_id = NEW.election_id;
    IF v_status <> 'draft' THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Candidates can only be added while the election is a draft';
    END IF;
END$$

-- Only approved voters, in an active election, in a constituency
-- that has a ballot for that election
CREATE TRIGGER trg_participation_bi BEFORE INSERT ON voter_participation
FOR EACH ROW
BEGIN
    DECLARE v_vstatus VARCHAR(10);
    DECLARE v_estatus VARCHAR(10);
    SELECT status INTO v_vstatus FROM voters WHERE voter_id = NEW.voter_id;
    SELECT status INTO v_estatus FROM elections WHERE election_id = NEW.election_id;
    IF v_vstatus <> 'approved' THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Voter is not approved';
    END IF;
    IF v_estatus <> 'active' THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Election is not active';
    END IF;
END$$

-- Votes can only be inserted while the election is active
CREATE TRIGGER trg_votes_bi BEFORE INSERT ON votes
FOR EACH ROW
BEGIN
    DECLARE v_estatus VARCHAR(10);
    SELECT status INTO v_estatus FROM elections WHERE election_id = NEW.election_id;
    IF v_estatus <> 'active' THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Election is not active';
    END IF;
END$$

-- Votes are immutable
CREATE TRIGGER trg_votes_bu BEFORE UPDATE ON votes
FOR EACH ROW
BEGIN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Votes cannot be modified';
END$$

CREATE TRIGGER trg_votes_bd BEFORE DELETE ON votes
FOR EACH ROW
BEGIN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Votes cannot be deleted';
END$$

-- Participation records are immutable too
CREATE TRIGGER trg_participation_bu BEFORE UPDATE ON voter_participation
FOR EACH ROW
BEGIN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Participation records cannot be modified';
END$$

CREATE TRIGGER trg_participation_bd BEFORE DELETE ON voter_participation
FOR EACH ROW
BEGIN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Participation records cannot be deleted';
END$$

DELIMITER ;

-- =====================================================================
-- VIEWS : feed the result pages
-- =====================================================================

-- Votes per candidate (candidates with zero votes still appear)
CREATE VIEW v_candidate_tally AS
SELECT  c.election_id,
        c.constituency_id,
        c.candidate_id,
        c.full_name                      AS candidate_name,
        COALESCE(p.short_name, 'IND')    AS party,
        COUNT(v.vote_id)                 AS votes
FROM    candidates c
LEFT JOIN parties p ON p.party_id = c.party_id
LEFT JOIN votes   v ON v.candidate_id = c.candidate_id
GROUP BY c.election_id, c.constituency_id, c.candidate_id,
         c.full_name, p.short_name;

-- NOTA votes per constituency
CREATE VIEW v_nota_tally AS
SELECT  election_id, constituency_id, COUNT(*) AS nota_votes
FROM    votes
WHERE   candidate_id IS NULL
GROUP BY election_id, constituency_id;

-- Turnout per election
CREATE VIEW v_turnout AS
SELECT  e.election_id,
        e.title,
        (SELECT COUNT(*) FROM voters WHERE status = 'approved')  AS eligible_voters,
        COUNT(vp.participation_id)                               AS votes_cast,
        ROUND(100 * COUNT(vp.participation_id) /
              NULLIF((SELECT COUNT(*) FROM voters WHERE status = 'approved'), 0), 2)
                                                                 AS turnout_percent
FROM    elections e
LEFT JOIN voter_participation vp ON vp.election_id = e.election_id
GROUP BY e.election_id, e.title;
