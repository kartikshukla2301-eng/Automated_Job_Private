# AI Job Application Agent — Workspace Instructions

All AI coding agents working in this repository must follow these mandatory rules:

1. **Architecture Authority**:
   - `docs/AI_Job_Application_Agent_Architecture_v1.0_LOCKED.docx` is the authoritative architecture document.
   - Summaries and rules are documented in `PROJECT_CONTEXT.md`, `docs/ARCHITECTURE.md`, `docs/BUILD_RULES.md`, and `docs/DECISIONS.md`.
   - Never silently change the locked architecture, database schema, model routing, safety gates, or provider ordering.

2. **Technology Stack**:
   - **Frontend**: Next.js + TypeScript in `apps/web/`.
   - **Backend API**: Python + FastAPI in `services/api/`.
   - **Worker**: Python pull-based worker in `worker/core/`.
   - **Database**: Supabase PostgreSQL (`migrations/`).
   - **Runtime AI**: OpenRouter strictly via central LLM Gateway (`worker/core/llm_gateway.py`).
   - **Browser Automation**: Playwright (deterministic-first).
   - **Scheduler**: APScheduler.
   - **Environment**: Native Windows only. No Docker, WSL, or Ubuntu in initial setup.

3. **Engineering & Safety Principles**:
   - Real submissions are strictly disabled until the locked Real-Submit Gate criteria are met.
   - Deterministic logic first; LLM only for ambiguity.
   - Fail closed: unknown fields require user review (`needs_user_input`).
   - Never invent candidate facts or token/cost counts.
   - Never commit secrets, `.env`, or browser session cookies (`worker/sessions/`).
   - Update `PROJECT_CONTEXT.md`, `docs/TASK_TRACKER.md`, and `docs/CHANGELOG.md` upon every task completion.
