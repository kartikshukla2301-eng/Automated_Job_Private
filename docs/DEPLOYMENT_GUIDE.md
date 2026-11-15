# Deployment Guide — AI Job Application Agent

**Platform**: AI Job Application Agent  
**Release**: L0 Supervised Execution Candidate (Phase 3.9)  
**Architecture Authority**: `docs/AI_Job_Application_Agent_Architecture_v1.0_LOCKED.docx` (Section 16)

---

## 1. System Architecture & Topology

```
+-------------------------------------------------------+
|                   OPERATOR BROWSER                    |
|             (http://localhost:3000 / UI)              |
+---------------------------+---------------------------+
                            |
                            v
+---------------------------+---------------------------+
|               NEXT.JS WEB DASHBOARD                   |
|                   (apps/web)                          |
+---------------------------+---------------------------+
                            | REST API (HTTP)
                            v
+-------------------------------------------------------+
|               FASTAPI BACKEND SERVICE                 |
|                   (services/api)                      |
+-------------+---------------------------+-------------+
              |                           |
              v                           v
+-------------+-------------+   +---------+-------------+
|    SUPABASE POSTGRESQL    |   |    AUTONOMOUS WORKER  |
|    (db.supabase.co:5432)  |   |      (worker/core)    |
+---------------------------+   +---------+-------------+
                                          |
                                          v
                                +---------+-------------+
                                |  PLAYWRIGHT BROWSERS  |
                                |  (L0 Dry-Run Guard)   |
                                +-----------------------+
```

---

## 2. Production Build & Packaging

### Next.js Frontend (`apps/web`)
To generate an optimized production bundle:
```powershell
cd apps/web
npm ci
npm run build
```

To run the Next.js production server:
```powershell
npm run start
```
By default, the server listens on port `3000`.

### Backend Service (`services/api`)
Run FastAPI behind a production ASGI server (Uvicorn with worker processes):
```powershell
.\.venv\Scripts\uvicorn services.api.main:app --host 0.0.0.0 --port 8000 --workers 4
```

---

## 3. Database Migration Deployment

Ensure all PostgreSQL migrations are applied in sequential order to the target Supabase instance:
1. `migrations/001_initial_schema.sql`: Core tables (`jobs`, `candidate_profiles`, `resumes`, `answer_bank`, `applications`, `application_events`, `circuit_breakers`, `audit_logs`).
2. `migrations/002_performance_indexes.sql`: Additive indexes for fast multi-filter job discovery and lifecycle queries.

Verify connection via PostgreSQL CLI or Supabase SQL Editor:
```sql
SELECT count(*) FROM jobs;
SELECT count(*) FROM applications;
```

---

## 4. Production Health & Readiness Verification

Before routing traffic, query the health probes:

- **Liveness Probe**: `GET http://127.0.0.1:8000/health/live`  
  *Response*: `{"status": "ok", "timestamp": "..."}`
- **Readiness Probe**: `GET http://127.0.0.1:8000/health/ready`  
  *Response*: `{"status": "ready", "database": "connected", "kill_switch": "armed"}`

---

## 5. Security Invariant Certification Checklist

Prior to production launch, verify the following architecture invariants:

- [x] **Real-Submit Gate Locked**: `real_submit_gate_enabled = False` unconditionally hardcoded across all 6 providers. Real form submissions are impossible.
- [x] **Daily Application Cap**: Hard-limited to 2 applications/day (Capacity Stage S0).
- [x] **Zero Password Storage**: No plaintext passwords, OTPs, or credit card numbers stored in database, configs, or session cookies.
- [x] **Cookie Session Isolation**: Playwright cookies stored exclusively in protected local `worker/sessions/` directory.
- [x] **Single-Operator Scoping**: Single-user allowlist and ownership validation enforced across all API endpoints.
- [x] **Telegram Cooldowns**: Alert deduplication active with 15-minute heartbeats and burst suppression.
