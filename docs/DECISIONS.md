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
