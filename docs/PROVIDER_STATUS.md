# Provider Rollout & Status Matrix

AUTHORITY:
- `docs/AI_Job_Application_Agent_Architecture_v1.0_LOCKED.docx` (Sections 9, 10, 11, 12, 14)
- `docs/BUILD_RULES.md`

This document defines the authoritative capabilities, authentication models, risk tiers, and autonomy constraints across all 6 supported job board and ATS providers.

---

## 1. Provider Capability & Risk Matrix

| Provider | Type | Risk Tier | Auth Model | Discovery Method | Form Inspection | Max Autonomy | Daily Cap Default | Status |
|---|---|---|---|---|---|---|---|---|
| **Greenhouse** | ATS | Low | Public (No auth) | REST API / HTML | Playwright DOM / HTML | L3 Full Auto | Standard (20/40) | **CERTIFIED (L0/L1)** |
| **Lever** | ATS | Low | Public (No auth) | REST API / HTML | Playwright DOM / HTML | L3 Full Auto | Standard (20/40) | **CERTIFIED (L0/L1)** |
| **Ashby** | ATS | Low | Public (No auth) | Board API / HTML | Playwright DOM / HTML | L3 Full Auto | Standard (20/40) | **CERTIFIED (L0/L1)** |
| **Naukri** | Job Board | Medium | Manual Session (`cookies.json`) | Ingestion / Cards | Playwright DOM / HTML | L3 Staged | Staged (S0: 2/day) | **CERTIFIED (L0/L1)** |
| **Wellfound** | Startup Board | Medium | Manual Session (`cookies.json`) | Ingestion / Cards | Playwright DOM / HTML | L3 Staged | Staged (S0: 2/day) | **CERTIFIED (L0/L1)** |
| **LinkedIn** | Social Network | **High (Restricted)** | Manual Session (`cookies.json`) | Ingestion / Cards | Playwright Easy Apply | **L1 Supervised ONLY** | Strictly Capped (2/day) | **CERTIFIED (L0/L1 Restricted)** |

---

## 2. Invariant Rules Across All Providers

1. **Hardcoded Real-Submit Barrier**:
   `real_submit_gate_enabled = False` is hardcoded across all provider adapters. No real application submission can occur. Calling `submit_application` unconditionally raises `RealSubmitGateBlockedError`.

2. **L0 Dry-Run DOM Safety**:
   In L0 dry-run execution, form inputs, select elements, and radio buttons remain completely untouched in the live DOM. No submit or apply buttons are clicked.

3. **Credential Storage Ban**:
   All session managers (`NaukriSessionManager`, `WellfoundSessionManager`, `LinkedInSessionManager`) store only session cookies and auth tokens in isolated JSON files. Passwords, secrets, and 2FA credentials are systematically rejected and never stored.

4. **Restricted Provider Constraints (LinkedIn)**:
   - **Autonomy Ceiling**: Strictly locked to **L1** (Supervised with individual human approval per application). Promotion checks to L2 or L3 fail closed and are blocked by `AutonomyController`.
   - **Anti-Bot & Checkpoint Defense**: In the event of a login wall, CAPTCHA, or security checkpoint, execution halts immediately with `LinkedInSecurityCheckpointError` or `LinkedInLoginWallError`. No evasion or stealth bypassing is ever attempted.
