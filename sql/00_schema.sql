-- 00_schema.sql
-- Simple schema for a stakeholder request tracker

DROP TABLE IF EXISTS requests;

CREATE TABLE requests (
  request_id TEXT PRIMARY KEY,
  request_date TEXT NOT NULL,
  requester_team TEXT NOT NULL,
  request_type TEXT NOT NULL,
  priority TEXT NOT NULL,
  channel TEXT,
  due_date TEXT NOT NULL,
  status TEXT NOT NULL,
  completed_date TEXT,
  estimated_hours REAL,
  actual_hours REAL
);
