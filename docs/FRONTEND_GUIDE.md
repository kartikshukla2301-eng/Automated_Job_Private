# Frontend Guide — AI Job Application Agent

**Platform**: AI Job Application Agent  
**Module**: `apps/web`  
**Architecture Authority**: `docs/AI_Job_Application_Agent_Architecture_v1.0_LOCKED.docx` (Section 14)  
**Status**: L0 Release Certified (Phase 3.9)

---

## 1. Overview & Architectural Principles

The frontend for the AI Job Application Agent is a high-performance, single-operator desktop cockpit built with **Next.js (App Router)** and **TypeScript**. It connects directly to the local FastAPI backend (`http://127.0.0.1:8000`) and the Python worker service.

### Authoritative Design Directives
1. **Premium Light Theme Strictly**: Clean white cards (`bg-white`), subtle neutral slate borders (`border-slate-200/80`), high-contrast typography, and accessible visual hierarchy. Dark mode defaults are strictly prohibited.
2. **Transparent Determinism**: Every matching score, eligibility gate, and form fill plan provides a transparent breakdown. The operator must always see *why* an action was taken.
3. **Fail-Closed Safety**: Real application submissions are permanently disabled in L0 supervised execution. All UI components reflect the hardcoded barrier (`real_submit_gate_locked = true`).
4. **Offline Resilience**: If the local FastAPI backend is unreachable or starting up, all workspaces gracefully fall back to cached demo snapshots with an interactive "Retry Connection" trigger.

---

## 2. Technology Stack

- **Framework**: Next.js 16.4.2 (App Router with Turbopack, Partial Prerendering, and Cache Components)
- **Language**: TypeScript 5.7+ (Strict mode, zero `any` policy)
- **Styling**: Tailwind CSS v4 with `@tailwindcss/postcss` and CSS variables
- **Icons**: Lucide React (`lucide-react`)
- **Testing**: Vitest 5.0+ with `@testing-library/react` and `@testing-library/jest-dom`
- **Fonts**: High-performance native system font stack (zero external Google Fonts HTTP dependencies for 100% offline build resilience)

---

## 3. Design System & UI Primitives

All reusable UI components reside in `apps/web/src/components/ui/`:

| Component | File | Description |
| :--- | :--- | :--- |
| **Badge** | `src/components/ui/badge.tsx` | Status tags with semantic color variants (`default`, `secondary`, `outline`, `destructive`, `success`, `warning`, `indigo`, `purple`) |
| **StatCard** | `src/components/ui/stat-card.tsx` | Metric KPI card with value, subtitle, trend indicator, and optional status badge |
| **PageHeader** | `src/components/ui/page-header.tsx` | Standard workspace header with breadcrumbs, title, description, badge, and action slot |
| **Input & Search** | `src/components/ui/input.tsx` | Styled form controls and real-time search input with clear button |
| **Table** | `src/components/ui/table.tsx` | Accessible table wrapper with striped rows and responsive container |
| **Tabs** | `src/components/ui/tabs.tsx` | ARIA-compliant tablist (`role="tablist"`, `role="tab"`, `role="tabpanel"`) |
| **Dialog** | `src/components/ui/dialog.tsx` | Accessible modal (`role="dialog"`, `aria-modal="true"`) with backdrop blur, Escape dismissal, and focus containment |
| **ChartContainer** | `src/components/ui/chart-container.tsx` | Structured card container for funnel and metric visualizations |
| **Skeleton** | `src/components/ui/skeleton.tsx` | Pulse-animated loading placeholder |
| **EmptyState** | `src/components/ui/empty-state.tsx` | Contextual zero-data illustration with call-to-action button |
| **ErrorState** | `src/components/ui/error-state.tsx` | Error banner with correlation ID and retry handler |

---

## 4. Workspaces & Route Hierarchy

The application consists of 12 distinct, fully implemented page routes:

```
apps/web/src/app/
├── page.tsx                           # Overview Dashboard (KPIs, recent apps, health)
├── jobs/
│   ├── page.tsx                       # Job Discovery Queue (filters, search, scoring)
│   └── [jobId]/page.tsx               # Detailed Job Match & L0 Dry-Run Inspection
├── applications/
│   ├── page.tsx                       # Application Workspace (lifecycle states, search)
│   └── [applicationId]/page.tsx       # 4-Tab Inspection (Overview, Plan, Evidence, Audit)
├── approvals/
│   └── page.tsx                       # Human-in-the-Loop Approval Queue
├── profile/
│   └── page.tsx                       # Candidate Profile & DevLeveler Sync Trigger
├── resumes/
│   └── page.tsx                       # Immutable Resumes & SHA-256 Digest Verification
├── answer-bank/
│   └── page.tsx                       # 12-Category Answer Bank & Policy Rules
├── providers/
│   └── page.tsx                       # 6-Provider Status, Risk Tiers, and Canaries
├── sessions/
│   └── page.tsx                       # Isolated Cookie Sessions (Zero Passwords)
├── automation/
│   └── page.tsx                       # Kill Switch, S0 Rate Caps, and APScheduler Window
├── analytics/
│   └── page.tsx                       # 8-Stage Lifecycle Funnel & Calibration Accuracy
└── settings/
    └── page.tsx                       # Platform Parameters, Telegram, LLM Budget Cap
```

---

## 5. API Client & Data Integration

The frontend communicates with FastAPI through `apps/web/src/lib/api-client.ts`:

```typescript
import { apiClient } from "@/lib/api-client";

// Retrieve overview metrics
const overview = await apiClient.getOverview();

// Discover jobs with multi-parameter filtering
const jobs = await apiClient.getJobs({ platform: "greenhouse", minScore: 75 });

// Human approval action
await apiClient.approveApplication("app_123", "Approved via console");

// Emergency kill switch
await apiClient.tripKillSwitch("Operator initiated emergency stop");
```

All data models are strongly typed in `apps/web/src/types/api.ts` adhering strictly to Locked Architecture v1.0 Section 14.

---

## 6. Security & Safety Invariants

1. **Zero Password Protocol**: Plaintext passwords, OTPs, and credit card numbers are strictly banned from UI storage and inputs.
2. **Real-Submit Gate Locked**: Form submission buttons do NOT exist. Actions only trigger supervised dry-runs (`L0`), form inspection, and screenshot verification.
3. **Session Cookie Isolation**: Manual login opens an isolated browser context saving session cookies directly to `worker/sessions/` without credential interception.
4. **Daily Rate Limit**: Hardcoded active limit of 2 applications/day (Stage S0).
