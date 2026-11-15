# Installation and Setup Guide (Native Windows)

This document provides definitive, end-to-end installation instructions for running the AI Job Application Agent on **Native Windows 10/11**.

> [!IMPORTANT]
> The AI Job Application Agent is strictly architected for Native Windows. Do not introduce WSL, Docker, Ubuntu, or Linux dependencies.

---

## 1. System Requirements

- **Operating System**: Windows 10 (Build 19041+) or Windows 11 64-bit
- **Shell**: PowerShell 7+ or Windows PowerShell 5.1
- **Python**: Version 3.13.0 or higher
- **Node.js**: Version 20.x or 24.x LTS
- **Package Manager**: npm 10+ (bundled with Node.js)
- **Browser Automation**: Chromium managed via Playwright
- **Hardware**: Minimum 8 GB RAM, 10 GB free disk space

---

## 2. Environment Verification

Open PowerShell and verify your environment binaries:

```powershell
python --version
# Expected: Python 3.13.x

node --version
# Expected: v20.x.x or v24.x.x

git --version
# Expected: git version 2.x.x
```

If Python or Node.js are missing:
- Install Python 3.13 via [python.org](https://www.python.org/downloads/) (ensure **"Add python.exe to PATH"** is checked).
- Install Node.js LTS via [nodejs.org](https://nodejs.org/).

---

## 3. Clone Repository

```powershell
git clone <repository_url> c:\Users\<username>\JOB_AGENT
cd c:\Users\<username>\JOB_AGENT
```

---

## 4. Backend Environment Setup

### 4.1. Create and Activate Virtual Environment
```powershell
python -m venv .venv

# Set execution policy for current process if required
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process

# Activate virtual environment
.\.venv\Scripts\Activate.ps1
```

### 4.2. Upgrade Pip and Install Dependencies
```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 4.3. Install Playwright Browsers
```powershell
playwright install chromium
```

---

## 5. Frontend Environment Setup

Navigate to the Next.js application directory and install dependencies:

```powershell
cd apps\web
npm install
cd ..\..
```

---

## 6. Configuration Setup

Copy the sample environment configuration file:

```powershell
Copy-Item .env.example .env
```

Open `.env` and configure your local settings:

```env
# Server
PORT=8000
ENVIRONMENT=development
LOG_LEVEL=INFO

# Security & Safety
REAL_SUBMIT_GATE_ENABLED=false
KILL_SWITCH_INITIAL_STATE=active

# LLM Gateway (OpenRouter)
OPENROUTER_API_KEY=mock-openrouter-key-for-dev
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
LLM_DEFAULT_MODEL=anthropic/claude-3.5-sonnet

# Supabase (Optional for in-memory testing)
SUPABASE_URL=http://localhost:54321
SUPABASE_KEY=ey...

# Telegram Notifications (Optional)
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
```

---

## 7. Verification and Testing

Execute the test suites to ensure everything is operating cleanly:

```powershell
# 1. Backend Verification (401+ tests)
.\.venv\Scripts\pytest -q

# 2. Frontend Unit Tests
npm test --prefix apps/web

# 3. Frontend ESLint
npm run lint --prefix apps/web
```

All commands must exit with status code `0`.

---

## 8. Starting the Local Services

### Start Backend API:
```powershell
.\.venv\Scripts\uvicorn services.api.main:app --host 127.0.0.1 --port 8000 --reload
```
Swagger UI will be available at: `http://127.0.0.1:8000/docs`

### Start Frontend Application:
```powershell
npm run dev --prefix apps/web
```
Dashboard will be available at: `http://localhost:3000`
