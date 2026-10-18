# Architecture Decisions Log

## AD-001 — Locked architecture
Status: Accepted / locked.
Follow `AI_Job_Application_Agent_Architecture_v1.0_LOCKED.docx`. Any change needs a written proposal and explicit owner approval.

## AD-002 — No Docker in initial development
Status: Accepted.
Start on native Windows without Docker, WSL or Ubuntu. Revisit only if owner explicitly approves.

## AD-003 — Coding agent vs runtime AI
Status: Accepted.
Freebuff is the development agent. The application runtime uses OpenRouter through its own LLM Gateway.

## AD-004 — Mandatory project handoff
Status: Accepted.
Maintain `PROJECT_CONTEXT.md`, task tracker, changelog, architecture reference and build rules. Every agent verifies them against code and Git before continuing.

## AD-005 — Daily application caps accounting timezone
Status: Proposed / Awaiting Owner Approval.
- Context: Appendix B defines `schedule.timezone: Asia/Kolkata` with `active_hours: "09:00-23:00"`, while initial Phase 0.5 daily caps accounting evaluates calendar dates against `timezone.utc`.
- Proposal: Daily rate cap accounting should evaluate calendar days using the configured `schedule.timezone` (`Asia/Kolkata`) so daily counters reset at local midnight rather than UTC midnight (05:30 AM IST).
- Constraint: Until approved and verified with boundary tests across midnight, accounting remains UTC-based.
