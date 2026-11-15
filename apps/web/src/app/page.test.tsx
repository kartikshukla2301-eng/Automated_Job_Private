import * as React from "react"
import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen, waitFor } from "@testing-library/react"
import OverviewPage from "./page"
import { apiClient } from "@/lib/api-client"

// Mock apiClient methods
vi.mock("@/lib/api-client", () => ({
  apiClient: {
    getOverview: vi.fn(),
    getApplications: vi.fn(),
  },
}))

describe("OverviewPage (Dashboard Phase 3.1)", () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it("renders live data and connected status when API resolves", async () => {
    vi.mocked(apiClient.getOverview).mockResolvedValueOnce({
      user_id: "usr-live-test",
      generated_at: "2026-11-15T10:00:00Z",
      jobs_discovered: 72,
      jobs_matched: 30,
      eligible_jobs: 22,
      applications_awaiting_approval: 5,
      applications_needing_input: 1,
      dry_runs_completed: 18,
      rejected_jobs: 8,
      skipped_applications: 0,
      failed_runs: 0,
      kill_switch_active: false,
      real_submit_gate_locked: true,
      provider_health: {
        greenhouse: "HEALTHY",
        lever: "HEALTHY",
        ashby: "HEALTHY",
        naukri: "HEALTHY",
        wellfound: "HEALTHY",
        linkedin: "RESTRICTED",
      },
    })

    vi.mocked(apiClient.getApplications).mockResolvedValueOnce({
      items: [
        {
          id: "app-test-01",
          job_id: "job-live-01",
          user_id: "usr-live-test",
          platform: "Greenhouse",
          external_id: "gh-live-01",
          profile_version: "2026.11.15-v1",
          autonomy_level: "L0",
          status: "AWAITING_APPROVAL",
          created_at: "2026-11-15T10:00:00Z",
          updated_at: "2026-11-15T10:05:00Z",
        },
      ],
      total: 1,
      limit: 5,
      offset: 0,
      has_more: false,
    })

    render(<OverviewPage />)

    // Verify live connected badge
    await waitFor(() => {
      expect(screen.getByText(/Connected to live FastAPI backend/i)).toBeInTheDocument()
    })

    // Verify KPI numbers from live response
    expect(screen.getByText("72")).toBeInTheDocument() // jobs discovered
    expect(screen.getByText("22")).toBeInTheDocument() // eligible jobs
    expect(screen.getByText("5")).toBeInTheDocument()  // pending approval
    expect(screen.getByText("18")).toBeInTheDocument() // dry-runs completed

    // Verify real submit gate is locked
    expect(screen.getByText("LOCKED DISABLED")).toBeInTheDocument()
  })

  it("gracefully falls back to offline demo mode when API fails", async () => {
    vi.mocked(apiClient.getOverview).mockRejectedValueOnce(
      new Error("Failed to connect to backend: ECONNREFUSED")
    )

    render(<OverviewPage />)

    // Wait for demo mode banner
    await waitFor(() => {
      expect(screen.getByText(/Offline Demo Mode/i)).toBeInTheDocument()
    })

    // Verify retry button exists
    expect(screen.getByText(/Retry Connection/i)).toBeInTheDocument()

    // Verify fallback KPI data renders
    expect(screen.getByText("Jobs Discovered")).toBeInTheDocument()
    expect(screen.getByText("L0 Dry-Run Guard Active")).toBeInTheDocument()
  })
})
