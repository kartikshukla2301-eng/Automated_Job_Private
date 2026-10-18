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
- Implemented automated test suite in `tests/test_health.py` and `tests/test_config.py` (6/6 tests passing).
- Phase 0.3: Centralized runtime configuration in `config/config.yaml` based on locked architecture Appendix B (`autonomy`, `caps`, `schedule`, `matching`, `llm`, `approval`, `retention`, `profile`).
- Upgraded `services/api/config.py` with `pydantic-settings` supporting typed nested configurations, deterministic precedence (Init > Env vars > .env > YAML > Defaults), and bounds validation.
- Implemented structured JSON logging with UTC ISO-8601 timestamps, log level, service identifier, request correlation ID, safe exception formatting, and recursive secret redaction filter (`services/api/logging_config.py`).
- Added `RequestCorrelationMiddleware` on FastAPI with strict validation of `X-Request-ID` (`^[a-zA-Z0-9_\-]{1,64}$`), fallback to UUID4, header propagation, and structured HTTP access logging.
- Expanded backend test suite to 18 passing tests covering YAML parsing, configuration precedence, out-of-bounds validation, secret scrubbing, log formatting, setup idempotency, and request ID behavior.
- Phase 0.4: Implemented strongly typed candidate profile models (`EducationEntry`, `ExperienceEntry`, `SkillEntry`, `ProjectEntry`, `CandidateDetails`, `CandidatePreferences`, `ProfileSnapshot`) with strict validation in `worker/profile/models.py`.
- Defined `ProfileSource` Protocol abstraction in `worker/profile/source.py` decoupling worker engines from profile storage.
- Implemented `LocalFileProfileSource` in `worker/profile/localfile.py` with typed exceptions (`ProfileNotFoundError`, `ProfileParseError`, `ProfileValidationError`) and deterministic SHA256 version calculation.
- Added non-canonical placeholder fixture in `fixtures/profile.yaml` with clear testing disclaimers.
- Expanded backend test suite to 29 passing tests covering model validation, YAML parsing errors, missing files, extra field rejection, and deterministic profile versioning.



