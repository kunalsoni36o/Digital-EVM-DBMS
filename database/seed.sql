-- Digi EVM demo data. Run after schema.sql:  mysql -u evm_user -p digi_evm < seed.sql
-- Logins: admin / Admin@123   |   voter ABC1000001 / Voter@123
USE digi_evm;

INSERT INTO constituencies (code, name, state) VALUES
 ('MUM-N', 'Mumbai North', 'Maharashtra'),
 ('MUM-S', 'Mumbai South', 'Maharashtra'),
 ('PUN-C', 'Pune Central',  'Maharashtra');

INSERT INTO parties (name, short_name, symbol) VALUES
 ('Progressive Alliance',  'PA',  'Lotus'),
 ('National Unity Party',  'NUP', 'Hand'),
 ('People''s Front',       'PF',  'Broom');

INSERT INTO admins (username, full_name, email, password_hash) VALUES
 ('admin', 'System Administrator', 'admin@digievm.local',
  'scrypt:32768:8:1$nh6Dainq9bQIhHFd$d7fd2c9b66e4dfbad90e6927d2a3fa31c1c26d759dbe12d5536214246d4883f894238eee9e42b162855f97a930c5399b5c2a02cb5e16b4a906e4ea49a190947b');

-- all demo voters share the password Voter@123
SET @vh = 'scrypt:32768:8:1$E7EaY2GOKU1rTNKc$fe19bdf0ca21d6e6012688c1ee14789cea546eade6c6222cd7a8c1714410b514ddef5eb78fa4a9ffd571cc2008aa170b185870d811049d0c3c0d88cb1aa686f6';

INSERT INTO voters (epic_no, full_name, dob, gender, email, phone, password_hash,
                    constituency_id, status, approved_by, approved_at) VALUES
 ('ABC1000001','Aarav Sharma','1995-04-12','male',  'aarav@example.com', '9000000001',@vh,1,'approved',1,NOW()),
 ('ABC1000002','Diya Patel',  '1998-09-23','female','diya@example.com',  '9000000002',@vh,1,'approved',1,NOW()),
 ('ABC1000003','Rohan Mehta', '1990-01-30','male',  'rohan@example.com', '9000000003',@vh,2,'approved',1,NOW()),
 ('ABC1000004','Sneha Iyer',  '2000-07-05','female','sneha@example.com', '9000000004',@vh,2,'approved',1,NOW()),
 ('ABC1000005','Kabir Singh', '1987-11-18','male',  'kabir@example.com', '9000000005',@vh,1,'approved',1,NOW()),
 ('ABC1000006','Meera Nair',  '1999-03-02','female','meera@example.com', '9000000006',@vh,3,'pending', NULL,NULL);

-- Election 1 (will be active) and Election 2 (stays draft)
INSERT INTO elections (title, description, start_time, end_time, status, created_by) VALUES
 ('General Election 2026', 'Demo general election',
  NOW() - INTERVAL 1 DAY, NOW() + INTERVAL 7 DAY, 'draft', 1),
 ('Student Council 2027', 'Upcoming draft election',
  NOW() + INTERVAL 30 DAY, NOW() + INTERVAL 31 DAY, 'draft', 1);

-- Candidates must be added while the election is a draft
INSERT INTO candidates (election_id, constituency_id, party_id, full_name) VALUES
 (1, 1, 1,    'Anil Kulkarni'),
 (1, 1, 2,    'Priya Deshmukh'),
 (1, 1, NULL, 'Sanjay Rao'),        -- independent
 (1, 2, 1,    'Neha Joshi'),
 (1, 2, 3,    'Farhan Qureshi');

UPDATE elections SET status = 'active' WHERE election_id = 1;

-- Sample ballots: participation (who) and votes (what) are stored separately
INSERT INTO voter_participation (election_id, voter_id) VALUES (1,1),(1,2),(1,3);
INSERT INTO votes (election_id, constituency_id, candidate_id, receipt_code) VALUES
 (1, 1, 1,    'RCPT0000000000A1'),
 (1, 1, NULL, 'RCPT0000000000B2'),   -- NOTA
 (1, 2, 4,    'RCPT0000000000C3');

INSERT INTO audit_logs (actor_type, actor_id, action, entity, entity_id, details) VALUES
 ('system', NULL, 'seed_loaded', 'database', NULL, 'Demo data loaded'),
 ('admin',  1,    'election_activated', 'election', 1, 'General Election 2026');
