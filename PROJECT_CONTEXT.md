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
- Frontend test suite (Vitest) verified passing (2 tests).

### In progress
- None (Phase 0.6 complete).

### Unverified / pending
- Supabase project and credentials.
- Current OpenRouter model IDs and pricing.
- LLM Gateway runtime costing implementation (Phase 0.9 / T-009).

## Next steps
1. Phase 0.7: Establish Supabase PostgreSQL database schema migration foundation (`migrations/`).

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
