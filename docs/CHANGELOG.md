# Changelog

## Unreleased — Bootstrap
- Prepared initial project documentation scaffold.
- Recorded no-Docker initial setup decision.
- Created `apps/web` minimal Next.js 16 + TypeScript + Tailwind CSS v4 foundation.
- Configured shadcn/ui (Base UI + Nova preset) and initialized button and sonner primitives.
- Installed core UI libraries: Lucide React, Motion, Recharts, TanStack Table, React Hook Form, Zod, Sonner.
- Configured frontend test suite with Vitest and Testing Library (React, DOM, Jest-DOM).
- Verified production build (`next build`), linter (`eslint`), and unit tests (`vitest run`).
- Initialized Git repository tracking at project root.
- Established planned directory layout (`services/api/`, `worker/core/`, `worker/profile/`, `worker/providers/`, `worker/sessions/`, `config/`, `migrations/`, `fixtures/forms/`, `tests/`) per locked architecture Appendix C.
- Added Python package initializers (`__init__.py`) with descriptive module docstrings.
- Added root `AGENTS.md` for persistent Antigravity instructions.
- Hardened `.gitignore` to safeguard secrets, browser sessions, caches, and test outputs.
- Created Python 3.13 virtual environment (`.venv`) at project root.
- Created `requirements.txt` with pinned dependencies for FastAPI, Pydantic, Playwright, and Pytest.
- Installed Playwright package and installed Chromium (v1248) + Chrome Headless Shell.
- Implemented minimal FastAPI foundation in `services/api` (`main.py`, `config.py`, `schemas.py`) with `GET /health` endpoint.
- Implemented automated test suite in `tests/test_health.py` and `tests/test_config.py` (6/6 tests passing).



