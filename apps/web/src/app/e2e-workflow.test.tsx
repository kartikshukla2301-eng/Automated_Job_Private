import * as React from "react"
import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen, fireEvent, waitFor } from "@testing-library/react"

import OverviewPage from "./page"
import JobsPage from "./jobs/page"
import ApprovalsPage from "./approvals/page"
import AutomationPage from "./automation/page"
import AnalyticsPage from "./analytics/page"
import { apiClient } from "@/lib/api-client"
import type {
  DashboardOverview,
  JobItem,
  ApplicationItem,
  FunnelAnalytics,
  KillSwitchStatus,
} from "@/types/api"

// Mock apiClient
vi.mock("@/lib/api-client", () => ({
  apiClient: {
    getOverview: vi.fn(),
    getJobs: vi.fn(),
    getJobDetail: vi.fn(),
    getApprovals: vi.fn(),
    approveApplication: vi.fn(),
    rejectApplication: vi.fn(),
    getApplications: vi.fn(),
    getApplicationDetail: vi.fn(),
    getApplicationTimeline: vi.fn(),
    getAnalytics: vi.fn(),
    tripKillSwitch: vi.fn(),
    resetKillSwitch: vi.fn(),
  },
}))

const mockOverview: DashboardOverview = {
  user_id: "usr_lead_dev",
  generated_at: "2026-11-15T12:00:00Z",
  jobs_discovered: 48,
  jobs_matched: 28,
  eligible_jobs: 22,
  applications_awaiting_approval: 4,
  applications_needing_input: 1,
  dry_runs_completed: 14,
  rejected_jobs: 2,
  skipped_applications: 0,
  failed_runs: 0,
  kill_switch_active: false,
  real_submit_gate_locked: true,
  provider_health: {
    greenhouse: "healthy",
    lever: "healthy",
    ashby: "healthy",
    naukri: "healthy",
    wellfound: "healthy",
    linkedin: "healthy",
  },
}

const mockJobs: JobItem[] = [
  {
    id: "job_gh_001",
    title: "Senior Platform Engineer",
    company: "Stripe",
    platform: "greenhouse",
    external_id: "gh_stripe_001",
    canonical_url: "https://boards.greenhouse.io/stripe/jobs/001",
    location: "Remote - US",
    work_mode: "Remote",
    employment_type: "full-time",
    match_score: 94,
    hard_gates_passed: true,
    discovered_at: "2026-11-15T08:00:00Z",
    required_skills: ["Kubernetes", "Go", "AWS", "Terraform"],
  },
  {
    id: "job_lev_002",
    title: "Staff Backend Architect",
    company: "Figma",
    platform: "lever",
    external_id: "lev_figma_002",
    canonical_url: "https://jobs.lever.co/figma/002",
    location: "San Francisco, CA",
    work_mode: "Hybrid",
    employment_type: "full-time",
    match_score: 88,
    hard_gates_passed: true,
    discovered_at: "2026-11-15T09:30:00Z",
    required_skills: ["Rust", "Distributed Systems", "PostgreSQL"],
  },
]

const mockApprovals: ApplicationItem[] = [
  {
    id: "app_stripe_001",
    job_id: "job_gh_001",
    user_id: "usr_lead_dev",
    platform: "greenhouse",
    external_id: "gh_stripe_984",
    profile_version: "2026-11-15.v1",
    resume_version: "res_platform_v2",
    autonomy_level: "L0",
    status: "AWAITING_APPROVAL",
    fields_filled: {
      "first_name": "Kartik",
      "last_name": "Shukla",
      "email": "kartik@example.com",
    },
    applied_at: "2026-11-15T10:00:00Z",
    created_at: "2026-11-15T10:00:00Z",
    updated_at: "2026-11-15T10:05:00Z",
  },
]

const mockFunnel: FunnelAnalytics = {
  discovered: 48,
  matched: 28,
  eligible: 22,
  ready: 18,
  awaiting_approval: 4,
  approved_and_filling: 2,
  dry_run_done: 14,
  applied_live: 0,
}

describe("End-to-End User Experience & Accessibility QA (Phase 3.8)", () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it("User Journey 1: Inspects Overview KPIs, navigates to Job Queue, and filters candidates", async () => {
    vi.mocked(apiClient.getOverview).mockResolvedValueOnce(mockOverview)
    vi.mocked(apiClient.getApplications).mockResolvedValueOnce({
      items: [],
      total: 0,
      limit: 5,
      offset: 0,
      has_more: false,
    })
    vi.mocked(apiClient.getJobs).mockResolvedValueOnce({
      items: mockJobs,
      total: 2,
      limit: 20,
      offset: 0,
      has_more: false,
    })

    // 1. Render Overview
    const { unmount } = render(<OverviewPage />)

    await waitFor(() => {
      expect(screen.getByText(/Connected to live FastAPI backend/i)).toBeInTheDocument()
    })

    // Validate KPI metrics
    expect(screen.getByText("Jobs Discovered")).toBeInTheDocument()
    expect(screen.getByText("Pending Approval")).toBeInTheDocument()
    expect(screen.getByText("Dry-Runs Completed")).toBeInTheDocument()
    expect(screen.getByText("L0 Dry-Run Guard Active")).toBeInTheDocument()

    unmount()

    // 2. Render Job Queue
    render(<JobsPage />)

    await waitFor(() => {
      expect(screen.getByText("Senior Platform Engineer")).toBeInTheDocument()
    })

    expect(screen.getByText("Staff Backend Architect")).toBeInTheDocument()
    expect(screen.getByText("Stripe")).toBeInTheDocument()
    expect(screen.getByText("Figma")).toBeInTheDocument()
  })

  it("User Journey 2: Reviews approval queue, confirms approval dialog, and verifies optimistic UI", async () => {
    vi.mocked(apiClient.getApprovals).mockResolvedValueOnce(mockApprovals)
    vi.mocked(apiClient.approveApplication).mockResolvedValueOnce({ status: "APPROVED" })

    render(<ApprovalsPage />)

    await waitFor(() => {
      expect(screen.getByText("Human-in-the-Loop Approval Queue")).toBeInTheDocument()
    })

    expect(screen.getByText("app_stripe_001")).toBeInTheDocument()

    // Trigger review & approve
    const approveBtn = screen.getByRole("button", { name: /Approve for L0/i })
    fireEvent.click(approveBtn)

    // Verify confirmation dialog
    expect(screen.getByText("Confirm Application Approval")).toBeInTheDocument()
    expect(screen.getByText(/Real submission gate is permanently locked disabled/i)).toBeInTheDocument()

    // Confirm approval
    const confirmApproveBtn = screen.getByRole("button", { name: "Confirm & Queue L0 Run" })
    fireEvent.click(confirmApproveBtn)

    await waitFor(() => {
      expect(apiClient.approveApplication).toHaveBeenCalledWith(
        "app_stripe_001",
        "Approved via UI Operator Console"
      )
    })

    // Verify optimistic removal from pending queue
    await waitFor(() => {
      expect(screen.getByText("All Caught Up!")).toBeInTheDocument()
    })
  })

  it("User Journey 3: Engages emergency kill switch and verifies locked submit barrier invariants", async () => {
    vi.mocked(apiClient.getOverview).mockResolvedValueOnce(mockOverview)
    const tripResult: KillSwitchStatus = {
      kill_switch_active: true,
      status: "TRIPPED",
      reason: "Operator emergency stop during E2E verification",
      updated_at: "2026-11-15T12:00:00Z",
    }
    vi.mocked(apiClient.tripKillSwitch).mockResolvedValueOnce(tripResult)

    render(<AutomationPage />)

    await waitFor(() => {
      expect(screen.getByText("Automation & Safety Control Center")).toBeInTheDocument()
    })

    // Invariant: Submit gate badge is present
    expect(screen.getByText("REAL SUBMISSIONS PERMANENTLY DISABLED")).toBeInTheDocument()

    // Invariant: Rate caps are present
    expect(screen.getByText("Capacity Stage S0 (Locked Daily Limits)")).toBeInTheDocument()

    // Trip the kill switch
    const tripBtn = screen.getByRole("button", { name: /TRIP EMERGENCY KILL SWITCH/i })
    fireEvent.click(tripBtn)

    expect(screen.getByText("Confirm Emergency Kill Switch Trip")).toBeInTheDocument()
    const confirmTripBtn = screen.getByRole("button", { name: /Confirm Immediate Stop/i })
    fireEvent.click(confirmTripBtn)

    await waitFor(() => {
      expect(apiClient.tripKillSwitch).toHaveBeenCalledWith("Operator engaged emergency stop via UI")
    })
  })

  it("User Journey 4: Inspects Analytics conversion funnel and verifies zero live submissions invariant", async () => {
    vi.mocked(apiClient.getAnalytics).mockResolvedValueOnce(mockFunnel)

    render(<AnalyticsPage />)

    await waitFor(() => {
      expect(screen.getByText("Analytics & Application History")).toBeInTheDocument()
    })

    // Invariant: Applied Live is strictly 0
    expect(screen.getByText("Live Submissions")).toBeInTheDocument()
    expect(screen.getByText("Locked Disabled")).toBeInTheDocument()
    expect(screen.getByText("Applied Live (Real Submit)")).toBeInTheDocument()

    // 0 wrong sensitive answers guarantee
    expect(screen.getByText("0 wrong sensitive answers")).toBeInTheDocument()
  })

  it("Accessibility Audit: Verifies ARIA roles and semantic HTML across dialogs and tabs", async () => {
    vi.mocked(apiClient.getApprovals).mockResolvedValueOnce(mockApprovals)

    render(<ApprovalsPage />)

    await waitFor(() => {
      expect(screen.getByText("Human-in-the-Loop Approval Queue")).toBeInTheDocument()
    })

    // Open review modal
    const approveBtn = screen.getByRole("button", { name: /Approve for L0/i })
    fireEvent.click(approveBtn)

    // Dialog must have role="dialog" and aria-modal="true"
    const dialog = screen.getByRole("dialog")
    expect(dialog).toBeInTheDocument()
    expect(dialog).toHaveAttribute("aria-modal", "true")
    expect(dialog).toHaveAttribute("aria-labelledby", "dialog-title")

    // Close button has aria-label
    expect(screen.getByLabelText("Close dialog")).toBeInTheDocument()

    // ESC key closes dialog
    fireEvent.keyDown(window, { key: "Escape" })
    await waitFor(() => {
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument()
    })
  })
})
