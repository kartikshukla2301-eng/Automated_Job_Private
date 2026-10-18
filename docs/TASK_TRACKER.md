# Task Tracker

Statuses: NOT_STARTED, IN_PROGRESS, BLOCKED, DONE, NEEDS_REVIEW.

| ID | Task | Status | Acceptance criteria |
|---|---|---|---|
| T-001 | Open project in VS Code | DONE | Folder opens at expected path |
| T-002 | Add locked architecture DOCX | DONE | Original v1.0 LOCKED file verified in `docs/` |
| T-003 | Verify instruction loading | DONE | Verified Antigravity (`AGENTS.md` / `.agents`) & Freebuff mechanisms |
| T-004 | Python 3.13 venv & dependencies | DONE | Python 3.13 `.venv`, requirements.txt pinned, Playwright Chromium installed |
| T-005 | Initialize Git & repo foundation | DONE | Git initialized at root, planned directory structure created, .gitignore verified |
| T-006 | Frontend UI foundation & dependencies | DONE | Next.js 16, Tailwind v4, shadcn/ui, Motion, Recharts, TanStack Table, Hook Form, Zod, Sonner, Vitest |
| T-007 | FastAPI backend foundation | DONE | App factory, GET /health, pydantic-settings config, test suite (6/6 passing) |
| T-007b | Centralized config & structured logging (Phase 0.3) | DONE | config/config.yaml + pydantic-settings precedence, structured JSON logging, correlation middleware, 18 backend tests passing |
| T-007c | Candidate ProfileSource & Local YAML Profile (Phase 0.4) | DONE | Profile models, ProfileSource protocol, LocalFileProfileSource, fixtures/profile.yaml, 29 backend tests passing |
| T-008 | Kill switch and caps (Phase 0.5) | DONE | KillSwitch (File/InMemory), CapsEnforcer, SafetyEngine, thread-safe ledgers, 44 backend tests passing proving fail-closed safety |
| T-009 | LLM Gateway and costing | NOT_STARTED | Input/output usage/cost tracked honestly |
| T-010 | Greenhouse dry-run skeleton (Phase 0.6) | DONE | Central JobApplicationRunner enforcing SafetyEngine barrier, strict local fixture validation, sensitive field skipping, truthful GreenhouseProvider form-filling, evidence capture, strictly no submit, 54 passing backend tests |
| T-011 | Supabase PostgreSQL schema foundation (Phase 0.7) | DONE | migrations/001_initial_schema.sql defining all 13 architecture tables, foreign keys, dedupe constraints, state check constraints, RLS on all tables, and static validation tests (62 passing backend tests) |
