-- 10_metrics_queries.sql
-- Example SQL queries to compute SLA / turnaround / backlog metrics

-- 1) Overall counts
SELECT
  COUNT(*) AS total_requests,
  SUM(CASE WHEN status = 'Done' THEN 1 ELSE 0 END) AS closed_requests,
  SUM(CASE WHEN status <> 'Done' THEN 1 ELSE 0 END) AS open_requests
FROM requests;

-- 2) Turnaround time (closed requests)
SELECT
  requester_team,
  AVG(julianday(completed_date) - julianday(request_date)) AS avg_turnaround_days
FROM requests
WHERE status = 'Done'
GROUP BY requester_team
ORDER BY avg_turnaround_days DESC;

-- 3) SLA breaches (example: breach when completed_date > due_date)
SELECT
  requester_team,
  COUNT(*) AS closed_requests,
  SUM(CASE WHEN completed_date > due_date THEN 1 ELSE 0 END) AS breached_requests,
  ROUND(100.0 * SUM(CASE WHEN completed_date > due_date THEN 1 ELSE 0 END) / COUNT(*), 2) AS breach_rate_pct
FROM requests
WHERE status = 'Done'
GROUP BY requester_team
ORDER BY breach_rate_pct DESC;

-- 4) Current backlog (open requests) + aging
SELECT
  requester_team,
  COUNT(*) AS open_requests,
  AVG(julianday('now') - julianday(request_date)) AS avg_age_days
FROM requests
WHERE status <> 'Done'
GROUP BY requester_team
ORDER BY open_requests DESC;
