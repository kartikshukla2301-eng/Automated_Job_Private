# AI Job Application Agent

Autonomous, deterministic-first, human-in-the-loop personal job application assistant.

> **CRITICAL ARCHITECTURAL INVARIANT**:
> `real_submit_gate_enabled = False` is hardcoded across all providers and runtime components. Real external form submission is strictly disabled until the locked Real-Submit Gate criteria are fully met and explicitly authorized by the candidate owner.

---

## 1. Architectural Source of Truth

- **Authoritative Architecture Document**: `docs/AI_Job_Application_Agent_Architecture_v1.0_LOCKED.docx`
- **Architecture Navigation & System Summary**: `docs/ARCHITECTURE.md`
- **Mandatory Engineering Rules**: `docs/BUILD_RULES.md`
- **Project Context & Handoff**: `PROJECT_CONTEXT.md`
- **Task & Milestone Tracker**: `docs/TASK_TRACKER.md`
- **Architectural Decision Records**: `docs/DECISIONS.md`
- **Provider Rollout Status**: `docs/PROVIDER_STATUS.md`
- **Release Readiness Certification**: `docs/RELEASE_READINESS.md`

---

## 2. Technology Stack

- **Operating Environment**: Native Windows 11 only. Strictly no Docker, WSL, or Linux containers.
- **Backend API**: Python 3.13 + FastAPI (`services/api/`)
- **Worker & Lifecycle Runtime**: Python pull-based worker (`worker/`)
- **Database & Persistence**: Supabase PostgreSQL (`migrations/`) with in-memory fallbacks for isolated testing
- **Browser Automation**: Playwright (`worker/browser/`) with deterministic DOM inspection
- **Runtime AI Gateway**: Centralized OpenRouter Gateway (`worker/core/llm_gateway.py`) with strict mock/fallback modes
- **Frontend Dashboard**: Next.js 16 + TypeScript + Tailwind CSS (`apps/web/`)
- **Scheduler**: APScheduler (`worker/ops/scheduler.py`) restricted to candidate active window (09:00–23:00 IST)

---

## 3. Supported Job Providers

| Provider | Ingestion Mode | Form Automation | Autonomy Support | Rollout Status |
| :--- | :--- | :--- | :--- | :--- |
| **Greenhouse** | Public Boards API | Playwright Form Parser & Dry-Run | L0 / L1 / L2 / L3 | Production-Ready (Dry-Run) |
| **Lever** | Public Postings API | Playwright Form Parser & Dry-Run | L0 / L1 / L2 / L3 | Production-Ready (Dry-Run) |
| **Naukri** | Session Ingestion | Playwright Automation & Dry-Run | L0 / L1 (S0 Ramp: 2/day) | Production-Ready (Dry-Run) |
| **Wellfound** | Public Feed API | Playwright Automation & Dry-Run | L0 / L1 / L2 / L3 | Production-Ready (Dry-Run) |
| **Ashby** | Public Job Board API | Playwright Automation & Dry-Run | L0 / L1 / L2 / L3 | Production-Ready (Dry-Run) |
| **LinkedIn** | Session-gated feed | Human-assist Fill / Playwright | **L1 Strictly Capped** | Production-Ready (Dry-Run) |

*Note: All providers enforce `RealSubmitGateBlockedError` upon any live submission attempt.*

---

## 4. Non-Negotiable Safety Principles

1. **Deterministic-First Logic**: Field resolution relies strictly on candidate profile facts and verified Answer Bank entries. LLM is invoked only for borderline semantic scoring and prompt-sanitized drafting.
2. **Fail-Closed Safety**: Unknown or ambiguous fields immediately trigger `NEEDS_USER_INPUT` or remain unpopulated. Facts are never hallucinated.
3. **Restricted Provider Constraints**: LinkedIn is hardcoded to never exceed Autonomy Level L1 (`AWAITING_APPROVAL` with mandatory human review). L2/L3 promotions are rejected by runtime validation.
4. **Credential Storage Ban**: Session managers exclusively consume pre-authenticated storage states (`storage_state.json`) or cookie dictionaries. Plaintext passwords and user secrets are strictly rejected.
5. **Anti-SSRF & Navigation Guard**: Browser navigation is locked down to verified provider domains. Private IP ranges, loopback addresses, local metadata services, and directory traversal attempts are blocked.
6. **Prompt Injection Sanitization**: All external job descriptions, company titles, and recruiter notes are stripped of control sequences, XML tags, and command prefixes before LLM processing.
7. **PII Redaction**: Application logs, event payloads, and audit trails automatically redact candidate emails, phone numbers, addresses, and sensitive demographic data.

---

## 5. Quickstart Guide (Native Windows)

### Prerequisites
- Windows 10/11
- Python 3.13+ installed and on `PATH`
- Node.js 20+ / 24+ and npm installed and on `PATH`
- Git installed and on `PATH`

### 1. Repository Setup
```powershell
git clone <repo-url> JOB_AGENT
cd JOB_AGENT
```

### 2. Backend Setup
```powershell
# Create and activate Python virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install backend dependencies
pip install -r requirements.txt

# Install Playwright browser binaries
playwright install chromium
```

### 3. Frontend Setup
```powershell
cd apps/web
npm install
cd ../..
```

### 4. Running Tests
```powershell
# Run complete backend test suite (401+ tests)
.\.venv\Scripts\pytest -v

# Run frontend test suite
npm test --prefix apps/web

# Run frontend linter
npm run lint --prefix apps/web
```

### 5. Running the Application (Local Development)
```powershell
# Terminal 1: Start FastAPI backend
.\.venv\Scripts\uvicorn services.api.main:app --host 127.0.0.1 --port 8000 --reload

# Terminal 2: Start Next.js frontend
npm run dev --prefix apps/web
```

Visit the dashboard at `http://localhost:3000` and API docs at `http://localhost:8000/docs`.

---

## 6. Operational Documentation

- **Installation Guide**: [docs/INSTALLATION.md](file:///c:/Users/Kartik%20Shukla/OneDrive/Desktop/JOB_AGENT/docs/INSTALLATION.md)
- **Configuration Reference**: [docs/CONFIGURATION.md](file:///c:/Users/Kartik%20Shukla/OneDrive/Desktop/JOB_AGENT/docs/CONFIGURATION.md)
- **Security Architecture**: [docs/SECURITY.md](file:///c:/Users/Kartik%20Shukla/OneDrive/Desktop/JOB_AGENT/docs/SECURITY.md)
- **Operator Runbook**: [docs/OPERATIONS_RUNBOOK.md](file:///c:/Users/Kartik%20Shukla/OneDrive/Desktop/JOB_AGENT/docs/OPERATIONS_RUNBOOK.md)
- **Disaster Recovery Runbook**: [docs/RECOVERY_RUNBOOK.md](file:///c:/Users/Kartik%20Shukla/OneDrive/Desktop/JOB_AGENT/docs/RECOVERY_RUNBOOK.md)
- **Release Readiness Evaluation**: [docs/RELEASE_READINESS.md](file:///c:/Users/Kartik%20Shukla/OneDrive/Desktop/JOB_AGENT/docs/RELEASE_READINESS.md)
