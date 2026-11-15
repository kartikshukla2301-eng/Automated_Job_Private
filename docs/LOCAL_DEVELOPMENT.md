# Local Development Guide — AI Job Application Agent

**Environment**: Native Windows 11 Only (No Docker, No WSL, No Linux dependencies)  
**Architecture Authority**: `docs/AI_Job_Application_Agent_Architecture_v1.0_LOCKED.docx`  
**Status**: L0 Certified (Phase 3.9)

---

## 1. Prerequisites

Before starting local development on Windows 11, ensure the following runtimes are installed:

- **Python**: 3.11+ or 3.13+ (Installed natively on Windows, with `python.exe` accessible in PATH or via `.venv`)
- **Node.js**: v20.x or v22.x LTS (with `npm` and `npx`)
- **PowerShell**: Windows PowerShell 5.1 or PowerShell 7+
- **Playwright Browsers**: Chromium installed via `python -m playwright install chromium`

---

## 2. Environment Configuration

Create a `.env` file in the repository root (`JOB_AGENT/.env`):

```env
# Runtime Environment
ENVIRONMENT=development
LOG_LEVEL=INFO
PORT=8000

# Supabase PostgreSQL Configuration
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-supabase-service-role-key
DATABASE_URL=postgresql://postgres:your-password@db.your-project.supabase.co:5432/postgres

# OpenRouter LLM Gateway
OPENROUTER_API_KEY=your-openrouter-key
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
LLM_DAILY_BUDGET_USD=0.50

# Telegram Operational Alerts
TELEGRAM_BOT_TOKEN=your-telegram-bot-token
TELEGRAM_ALLOWED_CHAT_IDS=["123456789"]

# DevLeveler Profile Integration
DEVLEVELER_API_BASE=http://localhost:3000
DEVLEVELER_API_KEY=your-devleveler-key

# Safety Invariants (Strictly Enforced)
REAL_SUBMIT_GATE_ENABLED=false
MAX_APPLICATIONS_PER_DAY=2
```

---

## 3. Starting Services Locally

To run the complete platform, start the three core components in separate PowerShell terminal windows:

### Terminal 1: Backend API Service (FastAPI)
```powershell
cd "c:\Users\Kartik Shukla\OneDrive\Desktop\JOB_AGENT"
.\.venv\Scripts\python.exe -m uvicorn services.api.main:app --host 127.0.0.1 --port 8000 --reload
```
*Health Check: Verify `http://127.0.0.1:8000/health/live` returns `{"status":"ok"}`.*

### Terminal 2: Web Dashboard (Next.js)
```powershell
cd "c:\Users\Kartik Shukla\OneDrive\Desktop\JOB_AGENT\apps\web"
npm run dev
```
*Web Console: Open `http://localhost:3000` in Google Chrome or Microsoft Edge.*

### Terminal 3: Autonomous Worker Service
```powershell
cd "c:\Users\Kartik Shukla\OneDrive\Desktop\JOB_AGENT"
.\.venv\Scripts\python.exe -m worker.core.orchestrator
```

---

## 4. Running Verification Test Suites

### Frontend Vitest Suite (34 Unit & E2E Tests)
```powershell
npm test --prefix apps/web
```

### Frontend Production Build & Type Check
```powershell
npm run build --prefix apps/web
```

### Backend Pytest Suite (440 Integration & Security Tests)
```powershell
.\.venv\Scripts\python.exe -m pytest tests/
```

---

## 5. Troubleshooting on Windows 11

### 1. `python.exe` opens Windows Store
If typing `python` redirects to the Microsoft Store:
- Use the virtual environment binary explicitly: `.\.venv\Scripts\python.exe`.
- Or disable App execution aliases: Windows Settings → Apps → Advanced app settings → App execution aliases → Turn off `python.exe` and `python3.exe`.

### 2. Git `index.lock` Permission Denied
If Git operations report `Unable to create '.git/index.lock': Permission denied`:
- Remove any stale lock file: `powershell -Command "Remove-Item -Force .git/index.lock"`
- Ensure no IDE background indexing process is locking the Git repository.

### 3. Next.js Turbo / Turbopack Cache Glitches
If a build fails due to stale segment references:
- Clear the cache directory: `powershell -Command "Remove-Item -Recurse -Force apps/web/.next"`
- Re-run `npm run build --prefix apps/web`.
