# AI Job Application Agent
Personal, human-in-the-loop job application assistant.

## Source of truth
- `docs/AI_Job_Application_Agent_Architecture_v1.0_LOCKED.docx` is authoritative when present.
- `docs/ARCHITECTURE.md`: architecture navigation summary.
- `docs/BUILD_RULES.md`: mandatory coding-agent rules.
- `PROJECT_CONTEXT.md`: handoff/status summary.
- `docs/TASK_TRACKER.md`: task status.

## Initial stack
- Frontend: Next.js + TypeScript
- API/worker: Python + FastAPI
- Database: Supabase PostgreSQL
- Runtime AI: OpenRouter through a central LLM Gateway
- Browser automation: Playwright
- Scheduler: APScheduler
- Git for version control
- No Docker, WSL, or Ubuntu in the initial setup.

Before coding, read `PROJECT_CONTEXT.md`, `docs/ARCHITECTURE.md`, `docs/BUILD_RULES.md`, and `docs/TASK_TRACKER.md`.
