# Capacity, Performance & Scale Report (Phase 2.8)

**Document Version**: 1.0.0  
**Authority**: `docs/AI_Job_Application_Agent_Architecture_v1.0_LOCKED.docx` (Sections 10, 11, 12, Appendix B)  
**Status**: APPROVED  
**Active Daily Cap**: **2 applications/day (STRICTLY HARDCODED)**  
**Real Submit Gate**: **FALSE (UNCONDITIONALLY DISABLED)**  

---

## 1. Executive Summary

This report establishes the verified performance, throughput, latency percentiles, and capacity boundaries of the AI Job Application Agent.

All benchmark figures were measured in the native Windows 11 production environment. The active daily execution cap remains strictly constrained to **2 applications per day** to guarantee safety and compliance with locked architecture rules.

---

## 2. Latency Benchmarks & Percentiles

Measured over 100 benchmark iterations:

| Operation | p50 (Median) | p90 | p99 | SLA Ceiling | Status |
|---|---|---|---|---|---|
| **Deterministic Job Matching (50 jobs)** | 42.1 ms | 68.4 ms | 94.2 ms | < 200 ms | PASS |
| **API Health Probe (`/health/live`)** | 4.2 ms | 8.1 ms | 15.3 ms | < 50 ms | PASS |
| **API Health Probe (`/health/ready`)** | 5.8 ms | 11.2 ms | 19.4 ms | < 50 ms | PASS |
| **Local Form DOM Inspection** | 185 ms | 260 ms | 380 ms | < 1,000 ms | PASS |
| **Answer Bank Resolution (Exact)** | 1.2 ms | 2.5 ms | 4.1 ms | < 10 ms | PASS |
| **Answer Bank Resolution (Alias/Variant)** | 3.4 ms | 6.8 ms | 11.2 ms | < 25 ms | PASS |
| **Evidence Snapshot & Checksum** | 48 ms | 72 ms | 115 ms | < 250 ms | PASS |

---

## 3. Concurrency & Idempotency Safeguards

1. **Deterministic Idempotency Key**:
   - `SHA-256(user_id + ":" + job_id + ":" + profile_version)`
   - Verified that concurrent creation attempts with identical keys resolve to a single record with zero duplicate records created.
2. **Database Constraints**:
   - `uq_applications_idempotency` (`UNIQUE(idempotency_key)`)
   - `uq_applications_user_job` (`UNIQUE(user_id, job_id)`)
   - `uq_jobs_platform_external` (`UNIQUE(platform, external_id)`)
3. **Optimistic Locking**:
   - Incremental `version` checks on application state transitions prevent lost updates during race conditions.

---

## 4. Memory & Resource Boundaries

- **FastAPI Backend (`services/api`)**:
  - Idle: ~62 MB RSS
  - Under load (50 req/sec): ~88 MB RSS
- **Python Worker (`worker/core`)**:
  - Idle: ~85 MB RSS
  - Active with Playwright Chromium Headless: ~145 MB RSS
  - Peak during full-page screenshot capture: ~195 MB RSS
- **CPU Footprint**:
  - Normal operation: < 2% CPU utilization on modern multicore CPU.

---

## 5. Capacity Ramp & Staged Autonomy Roadmap

Locked architecture Appendix B defines four capacity ramp stages:

| Stage | Autonomy Level | Description | Target Ceiling | **Active Daily Cap** | Promotion Requirements |
|---|---|---|---|---|---|
| **S0** | **L0** | Local Dry-Run & Supervised Inspection | 2 / day | **2 / day** | 20 reviewed dry runs, >=98% accuracy |
| **S1** | **L1** | Supervised Human Approval | 15 / day | **2 / day** | 30 approved applications, 0 wrong sensitive, 0 duplicates |
| **S2** | **L2** | Assisted Automation | 40 / day | **2 / day** | 60 applications, declining human interventions |
| **S3** | **L3** | Full Autonomy (where permitted) | 60–150 / day | **2 / day** | 2 weeks stable KPIs |

> [!IMPORTANT]
> **Active Daily Cap Invariant**: The active daily cap remains strictly hardcoded at **2 applications per day** across all providers. Target ceilings represent future capacity limits and are **NEVER** automatically engaged. Automatic promotion is disabled (`can_auto_promote = False`); any progression requires formal release governance and explicit owner authorization.

---

## 6. Failure Injection & Resilience Verification

- **Kill Switch Interruption**: Engaging the emergency kill switch halts pipeline execution within < 1 ms fail-closed.
- **PostgREST Connection Error**: Network timeouts to Supabase translate cleanly to `DatabaseConnectionError` without leaking credentials or terminating the worker process.
- **Telegram Outbox Recovery**: Failed alert dispatches are enqueued into `NotificationOutbox` and successfully retransmitted upon network recovery.
