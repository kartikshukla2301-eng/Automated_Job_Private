# Project Context & Agent Handoff

Update this file incrementally during work and before ending every task/session. It is a handoff summary, not a substitute for code, tests, Git history, or the locked architecture.

## Goal
Build a personal human-in-the-loop AI Job Application Agent for job discovery, matching, truthful form-answer resolution, policy-controlled form filling, and auditable evidence.

## Current status
- Stage: L0 Supervised Execution Certified (Phases 0.1 through 3.9 fully completed).
- Frontend: Fully functional, high-performance desktop cockpit in `apps/web/` (Next.js 16.4.2, TypeScript, Tailwind CSS v4, Lucide React). All 12 routes implemented with Premium Light Theme. 34 frontend tests passing (100%), ESLint clean (0 errors, 0 warnings), Next.js production build clean across all 17 routes.
- Backend API & Worker: Python 3.13 + FastAPI + Supabase PostgreSQL + centralized LLM Gateway + Playwright automation. 440 backend tests passing (100%).
- Safety & Gates: Real-Submit Gate permanently locked disabled (`real_submit_gate_enabled = False`); Stage S0 rate caps (2 applications/day active limit); zero password storage guarantee; file-backed emergency kill switch armed and operational.
- Environment: Native Windows 11 only (no Docker, no WSL, no Linux). Offline-resilient with zero external font download dependencies.

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

- Phase 1.2 complete: Intelligent Job Matching and Scoring Engine (`worker/matching/`).
  - Implemented strongly typed matching models in `worker/matching/models.py`: `MatchDecision` (`MATCH`, `BORDERLINE`, `REJECT`, `EXCLUDED`, `UNRESOLVED`), `MatchScoreBreakdown`, `MatchExplanation`, `CandidateJobPreferences`, `HardFilterResult`, `JobMatchRequest`, and `JobMatchResult`.
  - Implemented deterministic hard eligibility filters in `worker/matching/hard_filters.py`: evaluates job lifecycle status, max job age / freshness (24h default), duplicate & already-applied jobs, blocklisted companies & keywords, company cooldown (1 per 30d) & daily caps (2 per day), work mode & location alignment, employment type compatibility, experience & seniority ceilings, and minimum salary constraints. Invariant: missing fields never invented and never cause rejection unless strictly required by preferences; hard exclusions cannot be overridden by LLM or high scores.
  - Implemented explainable weighted scoring engine in `worker/matching/scoring.py` adhering strictly to Architecture Section 10 weights: Required skills 30%, Role relevance 20%, Experience fit 15%, Preferred skills 15%, Location/work mode 10%, Project evidence 10%. Features skill synonym normalization, token overlap role scoring, experience gap scaling, and tech stack evidence extraction from project portfolios.
  - Implemented local embedding provider abstraction in `worker/matching/embedding.py`: `EmbeddingProvider` protocol, `LocalSentenceTransformerEmbeddingProvider` (for local sentence-transformer models like `all-MiniLM-L6-v2`), `DeterministicFallbackEmbeddingProvider` (deterministic 384-d unit vector hashing fallback without external API calls or neural dependencies), and pure standard-library cosine similarity.
  - Implemented borderline review pipeline in `worker/matching/borderline.py` invoking central `LLMGateway`: triggered strictly when score falls within borderline band [55, 70]; applies prompt injection sanitization on untrusted job descriptions (`sanitize_untrusted_prompt_data`); validates strict structured output (`BorderlineLLMOutput`); bounded token usage; fails safe to deterministic decision if LLM call fails or returns malformed response; cannot override hard filters.
  - Implemented central `JobMatchingService` in `worker/matching/service.py`: coordinates end-to-end matching pipeline, executes batch matching with stable deterministic ranking, and updates job scores and statuses (`MATCHED` / `REJECTED`) in persistence via future-compatible `JobRepository.update_score()`.
  - Implemented deduplication safety classifier in `worker/matching/deduplication.py`: distinguishes Key 1 exact provider matches, Key 2 + 3 cross-platform identical matches, possible duplicates (same canonical key but distinct requisition descriptions preserved without losing openings), and distinct openings.
  - Total test coverage: 256 backend tests passing (pytest), 2 frontend tests passing (Vitest).

- Phase 1.3 complete: Application Lifecycle State Machine and Orchestration (`worker/application/`, `services/api/routes/applications.py`).
  - Implemented canonical `Application` and `ApplicationEvent` models in `worker/application/models.py` with all 18 statuses matching `ck_applications_status`, `AutonomyLevel` (`L0`-`L3`), and `ApprovalStatus`.
  - Implemented Section 13 central state machine in `worker/application/state_machine.py` with strict transition validation, typed exceptions, clock injection, and automatic audit event generation.
  - Implemented deterministic SHA-256 idempotency key generation in `worker/application/idempotency.py` bounded to 128 characters.
  - Implemented `ApplicationRepository` and `ApplicationEventRepository` protocols and thread-safe `InMemoryApplicationRepository` and `InMemoryApplicationEventRepository` in `worker/application/repository.py` enforcing `UNIQUE(user_id, job_id)` and `UNIQUE(idempotency_key)`.
  - Implemented central `ApplicationOrchestrator` in `worker/application/orchestrator.py` integrating discovery, matching, safety pre-apply barrier, human-in-the-loop approval gates, fail-closed crash recovery, and L0 dry-run execution without external submissions.
  - Implemented scoped FastAPI routes in `services/api/routes/applications.py` (`GET /{id}`, `GET /{id}/events`, `POST /{id}/approve`, `POST /{id}/reject`, `POST /{id}/execute-dry-run`).
  - Total test coverage: 287 backend tests passing (pytest), 2 frontend tests passing (Vitest).

- Phase 1.4 complete: Playwright Browser Runtime & Safe Form Execution Foundation (`worker/browser/`, `services/api/routes/applications.py`, `tests/`).
  - Implemented `BrowserManager` (`worker/browser/browser_manager.py`) and `BrowserSession` (`worker/browser/browser_session.py`) for on-demand Chromium lifecycle, cooperative session cancellation, and user session isolation.
  - Implemented `NavigationGuard` (`worker/browser/navigation_guard.py`) with origin allowlist (`boards.greenhouse.io`, `job-boards.greenhouse.io`, `jobs.lever.co`), anti-SSRF defenses (blocking private IPs, link-local, loopback, prohibited schemes), and bounded local fixture validation (`fixtures/forms/`).
  - Implemented `PageInspector` (`worker/browser/page_inspector.py`), `FieldDetector` (`worker/browser/field_detector.py`), and `LocatorResolver` (`worker/browser/locator_resolver.py`) with DOM and offline parser extraction, duplicate label disambiguation, semantic Playwright locator generation, and sensitive field classification.
  - Implemented `FillPlan` (`worker/browser/fill_plan.py`) and `ExecutionContext` (`worker/browser/execution_context.py`) integrating `ProfileSnapshot`, `AnswerResolver`, and `PolicyEngine` to classify fields into `AUTO_APPROVED`, `REQUIRES_USER_REVIEW`, `BLOCKED_BY_POLICY`, and `UNRESOLVED_MISSING`.
  - Implemented `EvidenceCollector` (`worker/browser/evidence.py`) capturing full-page inspection screenshots and metadata without storing raw sensitive credentials.
  - Implemented L0 dry-run safety invariant (`tests/test_l0_browser_safety.py`) verifying in live browser sessions that form inputs remain completely untouched in the DOM, with real submit disabled (`real_submit_gate_enabled=False`).
  - Implemented scoped FastAPI endpoints in `services/api/routes/applications.py`: `POST /api/v1/applications/{id}/inspect-form`, `GET /api/v1/applications/{id}/fill-plan`, and `GET /api/v1/applications/{id}/evidence`.
  - Added realistic offline Lever test fixture in `fixtures/forms/lever_job.html`.
  - Total test coverage: 317 backend tests passing (pytest), 2 frontend tests passing (Vitest).

- Phase 1.5 complete: Human-in-the-Loop & Operations Foundation (`worker/ops/`, `services/api/routes/ops.py`, `tests/`).
  - Implemented `ApprovalManager` (`worker/ops/approval.py`): user approval queue, server-side ownership verification, expiration TTL handling, and candidate missing answers workflow (`NEEDS_USER_INPUT` -> `FILLING`).
  - Implemented `TelegramNotificationService` (`worker/ops/telegram.py`): privacy-safe operational alerts and owner command parser (`/pause`, `/resume`, `/kill`, `/status`, `/approve`, `/reject`) with chat ID allowlist and mock adapter fallback.
  - Implemented `PersistentConfigManager` (`worker/ops/config_manager.py`): thread-safe JSON-persisted safety config for caps, cooldowns, autonomy levels, matching thresholds, and daily LLM budgets with strict bounds validation.
  - Implemented `ProviderHealthManager` (`worker/ops/provider_health.py`): failure counter tracking with auto-pause on 3 consecutive errors and isolated recovery.
  - Implemented `HeartbeatManager` (`worker/ops/heartbeat.py`): worker pulse and dead-man alert during IST active hours (09:00-23:00).
  - Implemented `ProviderCanaryRunner` (`worker/ops/canary.py`): fixture drift detection on Greenhouse and Lever forms without submitting or personal data.
  - Implemented `RunScheduler` (`worker/ops/scheduler.py`): single-run concurrency lock, IST active window enforcement, jitter delay, and catch-up discovery.
  - Implemented `MetricsAggregator` (`worker/ops/metrics.py`): truthful operational metrics derived from stored records.
  - Implemented `RealSubmitReadinessEvaluator` (`worker/ops/readiness.py`): non-executable evaluator checking the 8 locked architecture criteria while keeping `real_submit_gate_enabled = False` hardcoded.
  - Implemented scoped FastAPI routes in `services/api/routes/ops.py`.
  - Total test coverage: 350 backend tests passing (pytest), 2 frontend tests passing (Vitest).
- Phase 1.6 complete: Naukri Provider & Autonomy Ramp Foundation.
  - Implemented `NaukriSessionManager` managing authenticated session states, persistent cookie isolation, manual login verification, and strictly zero password storage.
  - Implemented `NaukriDiscoveryAdapter` for normalized job ingestion, content hashing, and cross-platform canonical deduplication.
  - Implemented `NaukriProvider` supporting Playwright-driven form inspection and L0 dry-run execution while rejecting real submissions.
  - Updated `NavigationGuard` and browser configurations to permit `naukri.com` and `www.naukri.com` domains.
  - Implemented `AutonomyController` managing staged autonomy progression (L0->L1->L2->L3) with strict promotion criteria (30 apps, >=98% accuracy, 0 sensitive errors, 0 duplicates) and automatic demotion on safety violation.
  - Implemented capacity stage evaluation (S0->S1) enforcing locked daily cap (2 applications/day).
  - Total test coverage: 364 backend tests passing (pytest), 2 frontend tests passing (Vitest).
- Phase 1.7 complete: Wellfound & Ashby Provider Adapters and Central Provider Registry.
  - Implemented `WellfoundSessionManager` managing persistent manual session cookies with password rejection.
  - Implemented `WellfoundDiscoveryAdapter` normalizing startup listings, compensation bounds, and already-applied flags.
  - Implemented `WellfoundProvider` supporting Playwright form inspection and L0 dry-run execution while rejecting real submits.
  - Implemented `AshbyDiscoveryAdapter` parsing Ashby boards and URL-based company identification.
  - Implemented `AshbyProvider` and `LeverProvider` supporting Playwright form inspection and L0 dry-run execution while rejecting real submits.
  - Updated `NavigationGuard`, `BrowserConfig`, and `ALLOWED_DISCOVERY_HOSTS` to permit Wellfound and Ashby domains.
  - Implemented central `ProviderRegistry` (`worker/providers/registry.py`) providing unified management across Greenhouse, Lever, Naukri, Wellfound, and Ashby.
  - Total test coverage: 377 backend tests passing (pytest), 2 frontend tests passing (Vitest).
- Phase 1.8 complete: Restricted LinkedIn Provider Foundation.
  - Implemented `LinkedInSessionManager` managing persistent manual session cookies in `worker/sessions/linkedin/cookies.json` with strict password rejection and 14-day expiry TTL.
  - Implemented `detect_security_checkpoint_or_wall` halting execution immediately upon encountering login walls (`/authwall`, `/login`) or CAPTCHA/bot challenges without stealth attempts.
  - Implemented `LinkedInDiscoveryAdapter` for normalized Easy Apply job ingestion, URL tracking parameter sanitization, and already-applied status detection.
  - Implemented `LinkedInProvider` supporting Playwright Easy Apply form inspection and L0 dry-run execution while rejecting real submissions.
  - Updated `NavigationGuard`, `BrowserConfig`, and `ALLOWED_DISCOVERY_HOSTS` to permit `linkedin.com` and `www.linkedin.com`.
  - Registered LinkedIn in `ProviderRegistry` and exported in `worker/providers/__init__.py`.
  - Enforced restricted provider autonomy in `AutonomyController` strictly capping LinkedIn at L1 autonomy and blocking promotion to L2 or L3.
  - Authored authoritative `docs/PROVIDER_STATUS.md` documenting rollout status across all 6 providers.
  - Total test coverage: 385 backend tests passing (pytest), 2 frontend tests passing (Vitest).
- Phase 1.9 complete: DevLeveler Profile Integration & Resume Intelligence.
  - Implemented `DevLevelerProfileSource` with ETag caching, local snapshot caching, 24-hour staleness detection, and fallback to `LocalFileProfileSource`.
  - Implemented `ResumeManager` managing versioned resume files, calculating SHA-256 content hashes, rejecting duplicate file uploads, and matching role families (platform, backend, fullstack).
  - Implemented `ResumeIntelligenceEngine` prioritizing and ordering verified experience highlights with audit diffs (`BulletDiff`) and enforcing zero-tolerance anti-hallucination validation (`HallucinationDetectedError`).
  - Implemented `CoverLetterGenerator` constructing personalized drafts with prompt injection sanitization, provenance hashes, and mandatory `needs_review=True` human verification.
  - Implemented `OutcomeTracker` and scoped FastAPI endpoints (`POST /api/v1/applications/{id}/outcomes`, `GET /api/v1/applications/{id}/outcomes`) for tracking interview and offer milestones.
  - Total test coverage: 395 backend tests passing (pytest), 2 frontend tests passing (Vitest).

- Phase 2.0 complete: Production Readiness & Release Candidate.
  - Implemented comprehensive security audit suite (`tests/test_security_audit.py`) verifying fail-closed real submit barriers across all 6 providers, password/secret rejection in session managers, SSRF/loopback/traversal blocking in `NavigationGuard`, prompt injection sanitization, and PII redaction.
  - Implemented full 11-step end-to-end integration test (`tests/test_end_to_end_l0_pipeline.py`) simulating complete lifecycle execution: profile ingestion, job discovery, matching, lifecycle state transitions, human approval, form inspection, L0 dry-run form execution via central orchestrator, real submit barrier verification, and post-application outcome tracking.
  - Hardcoded non-negotiable safety invariant `real_submit_gate_enabled = False` across all providers and runtime components.
  - Authored complete operational documentation suite: updated root `README.md`, native Windows setup guide `docs/INSTALLATION.md`, configuration reference `docs/CONFIGURATION.md`, security posture guide `docs/SECURITY.md`, daily operator guide `docs/OPERATIONS_RUNBOOK.md`, disaster recovery runbook `docs/RECOVERY_RUNBOOK.md`, and locked architecture gate evaluation `docs/RELEASE_READINESS.md`.
  - Total test coverage: 401 backend tests passing (pytest), 2 frontend tests passing (Vitest), ESLint clean.

- Phase 2.1 complete: Supervised L0 Live Form Validation & Evidence Management.
  - Built `worker/pilot/` (`PilotOrchestrator`, `PilotEvidenceManager`, `PilotFormRecord`, `PilotReviewRequest`) with sanitized PII-redacted evidence bundles (`form_schema.json`, `fill_plan.json`, `screenshot.png`) and SHA-256 provenance hashes.
  - Implemented explicit accuracy formula `((reviewed - incorrect) / reviewed * 100)` with zero tolerance for wrong sensitive answers.
  - Scoped REST endpoints in `services/api/routes/pilot.py` (`/api/v1/pilot/*`). 405 backend tests passing.

- Phase 2.2 complete: Durable Supabase Persistence & Storage Abstraction.
  - Built `SupabaseClient` async PostgREST wrapper with typed database exceptions (`DatabaseConnectionError`, `DuplicateRecordError`, `AuthorizationError`, `RecordNotFoundError`).
  - Production Supabase repositories (`SupabaseApplicationRepository`, `SupabaseApplicationEventRepository`, `SupabaseJobRepository`, `SupabaseAnswerBankRepository`) with idempotency, optimistic locking, and user isolation.
  - Private storage abstraction (`SupabaseStorageService`) with 15-minute signed URLs.
  - Additive performance indexes migration (`migrations/002_performance_indexes.sql`). 410 backend tests passing.

- Phase 2.3 complete: API Security Hardening, Authorization & Reliability.
  - Authenticated subject models (`AuthenticatedSubject`, `UserRole`: OWNER, OPERATOR, WORKER, ADMIN).
  - Cross-tenant application ownership verification (`verify_application_ownership` -> 403 Forbidden).
  - Sliding window rate limiter (`SlidingWindowRateLimiter`) with standard headers (`X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`, `Retry-After`).
  - Standardized `APIErrorResponse` schema, `/health/live` and `/health/ready` probes. 415 backend tests passing.

- Phase 2.4 complete: Dashboard API & Product Data Integration Layer.
  - Scoped dashboard REST endpoints in `services/api/routes/dashboard.py` (`/overview`, `/applications`, `/approvals`, `/applications/{id}`, `/timeline`, `/analytics`, `/profile/sync`).
  - Strongly typed TypeScript contracts (`apps/web/src/types/api.ts`) and typed asynchronous API client (`apps/web/src/lib/api-client.ts`). 417 backend tests passing.

- Phase 2.5 complete: Matching Calibration, Answer Quality Analytics & Golden Questions.
  - `MatchingCalibrator` with 50-job human-reviewed benchmark across role families (platform, backend, fullstack) and work modes, verifying zero hard-filter overrides.
  - `AnswerBankQualityReporter` with freshness and provenance auditing.
  - Invariant: LLM answers strictly require human review (`needs_review=True`).
  - Evaluated canonical 20 sensitive/golden questions suite; 100% fail-closed to `always_ask`. 423 backend tests passing.

- Phase 2.6 complete: Operational Reliability, Notifications & Disaster Recovery.
  - Enhanced `TelegramNotificationService` with bounded exponential retries (`_send_with_retries`), `AlertDeduplicator` suppressing repeating alert bursts, and `NotificationOutbox` queuing failed alerts for recovery.
  - Centralized structured logging context (`run_id`, `application_id`, `provider`, `request_id`) via `bind_logging_context` and `format_audit_log`.
  - `BackupManager` creating self-contained backup archives with SHA-256 cryptographic verification and tamper rejection. 430 backend tests passing.

- Phase 2.7 complete: L1 Supervised Execution Preparation & Pre-Submission Simulation.
  - `SupervisedExecutionSimulator` and `PreSubmissionSimulationReport` in `worker/application/supervised.py`, verifying kill switch, rate caps, provider health, answer freshness, and sensitive field policies, stopping strictly before submit.
  - Non-negotiable real submission barrier raising `RealSubmitGateBlockedError` on any submit attempt.
  - `AutonomyController` evaluating L1 promotion criteria (30 apps, >=98% accuracy, 0 wrong sensitive, 0 duplicates) and strictly capping LinkedIn at L1. 435 backend tests passing.

- Phase 2.8 complete: Performance, Scale & Resilience Testing.
  - Benchmarked matching latency (< 70ms for 50 jobs), health probe latency (< 15ms), and form inspection.
  - Verified concurrent application creation idempotency resolving to a single record without race conditions.
  - Authored `docs/CAPACITY_REPORT.md` documenting latency percentiles, memory profile, and capacity stages (S0->S1->S2->S3) while strictly locking active daily cap at 2. 440 backend tests passing.

- Phase 2.9 complete: Release Governance & Platform Certification.
  - Completed security re-audit across all 6 providers, verified `real_submit_gate_enabled = False` strictly across all codebase entrypoints.
  - Authored `docs/FINAL_RELEASE_REPORT.md` and `docs/PHASE_2_1_TO_2_9_COMPLETION.md`.
  - Updated operational runbooks (`docs/OPERATIONS_RUNBOOK.md`, `docs/RECOVERY_RUNBOOK.md`), `docs/SECURITY.md`, `docs/RELEASE_READINESS.md`, `docs/PROVIDER_STATUS.md`, and `README.md`.
  - 440 backend tests passing (100%), 2 frontend tests passing, ESLint clean.

### In progress
- None (All Phases 2.1 through 2.9 fully completed, tested, and certified).

### Unverified / pending
- Live Supabase project deployment and credentials (verified via static text and constraint parsing offline; no live Supabase connection initiated in Phases 0.7–2.9).
- Live OpenRouter network completion (verified via mocked HTTP transport and deterministic unit tests offline; no live OpenRouter calls initiated during tests).
- Live Telegram bot network delivery (verified via mock adapter offline; no live Telegram calls initiated during tests).
- Live Greenhouse, Lever, Naukri, Wellfound, Ashby, and LinkedIn external HTTP requests (verified via mocked HTTP transport and local HTML/JSON fixtures offline; no live external network requests initiated during tests).

## Next steps
1. Deploy Phase 2.9 Release Certified Platform in production runtime environment.
2. Operator staging verification under supervised L0/L1 execution.

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
