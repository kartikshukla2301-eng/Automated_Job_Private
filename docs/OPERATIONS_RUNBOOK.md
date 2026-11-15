# Operator Runbook

This runbook outlines daily operational procedures, triage workflows, health monitoring, and administrative tasks for maintaining the AI Job Application Agent.

---

## 1. Operating Schedule and Active Window

The agent operates strictly within the candidate's active waking window to simulate realistic human candidate behavior and respect provider rate boundaries.

- **Active Timezone**: `Asia/Kolkata` (IST)
- **Active Window**: `09:00` to `23:00` daily
- **Outside Window**: Automated scheduling halts. The runner sleeps until the next window open.
- **Randomized Jitter**: Action delays are randomized between 30 and 90 seconds.

---

## 2. Daily Operator Routine

### 2.1. Morning Health Check (09:00 IST)
1. **Verify Heartbeat Status**:
   ```powershell
   curl http://127.0.0.1:8000/api/v1/ops/heartbeat
   ```
   *Expected Response*: `{"status": "ok", "worker_alive": true, "timestamp": "..."}`
2. **Review Telegram Notifications**: Check for any overnight alerts regarding session expirations, circuit breakers, or unexpected provider DOM shifts.
3. **Run Provider Canaries**:
   ```powershell
   curl -X POST http://127.0.0.1:8000/api/v1/ops/canary
   ```
   *Verify*: All 6 providers return `"healthy": true`.

### 2.2. Midday Approval Triage (13:00 & 18:00 IST)
1. **Inspect Pending Approvals**:
   ```powershell
   curl http://127.0.0.1:8000/api/v1/ops/approvals
   ```
2. **Review Staged Applications**:
   Navigate to the web dashboard (`http://localhost:3000/approvals`) or review via Telegram.
3. **Approve or Reject**:
   - Approve vetted applications:
     ```powershell
     curl -X POST http://127.0.0.1:8000/api/v1/ops/approvals/{application_id}/approve -H "Content-Type: application/json" -d '{"actor": "operator"}'
     ```
   - Reject unsuited applications:
     ```powershell
     curl -X POST http://127.0.0.1:8000/api/v1/ops/approvals/{application_id}/reject -H "Content-Type: application/json" -d '{"actor": "operator", "reason": "Location mismatch"}'
     ```

### 2.3. End-of-Day Review (22:30 IST)
1. **Inspect Daily Application Metrics**:
   ```powershell
   curl http://127.0.0.1:8000/api/v1/ops/metrics
   ```
   Verify:
   - Total applications discovered, matched, approved, and dry-run completed.
   - Zero real submissions attempted (`"real_submissions": 0`).
   - Daily cap utilization (`apps_today <= global_per_day`).
2. **Stale Approval Sweep**: Ensure applications pending > 24 hours are auto-expired.

---

## 3. Capacity Ramp Management

For session-managed platforms (Naukri), volume is controlled via progressive capacity stages:

| Stage | Daily Volume Cap | Promotion Requirement | Failure Demotion Trigger |
| :--- | :--- | :--- | :--- |
| **S0** (Initial) | 2 applications/day | 3 consecutive clean operational days | Any checkpoint / security challenge |
| **S1** (Ramp 1) | 5 applications/day | 5 consecutive clean operational days | 2 consecutive failures |
| **S2** (Ramp 2) | 10 applications/day | 7 consecutive clean operational days | 2 consecutive failures |
| **S3** (Target) | 20 applications/day | Sustained healthy status | 3 consecutive failures |

*To inspect or manually adjust the capacity stage:*
```powershell
# Get autonomy and ramp status
curl http://127.0.0.1:8000/api/v1/ops/autonomy/status

# Record successful day for promotion evaluation
curl -X POST http://127.0.0.1:8000/api/v1/ops/autonomy/ramp/record-clean-day
```

---

## 4. Provider Session Maintenance

Platforms requiring authenticated browser sessions (LinkedIn, Naukri, Wellfound) periodically require refreshed cookies.

### Re-Authenticating a Session:
1. Open Playwright in headed mode on the local machine:
   ```powershell
   .\.venv\Scripts\python -m worker.browser.manual_login --provider naukri
   ```
2. Manually log in, solving 2FA or security challenges.
3. The script exports `storage_state.json` to `worker/sessions/naukri_storage_state.json`.
4. Validate that no password fields exist in the saved state:
   ```powershell
   .\.venv\Scripts\pytest tests/test_security_audit.py -k test_session_managers_reject_passwords_and_secrets
   ```
