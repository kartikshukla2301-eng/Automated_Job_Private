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
- Automated test suite in `tests/` verifying health and configuration validation (6/6 tests passing).

### In progress
- Phase 0.3: Core runtime configuration loader (`config.yaml`), structured logging, and LocalFileProfileSource.

### Unverified / pending
- Supabase project and credentials.
- Current OpenRouter model IDs and pricing.
- Worker core engine and Greenhouse adapter.

## Next steps
1. Implement runtime configuration loader (`config/config.yaml`) based on Appendix B and structured logging.
2. Implement LocalFileProfileSource (`worker/profile/source.py`, `localfile.py`, `fixtures/profile.yaml`).
3. Implement persisted kill switch and caps with unit tests (`worker/core/caps.py`, `kill_switch.py`).
4. Implement Greenhouse dry-run walking skeleton (`worker/providers/greenhouse.py`).

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
