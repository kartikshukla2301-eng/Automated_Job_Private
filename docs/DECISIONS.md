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

## AD-006 — Mandatory central runner execution barrier for provider actions
Status: Accepted / Locked for Phase 0.6.
- Context: Ensure provider adapters (Greenhouse, Lever, etc.) cannot be accidentally invoked without prior safety barrier checks.
- Decision: All provider automation must be coordinated through a central application runner that invokes `SafetyEngine.verify_pre_apply()` prior to launching browser contexts or filling forms.
- Real-submit gate remains strictly locked (`real_submit_gate_enabled=False`).

## AD-007 — Fail-closed frontend access for worker runs and LLM telemetry
Status: Accepted / Locked for Phase 0.7.
- Context: Section 14 defines `runs` and `llm_calls` without a `user_id` column. A permissive `USING (true)` policy would expose system-wide execution metrics to any authenticated Supabase user token.
- Decision: Do not invent unapproved `user_id` columns in the database migration. Instead, enforce fail-closed security by enabling RLS on `runs` and `llm_calls` with zero authenticated/anon policies (matching `sessions`). Frontend visibility into execution runs or LLM cost summaries must be routed through authorized backend APIs (or a future approved multi-tenant ownership model).

## AD-008 — Company rules deduplication constraint
Status: Pending / Awaiting Architecture Decision.
- Context: In `migrations/001_initial_schema.sql`, `company_rules` defines `(user_id, company, rule_type, value, expires_at)`. The post-implementation audit noted that the absence of a unique constraint allows multiple active rules of the same `rule_type` for the same employer.
- Problem: The locked architecture does not specify whether employers can have multiple rules of the same type (e.g. multiple distinct cooldown windows or threshold triggers) or exactly one per type.
- Options:
  1. Add `CONSTRAINT uq_company_rules UNIQUE (user_id, company, rule_type)`: Enforces at most one active rule per type per company.
  2. Retain current schema (no unique constraint): Allows multiple rules per company and resolves precedence/expiration at runtime in the policy engine.
- Decision: Defer adding any constraint to preserve the locked architecture without guessing. Runtime policy engine will handle resolution until explicitly decided.

## AD-009 — Fail-Closed Unpriced Call Policy for LLM Cost Budgets
Status: Accepted / Locked for Phase 0.9.
- Context: When a daily cost budget (`daily_cost_budget_usd`) is configured, OpenRouter or upstream model providers may occasionally return unpriced completions (omitting provider-reported `cost`) or completions for models without pre-configured token pricing rates.
- Decision:
  1. Fail-closed: When a daily cost budget is configured, every paid completion request requires pre-configured token pricing in `model_pricing` as a prerequisite before dispatching to the provider. Requests for unpriced models will be rejected with `LLMBudgetExceededError` (or degraded).
  2. Cost calculation precedence: Authoritative provider-reported cost takes precedence. If missing, cost is estimated strictly from valid provider token counts and configured rates.
  3. If both provider cost and valid token usage are missing, the cost is recorded as `unknown`. To prevent silent budget circumvention, recorded unknown-cost calls block subsequent paid provider requests for that day until the daily accounting boundary or explicit administrative reconciliation.
  4. Unknown costs are never treated as zero.
  5. Any relaxation of this policy requires written proposal and explicit owner approval.
