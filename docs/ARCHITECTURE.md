# Architecture Reference

The locked architecture DOCX is authoritative. This file is only a quick reference; do not omit requirements from the DOCX.

- DevLeveler is the canonical candidate profile source; Job Agent owns application-specific data.
- Use a versioned profile snapshot and `ProfileSource` abstraction, including local-file fallback.
- Answer resolution: exact/alias → semantic/local embedding → LLM → user.
- Policy is enforced in code. Unknown fields default to `always_ask`.
- Autonomy levels L0–L3; every provider starts at L0.
- Deterministic Playwright first; manual login and user intervention for OTP/CAPTCHA.
- No stealth, fingerprint spoofing, or evasion.
- Initial provider order: Greenhouse/Lever, Naukri, Wellfound/Ashby, LinkedIn last.
- APScheduler for MVP; no Celery/Redis without approval.
- Explainable weighted matching; local embeddings first; LLM only for borderline cases.
- Auditable, idempotent submissions; uncertain result means verify, never blindly retry.
- Job descriptions and form text are untrusted input.
- Central LLM Gateway handles model routing, token/cost tracking, caching, budget and circuit breaker.
- Supabase service-role key stays in FastAPI; never in frontend or worker.
- Browser sessions remain local and outside cloud-synced folders.
- Start at L0 dry-run; real submissions require all locked gates and explicit owner approval.
- Safety execution boundary: all provider form filling, dry-run navigation, and submission attempts must pass through a central runner that calls `SafetyEngine.verify_pre_apply()` before any browser interaction. Direct invocation of provider browser actions without prior safety clearance is forbidden.
- Real-Submit Gate remains hard-coded as disabled until all criteria in Architecture v1.0 LOCKED line 683 are formally met.

Planned components: `apps/web`, `services/api`, `worker/core`, `worker/providers`, `worker/profile`, `worker/sessions`, `migrations`, `fixtures/forms`, `tests`.
