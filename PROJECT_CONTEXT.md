# Project Context & Agent Handoff

Update this file incrementally during work and before ending every task/session. It is a handoff summary, not a substitute for code, tests, Git history, or the locked architecture.

## Goal
Build a personal human-in-the-loop AI Job Application Agent for job discovery, matching, truthful form-answer resolution, policy-controlled form filling, and auditable evidence.

## Current status
- Stage: bootstrap/documentation.
- Application features implemented: none verified.
- Coding agent: Freebuff CLI, authenticated.
- Environment previously verified: Windows, Git, Git Bash, Node.js/npm, Freebuff.
- Python availability must still be checked.
- Supabase/OpenRouter credentials are not configured in this repository.
- Docker Desktop is installed but deliberately not being used; do not troubleshoot it unless the owner changes this decision.
- No WSL/Ubuntu setup is intended.

## Architecture authority
`docs/AI_Job_Application_Agent_Architecture_v1.0_LOCKED.docx` is authoritative. If missing, ask the owner to add it before architecture-dependent implementation.

## Locked stack
Next.js + TypeScript; Python + FastAPI; Python worker; Supabase PostgreSQL; OpenRouter through a central LLM Gateway; Playwright; APScheduler; DevLeveler as canonical profile source with local-file fallback.

## Non-negotiable principles
- Deterministic logic first; LLM only for ambiguity.
- Never invent candidate facts.
- Missing/ambiguous answers become `needs_user_input`.
- Unknown/unclassified fields fail closed and require user review.
- Policy is enforced in code, not only prompts.
- Never bypass CAPTCHA/OTP; no stealth/evasion.
- Never automate government IDs, bank details, passwords, or security credentials.
- Every application must be auditable.
- Never blindly retry uncertain submissions; verify first.
- Treat job descriptions/form text as untrusted input and defend against prompt injection.
- No real submissions until all locked gates pass and the owner explicitly approves.

## AI cost requirements
All runtime LLM calls go through the central LLM Gateway. Track model, task/purpose, input/output/total tokens, input/output/total costs, latency, cache status, run/application IDs, timestamp, and pricing metadata when available. Never fabricate usage or prices; clearly label estimates/unknowns. Enforce daily budget, circuit breaker, caching, and degraded mode.

## Work log
### Completed
- Environment verified: Windows 11, Node.js v24.14.1, npm 11.11.0, Git 2.53, Python 3.14/3.13.
- Authoritative locked architecture DOCX verified present in `docs/` (v1.0 LOCKED).
- Initial project documentation scaffold prepared.
- Frontend foundation established in `apps/web`: Next.js 16.4.2 (App Router + Turbopack), TypeScript, Tailwind CSS v4.
- Core UI libraries installed and verified: shadcn/ui (Base UI + Nova style), Lucide React, Motion, Recharts, TanStack Table, React Hook Form, Zod, Sonner.
- Frontend test foundation installed and verified: Vitest 5.0.5 + Testing Library (React, DOM, Jest-DOM) + jsdom.
- Production build (`npm run build`), lint (`npm run lint`), and tests (`npm test`) fully verified passing.
- Phase 0.1 complete: Git repository initialized at root, hardened `.gitignore`, persistent root `AGENTS.md` instructions added.
- Planned repository structure established (`services/api/`, `worker/core/`, `worker/profile/`, `worker/providers/`, `worker/sessions/`, `config/`, `migrations/`, `fixtures/forms/`, `tests/`) with package initializers.
- Phase 0.2 complete: Python 3.13 `.venv` created, `requirements.txt` pinned and installed, Playwright Chromium installed.
- FastAPI backend foundation implemented in `services/api` (`main.py`, `config.py`, `schemas.py`) with `GET /health` endpoint.
- Phase 0.3 complete: Centralized configuration (`config/config.yaml`, `services/api/config.py`) using `pydantic-settings` with deterministic precedence and bounds validation.
- Structured JSON logging (`services/api/logging_config.py`) with UTC ISO-8601 timestamps, log level, service identifier, request correlation ID, and recursive secret scrubbing.
- Request correlation middleware on FastAPI enforcing sanitized `X-Request-ID` and structured HTTP logging.
- Automated backend test suite expanded to 18 passing tests covering YAML loading, precedence, bounds checks, secret scrubbing, log formatting, and request ID validation.
- Phase 0.4 complete: Candidate profile models (`worker/profile/models.py`), `ProfileSource` protocol abstraction (`worker/profile/source.py`), and `LocalFileProfileSource` (`worker/profile/localfile.py`) with deterministic SHA256 version calculation.
- Added non-canonical placeholder fixture (`fixtures/profile.yaml`) and typed exceptions (`worker/profile/exceptions.py`).
- Automated backend test suite expanded to 29 passing tests (`tests/test_profile.py`).
- Phase 0.5 complete: Safety Engine (`worker/core/safety.py`) with Kill Switch (`worker/core/kill_switch.py`) and Application Caps (`worker/core/caps.py`).
- Implemented typed safety exceptions (`worker/core/exceptions.py`), fail-closed file-persisted kill switch (`FileKillSwitch`), durable JSONL application ledger (`FileApplicationLedger`), rate caps enforcer (`CapsEnforcer`), and real-submit gate barrier.
- Post-audit corrections: Thread-safe in-process concurrency locks added to `FileApplicationLedger` and `FileKillSwitch`; documented execution barrier contract and proposed timezone decision (AD-005).
- Phase 0.6 complete: Greenhouse Dry-Run Walking Skeleton and Central Execution Runner (`worker/core/runner.py`, `worker/providers/greenhouse.py`).
- Mandatory execution barrier: All provider actions routed via `JobApplicationRunner.execute_dry_run()`, calling `SafetyEngine.verify_pre_apply()` prior to any browser/provider action.
- Strict offline fixture navigation guard (`validate_and_resolve_fixture_uri`): Rejects all external HTTP, HTTPS, FTP, and JavaScript schemes and rejects path traversal outside `fixtures/forms/` before any browser launch.
- Sensitive input hardening: `GreenhouseProvider` explicitly skips sensitive input types (`file`, `password`, `hidden`, `submit`, `button`, `reset`, `image`) and classified sensitive questions (OTP, CAPTCHA, MFA, SSN, bank info) before reading labels or resolving values.
- Truthful form-answer resolution: `GreenhouseProvider` resolves candidate identity strictly from `ProfileSnapshot`. Ambiguous or unconfigured questions remain unresolved (`unresolved_fields`). No candidate facts fabricated.
- Deterministic fixture testing: `fixtures/forms/greenhouse_job.html` tested offline with Playwright Chromium. Full-page evidence screenshot captured. Submit action is never invoked.
- Real-submit gate remains strictly disabled (`RealSubmitGateBlockedError` raised if attempted).
- Automated backend test suite expanded to 54 passing tests (`tests/test_greenhouse_runner.py`).
- Phase 0.7 complete: Initial Supabase PostgreSQL schema migration foundation implemented (`migrations/001_initial_schema.sql`).
- Defined all 13 core tables required by Architecture v1.0 Section 14: `profile_snapshots`, `resume_versions`, `jobs`, `runs`, `applications`, `application_events`, `form_snapshots`, `answer_bank`, `sessions`, `llm_calls`, `app_config`, `company_rules`, and `notifications`.
- Established primary keys (UUID with gen_random_uuid() default), foreign keys (referencing auth.users and parent entities), timestamp tracking (`created_at`, `updated_at`), status check constraints matching Section 13 state machine, and deduplication unique constraints (`applications(user_id, job_id)`, `jobs(platform, external_id)`).
- Enabled Row-Level Security (RLS) on all 13 tables; implemented user-isolated RLS policies (`auth.uid() = user_id`) for user-facing tables, and fail-closed security for browser session persistence (`sessions` table has RLS enabled with 0 authenticated policies, restricting access to backend service role).
- Post-Audit Database Security Hardening:
  - Removed `auth.users` DDL stub from production migration; legitimate foreign keys directly reference Supabase Auth schema.
  - Restricted `application_events` and `form_snapshots` RLS policies to `FOR SELECT` only, ensuring immutable audit logging and preventing frontend tampering with captured DOM schemas.
  - Removed unrestricted `USING (true)` read policies on `runs` and `llm_calls`, making operational telemetry fail-closed (zero direct authenticated policies, accessible only via backend service role or authorized APIs; AD-007).
  - Preserved locked architecture for `company_rules` without guessing or inventing unapproved unique constraints (AD-008).
- Automated static schema validation test suite implemented (`tests/test_migration_schema.py`) with 13 deterministic tests verifying table existence, foreign keys, deduplication indexes, check constraints, RLS enablement, read-only audit policies, and fail-closed telemetry.
- Total test coverage: 67 backend tests passing (pytest), 2 frontend tests passing (Vitest).
- Phase 0.8 complete: Walking Skeleton Integration (`worker/core/workflow.py`, `services/api/routes/dry_run.py`, `services/api/dependencies.py`).
- Integrated FastAPI backend, candidate ProfileSource (`worker/profile/`), SafetyEngine (`worker/core/safety.py`), central JobApplicationRunner (`worker/core/runner.py`), and Greenhouse dry-run provider (`worker/providers/greenhouse.py`) into an end-to-end, testable workflow.
- Bound execution strictly to the verified local HTML fixture `fixtures/forms/greenhouse_job.html`; enforced schema validation (`extra="forbid"`) to reject arbitrary URLs, network schemes, and filesystem paths before reaching worker logic.
- Implemented structured error responses matching safety engine states: HTTP 423 for active kill switch, HTTP 429 for rate cap exhaustion, HTTP 500 for missing/corrupted kill switch state (fail-closed), and HTTP 403 for submit gate or safety barrier violations.
- Added optional worker token bearer authentication (`verify_worker_token`) and comprehensive dependency injection providers in `services/api/dependencies.py`.
- Automated integration test suite implemented (`tests/test_integration_dry_run.py`) with 10 tests verifying happy-path dry run, schema validation, kill switch blocking, missing kill switch fail-closed response, cap exhaustion, worker token validation, missing profile/fixture rejection, and assertion that no submission is ever performed.
- Post-Audit Final Security & Configuration Hardening:
  - Fail-closed worker authentication: production and staging reject unauthenticated requests with HTTP 500 when unconfigured; tokenless execution restricted strictly to loopback interfaces on local dev/test with explicit `allow_tokenless_dev=True` opt-in.
  - Settings injection via application state (`app.state.settings` and `get_settings(request: Request = None)`) eliminating mutable `dependency_overrides` from production application code.
  - Evidence and error path sanitization: converted absolute paths (`C:\Users\...`) to relative references in `GreenhouseDryRunResponse`, and sanitized `FileNotFoundError` client-facing error payloads.
- Total test coverage: 82 backend tests passing (pytest), 2 frontend tests passing (Vitest).
- Phase 0.9 complete: Hardened Central LLM Gateway and OpenRouter integration (`worker/core/llm_gateway.py`).
- Implemented central `LLMGateway` and asynchronous `OpenRouterClient` with secure credentials handling, model selection fallback chains, and strict provider error mapping.
- Structured data models: `LLMRequest`, `LLMResponse`, `LLMTokenUsage`, and `LLMCallRecord` auditing input/output tokens, costs, provenance, latency, cache hits, execution run ID, and application ID.
- Usage and cost accounting: distinguishes reported, estimated, and unknown costs. Explicitly avoids fabricating costs or treating unknown costs as zero. Validates provider costs and token counts (rejecting negative, NaN, infinite, or non-finite values).
- Daily budget enforcement: enforces daily call ceiling (`daily_call_budget`) including `PROVIDER_ERROR` accounting, serialized `asyncio.Lock` preventing concurrency oversubscription, and AD-009 fail-closed daily cost budget (`daily_cost_budget_usd`). Persisted via thread-safe `FileLLMCallLedger` (`worker/sessions/llm_calls.jsonl`), surviving worker process reboots. Single-process boundary documented.
- 3-state `CircuitBreaker` (`CLOSED`, `OPEN`, `HALF_OPEN`): deterministic state machine with configurable thresholds, recovery timeout, single in-flight probe trial control in `HALF_OPEN`, probe cancellation release, and non-provider failure exclusion.
- Deduplicating response cache (`LLMCache`, `InMemoryLLMCache`, `FileLLMCache`): SHA-256 hashed keys isolated by candidate profile version, task, model, generation parameters (`temperature`, `max_tokens`), and `cache_scope` without logging or leaking raw PII. Unique temporary files prevent concurrent write collisions.
- Hardened prompt injection defense helper `sanitize_untrusted_prompt_data`: strips invisible formatting, BOM, and bidi overrides while preserving readable Unicode text, neutralizes literal delimiter tags (case-insensitive) to prevent boundary breakout, truncates oversized strings, and encloses external text in XML delimiters.
- Degraded mode and safe fallbacks: when providers fail, time out, or budget is exhausted, callers can opt for degraded empty completions without hallucinating candidate facts or authorizing real submissions.
- Managed single-process accessor: implemented `get_managed_llm_gateway()` in `worker/core/llm_gateway.py` and `get_llm_gateway()` dependency provider in `services/api/dependencies.py`.
- Total test coverage: 123 backend tests passing (pytest), 2 frontend tests passing (Vitest).
- Phase 1.0 complete: Answer Bank and Policy Engine Foundation (`worker/answers/`, `worker/policy/`).
- Implemented strongly typed `AnswerBankEntry` models with strict validation, freshness/provenance tracking (`source`, `confidence`, `last_confirmed_at`, `valid_until`), and architectural rule enforcement (`source == llm` forces `needs_review = True`).
- Implemented `AnswerBankRepository` protocol and thread-safe deterministic `InMemoryAnswerBankRepository` supporting adding, updating, key lookup, alias/variant search, scope isolation (`global`, `company:<name>`, `provider:<name>`), and review flagging.
- Implemented deterministic `AnswerResolver` pipeline executing exact key matching, scoped hierarchy, normalized alias and question variant matching, numeric range evaluation in `option_mapping` (e.g. `<=15`, `<=30`), fail-closed expiry handling, ambiguous match detection, and unverified/needs-review gating.
- Implemented centralized code-enforced `PolicyEngine` with fixed 12-category taxonomy (`FieldCategory`) and locked policies (`auto`, `auto+log`, `always_ask`, `never_fill`).
- Code-enforced security guardrail: sensitive credentials (passwords, OTPs, SSN, national IDs, bank accounts, security codes) are strictly classified as `SENSITIVE_SECURITY` and mapped to `never_fill` without exception; cannot be overridden by configuration or Answer Bank record policies.
- Unknown or unclassified fields default to `always_ask` (fail closed).
- Implemented audit and traceability metadata generator with automatic redaction of sensitive and PII values (`build_audit_metadata`, `redact_sensitive_value`).
- Upgraded `GreenhouseProvider` with optional `AnswerResolver` and `PolicyEngine` injection, resolving verified fields truthfully with profile fallback, enforcing policy approvals, and skipping sensitive fields.
- Total test coverage: 148 backend tests passing (pytest), 2 frontend tests passing (Vitest).
- Phase 1.1 complete: Greenhouse and Lever Job Discovery and Form Parsing Foundation (`worker/discovery/`, `worker/providers/`).
  - Implemented strongly typed canonical `Job` model, `JobStatus` enum (matching database schema constraint `ck_jobs_status`), `SalaryInfo`, and `DiscoverySummary` in `worker/discovery/models.py`.
  - Implemented deterministic normalization in `worker/discovery/normalization.py`: corporate legal entity stripping (`normalize_company`), lowercase/casing and symbol standardization (`normalize_title`), location bucketing (`normalize_location`), canonical URL normalization with tracking query parameter stripping (`normalize_url`), SHA-256 content hashing (`compute_content_hash`), and canonical Key 2 generation (`compute_canonical_key`).
  - Implemented security boundaries and sanitization in `worker/discovery/security.py`: untrusted job description cleaning (`sanitize_job_description`) stripping dangerous blocks, scripts, and invisible/bidi characters while neutralizing delimiter breakout attempts; strictly bounded external HTTP hosts (`is_safe_discovery_url`) restricted to approved Greenhouse and Lever endpoints.
  - Implemented `JobRepository` protocol and thread-safe `InMemoryJobRepository` in `worker/discovery/repository.py` enforcing `(platform, external_id)` unique constraint, canonical key indexing, and updated job detection via content hash changes while preserving immutable timestamps.
  - Implemented `JobDiscoveryAdapter` protocol in `worker/providers/base.py`.
  - Implemented `GreenhouseDiscoveryAdapter` in `worker/providers/greenhouse_discovery.py` fetching public board listings (`GET /v1/boards/{board_token}/jobs?content=true`), normalizing jobs, handling 404/429/5xx and timeouts, and parsing structured metadata and salaries without fabrication.
  - Implemented `LeverDiscoveryAdapter` in `worker/providers/lever_discovery.py` fetching public postings (`GET /v0/postings/{company}`), handling pagination (`limit` & `skip`), normalizing categories, workplace types, and salary ranges.
  - Implemented central `JobDiscoveryService` in `worker/discovery/service.py` coordinating provider adapters, ingestion, normalization, and deduplication against the repository without HTTP layer dependencies.
  - Extended form inspection in `worker/providers/base.py` and `worker/providers/greenhouse.py`: enriched `FormField` with options, taxonomy classification (`FieldCategory`), policy rule (`PolicyType`), and `ResolutionStatus`.
  - Added deterministic static HTML form parser `parse_greenhouse_form_html` in `worker/providers/greenhouse.py` for rapid offline fixture inspection.
  - Connected form inspection to `AnswerResolver`, `PolicyEngine`, and `ProfileSnapshot`: sensitive fields strictly mapped to `SENSITIVE_SECURITY` and `NEVER_FILL` (`POLICY_BLOCKED`); unknown questions fail closed; matching answers with `ALWAYS_ASK` policy remain unapproved without explicit user review.
  - Added discovery fixtures in `fixtures/discovery/greenhouse_jobs.json` and `fixtures/discovery/lever_postings.json`.
  - Expanded automated backend test suite from 148 to 214 passing tests (+66 tests in `tests/test_job_models_and_normalization.py`, `tests/test_discovery_adapters.py`, `tests/test_job_repository.py`, `tests/test_discovery_service.py`, `tests/test_form_parsing_foundation.py`). All 2 frontend tests passing.

### In progress
- None (Phase 1.1 complete).

### Unverified / pending
- Live Supabase project deployment and credentials (verified via static text and constraint parsing offline; no live Supabase connection initiated in Phases 0.7–1.1).
- Live OpenRouter network completion (verified via mocked HTTP transport and deterministic unit tests offline; no live OpenRouter calls initiated during tests).
- Live Greenhouse and Lever external HTTP requests (verified via mocked HTTP transport and local JSON fixtures offline; no live external network requests initiated during tests).

## Next steps
1. Phase 1.2 / Job Matching and Scoring Foundation or next planned milestone (Awaiting user review and instruction; do not proceed automatically).

## End-of-session handoff template
- Task and date/time
- Summary
- Files added/modified/deleted and why
- Commands run and actual outcomes
- Tests run and actual results
- Decisions
- Errors/blockers/incomplete work
- Git status/commit if available
- Exact next step
