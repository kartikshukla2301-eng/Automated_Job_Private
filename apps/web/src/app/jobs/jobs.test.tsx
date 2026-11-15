import * as React from "react"
import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen, fireEvent, waitFor } from "@testing-library/react"
import JobsPage from "./page"
import JobDetailPage from "./[jobId]/page"
import { apiClient } from "@/lib/api-client"

// Mock apiClient methods
vi.mock("@/lib/api-client", () => ({
  apiClient: {
    getJobs: vi.fn(),
    getJobDetail: vi.fn(),
  },
}))

describe("Jobs Discovery & Matching Workspace (Phase 3.2)", () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it("renders discovered jobs queue with summary KPIs and table", async () => {
    vi.mocked(apiClient.getJobs).mockResolvedValueOnce({
      items: [
        {
          id: "job-test-1",
          title: "Senior Cloud Platform Engineer",
          company: "Acme Corp",
          location: "Remote (US)",
          work_mode: "Remote",
          platform: "Greenhouse",
          external_id: "gh-acme-1",
          canonical_url: "https://boards.greenhouse.io/acme/1",
          employment_type: "Full-Time",
          salary_range: "$170,000 - $210,000",
          match_score: 92,
          hard_gates_passed: true,
          discovered_at: "2026-11-15T08:00:00Z",
          required_skills: ["Kubernetes", "Go", "AWS"],
        },
      ],
      total: 1,
      limit: 50,
      offset: 0,
      has_more: false,
    })

    render(<JobsPage />)

    await waitFor(() => {
      expect(screen.getByText("Senior Cloud Platform Engineer")).toBeInTheDocument()
    })

    expect(screen.getByText("Acme Corp")).toBeInTheDocument()
    expect(screen.getAllByText("Greenhouse").length).toBeGreaterThan(0)
    expect(screen.getByText("92%")).toBeInTheDocument()
    expect(screen.getByText("Passed")).toBeInTheDocument()
  })

  it("filters jobs interactively by search query", async () => {
    // Falls back to FALLBACK_JOBS
    vi.mocked(apiClient.getJobs).mockRejectedValueOnce(new Error("Offline mode"))

    render(<JobsPage />)

    await waitFor(() => {
      expect(screen.getByText("Senior Platform Infrastructure Engineer")).toBeInTheDocument()
    })

    const searchInput = screen.getByPlaceholderText(/Search by job title, company, or skills/i)
    fireEvent.change(searchInput, { target: { value: "Datadog" } })

    // Datadog should still be visible, Stripe should be filtered out
    expect(screen.getByText("Staff Distributed Systems Engineer")).toBeInTheDocument()
    expect(screen.queryByText("Senior Platform Infrastructure Engineer")).not.toBeInTheDocument()
  })

  it("filters jobs by platform select", async () => {
    vi.mocked(apiClient.getJobs).mockRejectedValueOnce(new Error("Offline mode"))

    render(<JobsPage />)

    await waitFor(() => {
      expect(screen.getByText("Senior Platform Infrastructure Engineer")).toBeInTheDocument()
    })

    const platformSelect = screen.getByRole("combobox", { name: /Filter by Platform/i })
    fireEvent.change(platformSelect, { target: { value: "lever" } })

    // Lever jobs visible, Greenhouse hidden
    expect(screen.getByText("Staff Distributed Systems Engineer")).toBeInTheDocument()
    expect(screen.queryByText("Senior Platform Infrastructure Engineer")).not.toBeInTheDocument()
  })

  it("renders 6-dimension match breakdown and hard gates in detail page", async () => {
    vi.mocked(apiClient.getJobDetail).mockRejectedValueOnce(new Error("Offline mode"))

    render(<JobDetailPage />)

    await waitFor(() => {
      expect(screen.getByText("Matching Fit Breakdown")).toBeInTheDocument()
    })

    // Check 6 architecture-locked dimensions
    expect(screen.getByText(/Required Skills Fit/i)).toBeInTheDocument()
    expect(screen.getByText(/Role & Title Relevance/i)).toBeInTheDocument()
    expect(screen.getByText(/Experience Fit/i)).toBeInTheDocument()
    expect(screen.getByText(/Preferred Skills Match/i)).toBeInTheDocument()
    expect(screen.getByText(/Location & Mode Fit/i)).toBeInTheDocument()
    expect(screen.getByText(/Project Evidence/i)).toBeInTheDocument()

    // Check hard gates checklist
    expect(screen.getByText("Deterministic Hard Eligibility Gates")).toBeInTheDocument()
    expect(screen.getByText("5 / 5 PASSED")).toBeInTheDocument()
  })
})
