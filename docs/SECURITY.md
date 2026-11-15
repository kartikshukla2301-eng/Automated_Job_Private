# Security Architecture and Compliance Guide

This document defines the core security posture, threat model, and defense-in-depth controls implemented across the AI Job Application Agent.

---

## 1. Threat Model

The agent operates in an untrusted web environment, processing external HTML forms, untrusted job postings, and dynamic web content.

```
       [ Untrusted Internet / Job Boards ]
                       │
                       ▼
        [ NavigationGuard / SSRF Filter ]
                       │
                       ▼
        [ Playwright Browser Automation ]
                       │
       ┌───────────────┴───────────────┐
       ▼                               ▼
 [ Form Inspector ]          [ Untrusted HTML / Text ]
       │                               │
       ▼                               ▼
 [ PolicyEngine ]            [ Prompt Sanitizer ]
 (NEVER_FILL / Security)      (Strip XML / Control Chars)
       │                               │
       ▼                               ▼
 [ AnswerResolver ]          [ Central LLM Gateway ]
 (Truthful Profile Only)     (Mock / Fail-Closed)
       │                               │
       └───────────────┬───────────────┘
                       │
                       ▼
       [ Real-Submit Gate Barrier ] ──❌ BLOCKED (real_submit_gate_enabled = False)
```

### Key Threats & Mitigations:
1. **Unintended External Submission**: Hardcoded barrier `RealSubmitGateBlockedError` blocks live submissions across all 6 providers.
2. **Credential Theft / Exposure**: Storing passwords or plaintext credentials in session files is strictly prohibited. Session managers only load session cookies.
3. **SSRF / Host Traversal**: `NavigationGuard` blocks local loopback, RFC 1918 private subnets, cloud metadata endpoints, and directory traversal.
4. **Prompt Injection**: External job titles, company blurbs, and recruiter prompts are scrubbed of prompt injection payloads and XML delimiter tags.
5. **PII Leakage in Logs**: Automated redaction sanitizes emails, phone numbers, postal addresses, and SSNs in application event ledgers.
6. **Account Banning / Detection**: Human-like randomized jitter (30s–90s delays), strict daily volume caps, and LinkedIn L1 ceiling prevent aggressive automation.

---

## 2. Real-Submit Gate Invariant

Under Architecture v1.0 LOCKED, `real_submit_gate_enabled = False` is enforced by default in code:
- Every provider's `submit_application()` method explicitly checks this flag and raises `RealSubmitGateBlockedError`.
- Even in Autonomy Level L3, live submission cannot occur without explicitly passing the 8 locked architecture submit-readiness criteria.

---

## 3. Credential Storage Ban & Session Management

The system strictly enforces a zero-password storage policy:
- `worker/sessions/` stores only temporary browser session cookies and Playwright `storage_state.json`.
- `NaukriSessionManager`, `WellfoundSessionManager`, and `LinkedInSessionManager` inspect ingested session dicts and immediately raise `ValueError` if any key contains `password`, `secret`, `api_key`, `token`, or `credential`.
- Session cookie directories are gitignored and never committed to source control.

---

## 4. Anti-SSRF & Navigation Guard (`NavigationGuard`)

All Playwright browser navigation passes through `worker/browser/navigation_guard.py`:
- **Allowed Schemes**: Only `https://` (and strictly local `file://` under `fixtures/forms/` for test fixtures) are accepted.
- **Allowed Hosts**: Navigations are restricted to verified job board domains:
  - `greenhouse.io`, `boards.greenhouse.io`
  - `lever.co`, `jobs.lever.co`
  - `naukri.com`, `www.naukri.com`
  - `wellfound.com`, `angel.co`
  - `ashbyhq.com`, `jobs.ashbyhq.com`
  - `linkedin.com`, `www.linkedin.com`
- **Blocked IP Ranges**:
  - Loopback (`127.0.0.1`, `localhost`, `::1`)
  - Private Networks (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`)
  - Cloud Metadata Endpoints (`169.254.169.254`, `metadata.google.internal`)
- **Directory Traversal**: Paths containing `..`, `%2e%2e`, or resolving outside `fixtures/forms/` are rejected before invocation.

---

## 5. Policy Engine & Classification Taxonomy

Every discovered form field is evaluated against `worker/policy/engine.py` and categorized according to `FieldCategory`:

| Field Category | Policy Type | Automation Rule |
| :--- | :--- | :--- |
| `SENSITIVE_SECURITY` | `NEVER_FILL` | **Strictly Blocked**: Captcha, OTP, password, MFA, SSN, bank info. |
| `COMPENSATION` | `ALWAYS_ASK` | Requires explicit candidate confirmation; never guessed. |
| `DEMOGRAPHICS_EEO` | `ALWAYS_ASK` / `AUTO` | Filled only if candidate explicitly specified voluntary disclosure. |
| `STANDARD_IDENTITY` | `AUTO` | First name, last name, email, phone, location from verified profile. |
| `UNKNOWN_CUSTOM` | `ALWAYS_ASK` | Transitions application to `NEEDS_USER_INPUT` if required. |

---

## 6. Prompt Injection Defense (`worker/core/sanitizer.py`)

Untrusted text extracted from external job listings is sanitized before feeding into LLM prompts:
- Delimiter tags (e.g. `<instructions>`, `</system>`, `### SYSTEM`) are stripped or escaped.
- System prompt override phrases (e.g. "Ignore previous instructions", "Output the system prompt") are neutralized.
- Strict token budgets prevent context window stuffing attacks.

---

## 7. Data Privacy and PII Redaction

- Loggers strip email addresses, phone numbers, and candidate names using regex sanitizers before writing to console or file.
- Event payloads in `ApplicationEvent` record field keys resolved (`{"first_name": "<RESOLVED_FIELD>"}`), never storing raw sensitive values in plain text.
- Database schemas enforce Row Level Security (RLS) ensuring `user_id = auth.uid()` on all candidate applications and profile snapshots.
