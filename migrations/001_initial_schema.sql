-- ==============================================================================
-- AI Job Application Agent — Initial Database Schema Migration
-- Migration: 001_initial_schema.sql
-- Authority: docs/AI_Job_Application_Agent_Architecture_v1.0_LOCKED.docx (Section 14)
-- Target Engine: Supabase PostgreSQL (PostgreSQL 15+)
-- ==============================================================================

-- Note: Foreign keys reference Supabase-managed auth.users(id).
-- The migration assumes the Supabase Auth system schema exists.

-- ==============================================================================
-- 1. profile_snapshots: Cached DevLeveler or local YAML candidate profiles
-- ==============================================================================
CREATE TABLE IF NOT EXISTS profile_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    profile_version VARCHAR(64) NOT NULL,
    schema_version VARCHAR(32) NOT NULL DEFAULT '1.0',
    profile_json JSONB NOT NULL,
    synced_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    CONSTRAINT uq_profile_snapshots_user_version UNIQUE (user_id, profile_version)
);

CREATE INDEX IF NOT EXISTS idx_profile_snapshots_user_id ON profile_snapshots(user_id);
CREATE INDEX IF NOT EXISTS idx_profile_snapshots_version ON profile_snapshots(profile_version);

-- ==============================================================================
-- 2. resume_versions: Resume variants per role family (e.g. backend, fullstack)
-- ==============================================================================
CREATE TABLE IF NOT EXISTS resume_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    file_ref TEXT NOT NULL,
    role_family VARCHAR(100) NOT NULL,
    version VARCHAR(32) NOT NULL,
    active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

CREATE INDEX IF NOT EXISTS idx_resume_versions_user_role ON resume_versions(user_id, role_family);

-- ==============================================================================
-- 3. jobs: Normalised and deduplicated job listings across platforms
-- ==============================================================================
CREATE TABLE IF NOT EXISTS jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    platform VARCHAR(50) NOT NULL,
    external_id VARCHAR(255) NOT NULL,
    canonical_key VARCHAR(255) NOT NULL,
    company VARCHAR(255) NOT NULL,
    title VARCHAR(255) NOT NULL,
    url TEXT NOT NULL,
    description TEXT,
    posted_at TIMESTAMPTZ,
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    content_hash VARCHAR(64) NOT NULL,
    embedding JSONB,
    score NUMERIC(5,2),
    score_breakdown JSONB DEFAULT '{}'::jsonb,
    status VARCHAR(50) NOT NULL DEFAULT 'DISCOVERED',
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    CONSTRAINT uq_jobs_platform_external UNIQUE (platform, external_id),
    CONSTRAINT ck_jobs_status CHECK (
        status IN ('DISCOVERED', 'MATCHED', 'APPLIED', 'REJECTED', 'EXPIRED', 'IGNORED', 'DUPLICATE')
    )
);

CREATE INDEX IF NOT EXISTS idx_jobs_canonical_key ON jobs(canonical_key);
CREATE INDEX IF NOT EXISTS idx_jobs_content_hash ON jobs(content_hash);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_company ON jobs(company);

-- ==============================================================================
-- 4. runs: Worker execution session summaries
-- ==============================================================================
CREATE TABLE IF NOT EXISTS runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    started_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    ended_at TIMESTAMPTZ,
    jobs_found INTEGER NOT NULL DEFAULT 0,
    applied INTEGER NOT NULL DEFAULT 0,
    skipped INTEGER NOT NULL DEFAULT 0,
    failed INTEGER NOT NULL DEFAULT 0,
    interrupted BOOLEAN NOT NULL DEFAULT false,
    llm_calls INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

CREATE INDEX IF NOT EXISTS idx_runs_started_at ON runs(started_at);

-- ==============================================================================
-- 5. applications: End-to-end application lifecycle and state transitions
-- ==============================================================================
CREATE TABLE IF NOT EXISTS applications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id UUID NOT NULL REFERENCES jobs(id) ON DELETE RESTRICT,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    run_id UUID REFERENCES runs(id) ON DELETE SET NULL,
    profile_version VARCHAR(64) NOT NULL,
    resume_version VARCHAR(32),
    autonomy_level VARCHAR(10) NOT NULL DEFAULT 'L0',
    status VARCHAR(50) NOT NULL DEFAULT 'DISCOVERED',
    fields_filled JSONB DEFAULT '{}'::jsonb,
    evidence_ref TEXT,
    idempotency_key VARCHAR(128),
    error TEXT,
    applied_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    CONSTRAINT uq_applications_idempotency UNIQUE (idempotency_key),
    CONSTRAINT uq_applications_user_job UNIQUE (user_id, job_id),
    CONSTRAINT ck_applications_autonomy CHECK (
        autonomy_level IN ('L0', 'L1', 'L2', 'L3')
    ),
    CONSTRAINT ck_applications_status CHECK (
        status IN (
            'DISCOVERED', 'MATCHED', 'ELIGIBLE', 'READY', 'AWAITING_APPROVAL',
            'FILLING', 'NEEDS_USER_INPUT', 'BLOCKED', 'SUBMITTING',
            'UNCERTAIN', 'VERIFYING', 'APPLIED', 'DRY_RUN_DONE',
            'SKIPPED', 'REJECTED', 'EXPIRED', 'DUPLICATE', 'FAILED'
        )
    )
);

CREATE INDEX IF NOT EXISTS idx_applications_user_id ON applications(user_id);
CREATE INDEX IF NOT EXISTS idx_applications_job_id ON applications(job_id);
CREATE INDEX IF NOT EXISTS idx_applications_status ON applications(status);
CREATE INDEX IF NOT EXISTS idx_applications_run_id ON applications(run_id);
CREATE INDEX IF NOT EXISTS idx_applications_applied_at ON applications(applied_at);

-- ==============================================================================
-- 6. application_events: Comprehensive append-only audit trail
-- ==============================================================================
CREATE TABLE IF NOT EXISTS application_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id UUID NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    event_type VARCHAR(100) NOT NULL,
    payload JSONB DEFAULT '{}'::jsonb,
    reason TEXT,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

CREATE INDEX IF NOT EXISTS idx_application_events_app_id ON application_events(application_id);
CREATE INDEX IF NOT EXISTS idx_application_events_type ON application_events(event_type);
CREATE INDEX IF NOT EXISTS idx_application_events_timestamp ON application_events(timestamp);

-- ==============================================================================
-- 7. form_snapshots: Sanitised form DOM structure per application
-- ==============================================================================
CREATE TABLE IF NOT EXISTS form_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id UUID NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    provider VARCHAR(50) NOT NULL,
    form_schema JSONB NOT NULL DEFAULT '{}'::jsonb,
    html_ref TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

CREATE INDEX IF NOT EXISTS idx_form_snapshots_app_id ON form_snapshots(application_id);
CREATE INDEX IF NOT EXISTS idx_form_snapshots_provider ON form_snapshots(provider);

-- ==============================================================================
-- 8. answer_bank: Verified recurring questions and policy-controlled answers
-- ==============================================================================
CREATE TABLE IF NOT EXISTS answer_bank (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    key VARCHAR(255) NOT NULL,
    category VARCHAR(100) NOT NULL,
    aliases JSONB DEFAULT '[]'::jsonb,
    variants JSONB DEFAULT '[]'::jsonb,
    type VARCHAR(50) NOT NULL DEFAULT 'text',
    value TEXT NOT NULL,
    option_mapping JSONB DEFAULT '{}'::jsonb,
    scope VARCHAR(50) NOT NULL DEFAULT 'global',
    policy VARCHAR(50) NOT NULL DEFAULT 'always_ask',
    source VARCHAR(50) NOT NULL DEFAULT 'user',
    confidence NUMERIC(3,2) NOT NULL DEFAULT 1.00,
    needs_review BOOLEAN NOT NULL DEFAULT false,
    last_confirmed_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    valid_until TIMESTAMPTZ,
    embedding JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    CONSTRAINT uq_answer_bank_user_key_scope UNIQUE (user_id, key, scope),
    CONSTRAINT ck_answer_bank_policy CHECK (
        policy IN ('always_ask', 'auto_fill', 'review_required')
    ),
    CONSTRAINT ck_answer_bank_type CHECK (
        type IN ('text', 'select', 'boolean', 'number', 'date', 'textarea')
    ),
    CONSTRAINT ck_answer_bank_scope CHECK (
        scope IN ('global', 'company', 'provider')
    )
);

CREATE INDEX IF NOT EXISTS idx_answer_bank_user_id ON answer_bank(user_id);
CREATE INDEX IF NOT EXISTS idx_answer_bank_category ON answer_bank(category);
CREATE INDEX IF NOT EXISTS idx_answer_bank_needs_review ON answer_bank(needs_review);

-- ==============================================================================
-- 9. sessions: Browser session metadata (sensitive; no frontend access)
-- ==============================================================================
CREATE TABLE IF NOT EXISTS sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    platform VARCHAR(50) NOT NULL,
    local_profile_ref TEXT NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'ACTIVE',
    last_verified_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    CONSTRAINT uq_sessions_platform UNIQUE (platform),
    CONSTRAINT ck_sessions_status CHECK (
        status IN ('ACTIVE', 'EXPIRED', 'LOCKED', 'INVALID')
    )
);

CREATE INDEX IF NOT EXISTS idx_sessions_platform ON sessions(platform);

-- ==============================================================================
-- 10. llm_calls: Runtime AI audit trail, budget tracking, and latency metrics
-- ==============================================================================
CREATE TABLE IF NOT EXISTS llm_calls (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID REFERENCES runs(id) ON DELETE SET NULL,
    task VARCHAR(100) NOT NULL,
    model VARCHAR(100) NOT NULL,
    tokens JSONB NOT NULL DEFAULT '{"input": 0, "output": 0, "total": 0}'::jsonb,
    cost_usd NUMERIC(10,6) DEFAULT 0.000000,
    latency_ms INTEGER NOT NULL,
    cache_hit BOOLEAN NOT NULL DEFAULT false,
    outcome VARCHAR(50) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

CREATE INDEX IF NOT EXISTS idx_llm_calls_run_id ON llm_calls(run_id);
CREATE INDEX IF NOT EXISTS idx_llm_calls_task ON llm_calls(task);
CREATE INDEX IF NOT EXISTS idx_llm_calls_created_at ON llm_calls(created_at);

-- ==============================================================================
-- 11. app_config: Persisted runtime controls and policy overrides
-- ==============================================================================
CREATE TABLE IF NOT EXISTS app_config (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    kill_switch JSONB NOT NULL DEFAULT '{"active": false}'::jsonb,
    caps JSONB NOT NULL DEFAULT '{"global_per_day": 50, "per_company_per_day": 3}'::jsonb,
    autonomy_per_provider JSONB NOT NULL DEFAULT '{"greenhouse": "L0", "lever": "L0"}'::jsonb,
    schedule JSONB NOT NULL DEFAULT '{"active_hours": "09:00-23:00", "timezone": "Asia/Kolkata"}'::jsonb,
    thresholds JSONB NOT NULL DEFAULT '{"match_threshold": 75}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    CONSTRAINT uq_app_config_user UNIQUE (user_id)
);

CREATE INDEX IF NOT EXISTS idx_app_config_user_id ON app_config(user_id);

-- ==============================================================================
-- 12. company_rules: Employer blocklist, cooldowns, and custom thresholds
-- ==============================================================================
CREATE TABLE IF NOT EXISTS company_rules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    company VARCHAR(255) NOT NULL,
    rule_type VARCHAR(50) NOT NULL,
    value JSONB DEFAULT '{}'::jsonb,
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    CONSTRAINT ck_company_rules_type CHECK (
        rule_type IN ('BLOCKLIST', 'COOLDOWN', 'CUSTOM_THRESHOLD', 'ALWAYS_ASK')
    )
);

CREATE INDEX IF NOT EXISTS idx_company_rules_user_company ON company_rules(user_id, company);
CREATE INDEX IF NOT EXISTS idx_company_rules_rule_type ON company_rules(rule_type);

-- ==============================================================================
-- 13. notifications: User alert feed and asynchronous approval requests
-- ==============================================================================
CREATE TABLE IF NOT EXISTS notifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    type VARCHAR(100) NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    sent_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    acknowledged_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_notifications_user_id ON notifications(user_id);
CREATE INDEX IF NOT EXISTS idx_notifications_type ON notifications(type);
CREATE INDEX IF NOT EXISTS idx_notifications_sent_at ON notifications(sent_at);

-- ==============================================================================
-- ROW-LEVEL SECURITY (RLS) POLICIES
-- ==============================================================================

-- 1. Enable RLS unconditionally on all 13 tables
ALTER TABLE profile_snapshots ENABLE ROW LEVEL SECURITY;
ALTER TABLE resume_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE applications ENABLE ROW LEVEL SECURITY;
ALTER TABLE application_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE form_snapshots ENABLE ROW LEVEL SECURITY;
ALTER TABLE answer_bank ENABLE ROW LEVEL SECURITY;
ALTER TABLE sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE llm_calls ENABLE ROW LEVEL SECURITY;
ALTER TABLE app_config ENABLE ROW LEVEL SECURITY;
ALTER TABLE company_rules ENABLE ROW LEVEL SECURITY;
ALTER TABLE notifications ENABLE ROW LEVEL SECURITY;

-- 2. User-Scoped Isolation Policies (authenticated user owns their records)
CREATE POLICY "Users can manage their own profile snapshots"
    ON profile_snapshots FOR ALL TO authenticated
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can manage their own resume versions"
    ON resume_versions FOR ALL TO authenticated
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can manage their own applications"
    ON applications FOR ALL TO authenticated
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can manage their own answer bank entries"
    ON answer_bank FOR ALL TO authenticated
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can manage their own app config"
    ON app_config FOR ALL TO authenticated
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can manage their own company rules"
    ON company_rules FOR ALL TO authenticated
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can manage their own notifications"
    ON notifications FOR ALL TO authenticated
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

-- 3. Application Dependent Child Policies (inheriting application ownership)
CREATE POLICY "Users can view events for their applications"
    ON application_events FOR SELECT TO authenticated
    USING (EXISTS (
        SELECT 1 FROM applications a
        WHERE a.id = application_events.application_id AND a.user_id = auth.uid()
    ));

CREATE POLICY "Users can view form snapshots for their applications"
    ON form_snapshots FOR SELECT TO authenticated
    USING (EXISTS (
        SELECT 1 FROM applications a
        WHERE a.id = form_snapshots.application_id AND a.user_id = auth.uid()
    ));

-- 4. Shared Reference Read-Only Policies
CREATE POLICY "Authenticated users can view discovered jobs"
    ON jobs FOR SELECT TO authenticated
    USING (true);

-- 5. Strict Zero-Access / Fail-Closed Tables
-- Note: 'sessions', 'runs', and 'llm_calls' tables have Row-Level Security ENABLED,
-- but have NO policy granted to 'authenticated' or 'anon'.
-- Direct frontend access is denied by default.
-- Browser session state, worker execution runs, and LLM telemetry are accessible
-- only via trusted backend/service_role operations or authorized backend APIs.
