-- ==============================================================================
-- AI Job Application Agent — Additive Performance Indexes (Phase 2.2)
-- Migration: 002_performance_indexes.sql
-- Authority: docs/AI_Job_Application_Agent_Architecture_v1.0_LOCKED.docx (Section 14)
-- Target Engine: Supabase PostgreSQL (PostgreSQL 15+)
-- ==============================================================================

-- Preserves existing schema and data.
-- Does NOT alter locked decisions AD-005, AD-008, or AD-009.

-- 1. Applications query optimization
-- Optimize approval queue queries and status filtering per user
CREATE INDEX IF NOT EXISTS idx_applications_user_status ON applications(user_id, status);

-- Optimize chronological ordering and pagination for applications list
CREATE INDEX IF NOT EXISTS idx_applications_created_desc ON applications(created_at DESC);

-- 2. Jobs query optimization
-- Optimize discovery freshness and 24h age filter
CREATE INDEX IF NOT EXISTS idx_jobs_posted_at_desc ON jobs(posted_at DESC NULLS LAST);

-- Optimize company deduplication and cooldown lookups
CREATE INDEX IF NOT EXISTS idx_jobs_company_lower ON jobs(lower(company));

-- 3. Answer Bank query optimization
-- Fast key and scope lookup per candidate
CREATE INDEX IF NOT EXISTS idx_answer_bank_user_key_scope_lower ON answer_bank(user_id, lower(key), lower(scope));

-- 4. Application Events audit history ordering
-- Fast chronological event playback per application
CREATE INDEX IF NOT EXISTS idx_application_events_app_time ON application_events(application_id, timestamp ASC);

-- 5. Runs monitoring
-- Fast query for incomplete or interrupted runs
CREATE INDEX IF NOT EXISTS idx_runs_interrupted ON runs(interrupted) WHERE interrupted = true;
