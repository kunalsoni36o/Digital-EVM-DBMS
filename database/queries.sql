-- Digi EVM sample reports (good for demo / viva).  USE digi_evm;

-- 1. Candidate tally for one election, highest first
SELECT constituency_id, candidate_name, party, votes
FROM v_candidate_tally
WHERE election_id = 1
ORDER BY constituency_id, votes DESC;

-- 2. Winner per constituency (window function); ties show the same rank
SELECT * FROM (
  SELECT t.constituency_id, k.name AS constituency, t.candidate_name, t.party, t.votes,
         RANK() OVER (PARTITION BY t.constituency_id ORDER BY t.votes DESC) AS pos
  FROM v_candidate_tally t
  JOIN constituencies k ON k.constituency_id = t.constituency_id
  WHERE t.election_id = 1
) r WHERE pos = 1;

-- 3. NOTA votes per constituency
SELECT k.name, n.nota_votes
FROM v_nota_tally n JOIN constituencies k USING (constituency_id)
WHERE n.election_id = 1;

-- 4. Overall turnout
SELECT * FROM v_turnout;

-- 5. Turnout per constituency
SELECT k.name AS constituency,
       COUNT(DISTINCT v.voter_id)            AS eligible,
       COUNT(DISTINCT vp.voter_id)           AS voted,
       ROUND(100 * COUNT(DISTINCT vp.voter_id) / COUNT(DISTINCT v.voter_id), 1) AS turnout_pct
FROM constituencies k
JOIN voters v ON v.constituency_id = k.constituency_id AND v.status = 'approved'
LEFT JOIN voter_participation vp ON vp.voter_id = v.voter_id AND vp.election_id = 1
GROUP BY k.constituency_id, k.name;

-- 6. Approved voters who have not voted yet
SELECT v.epic_no, v.full_name
FROM voters v
LEFT JOIN voter_participation vp ON vp.voter_id = v.voter_id AND vp.election_id = 1
WHERE v.status = 'approved' AND vp.voter_id IS NULL;

-- 7. Registrations waiting for admin approval
SELECT epic_no, full_name, created_at FROM voters WHERE status = 'pending';

-- 8. Verify a receipt (proves the vote exists, reveals nothing about the voter)
SELECT election_id, cast_at FROM votes WHERE receipt_code = 'RCPT0000000000A1';

-- 9. Integrity check: ballots counted must equal participation records
SELECT e.election_id,
       (SELECT COUNT(*) FROM votes WHERE election_id = e.election_id)               AS ballots,
       (SELECT COUNT(*) FROM voter_participation WHERE election_id = e.election_id) AS participants
FROM elections e;

-- 10. Latest audit trail
SELECT created_at, actor_type, actor_id, action, details
FROM audit_logs ORDER BY log_id DESC LIMIT 20;
