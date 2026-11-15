# Disaster Recovery and Incident Response Runbook

This document details remediation workflows for emergency incidents, worker crashes, security challenges, and system circuit breaks.

---

## 1. Emergency Kill Switch Management

The kill switch provides an instantaneous, zero-latency halt to all browser automation, worker execution, and form interaction.

### 1.1. Tripping the Kill Switch (Manual Emergency Halt)
Trigger the kill switch if abnormal browser activity, unexpected network calls, or unexpected form submissions are suspected:

```powershell
curl -X POST http://127.0.0.1:8000/api/v1/ops/kill-switch/trip -H "Content-Type: application/json" -d '{"reason": "Investigating unexpected DOM navigation"}'
```
*Effect*: All subsequent worker actions fail immediately with `KillSwitchActiveError`. Any ongoing dry-run is aborted.

### 1.2. Resetting the Kill Switch
Once the underlying cause is resolved:
```powershell
curl -X POST http://127.0.0.1:8000/api/v1/ops/kill-switch/reset -H "Content-Type: application/json" -d '{"actor": "operator", "notes": "Root cause identified and remediated"}'
```

---

## 2. Worker Crash Recovery (RC-3 Protocol)

If the worker process terminates abnormally (e.g. machine restart, power loss, OOM):

1. **Detection**: Upon restart, the orchestrator queries all applications currently in `FILLING` or `SUBMITTING` status.
2. **Deterministic State Resolution**:
   - Applications interrupted during `FILLING` are safely transitioned to `NEEDS_USER_INPUT` or reset to `READY`.
   - Applications are **never** assumed to have been submitted.
   - An immutable `ApplicationEvent` with `event_type = "RECOVERED"` is appended to the event ledger.
3. **Triggering Manual Sweep**:
   ```powershell
   curl -X POST http://127.0.0.1:8000/api/v1/ops/recovery/sweep-interrupted
   ```

---

## 3. Provider Circuit Breakers and Auto-Pause

Each provider is monitored by `ProviderHealthManager`. If a provider encounters:
- 3 consecutive navigation timeouts, or
- 2 consecutive structural DOM parsing failures, or
- An HTTP 429 (Rate Limited) or 403 (Forbidden) response:

The provider's circuit breaker automatically trips to `AUTO_PAUSED`.

### Remediation Workflow:
1. **Inspect Provider Status**:
   ```powershell
   curl http://127.0.0.1:8000/api/v1/ops/health
   ```
2. **Review Logs for Structural Shifts**: Inspect `logs/worker.log` to determine if the provider updated their HTML form layout or selectors.
3. **Update Selectors or Clear Cooldown**: If caused by temporary rate limits, wait out the 15-minute cooldown.
4. **Reset Provider Health**:
   ```powershell
   curl -X POST http://127.0.0.1:8000/api/v1/ops/providers/{provider_name}/reset
   ```

---

## 4. Security Checkpoint / CAPTCHA Protocol

If a platform (e.g. LinkedIn, Naukri) presents a security checkpoint, CAPTCHA, or verification wall:

> [!CAUTION]
> **Strict Guideline Compliance**: Never attempt to programmatically bypass, solve, or click through CAPTCHAs, Cloudflare Turnstile, or security verification walls.

### Remediation Protocol:
1. The provider detection routine (`detect_security_checkpoint_or_wall`) immediately stops execution.
2. Application transitions to `BLOCKED` with reason `"SECURITY_CHECKPOINT_DETECTED"`.
3. An urgent Telegram alert is dispatched to the operator.
4. For Naukri: Autonomy ramp is automatically demoted to stage `S0` (capacity restricted to 2/day).
5. The operator opens a visible browser window locally, signs in manually, and solves the checkpoint.
6. The updated `storage_state.json` is exported.
7. The provider state is reset.

---

## 5. Stale Approval Queue Sweep

Applications that have lingered in `AWAITING_APPROVAL` longer than the configured TTL (default: 24 hours) become stale.

### Execution:
The scheduled job automatically marks stale applications as `EXPIRED`. To force an immediate manual sweep:
```powershell
curl -X POST http://127.0.0.1:8000/api/v1/ops/approvals/expire-stale
```
Expired applications emit an audit event and are cleared from active triage queues.

---

## 6. Disaster Recovery & Archive Restore (Phase 2.6)

In the event of database corruption, system reinstallation, or hardware migration:

### Procedure:
1. Locate the latest verified backup archive (e.g., `backups/backup_latest.json`).
2. Run cryptographic integrity verification:
   ```powershell
   .\.venv\Scripts\python -c "from worker.ops.backup import BackupManager; assert BackupManager.verify_backup_integrity('backups/backup_latest.json'); print('Integrity verified!')"
   ```
3. Execute restore:
   ```powershell
   .\.venv\Scripts\python -c "from worker.ops.backup import BackupManager; res = BackupManager.restore_backup('backups/backup_latest.json'); print('Restored items:', res.restored_counts)"
   ```
4. Verify system health probes:
   ```powershell
   curl http://127.0.0.1:8000/health/ready
   ```
