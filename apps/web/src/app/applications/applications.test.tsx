import * as React from "react"
import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen, fireEvent, waitFor } from "@testing-library/react"
import ApplicationsPage from "./page"
import ApprovalsPage from "../approvals/page"
import ApplicationDetailPage from "./[applicationId]/page"
import { apiClient } from "@/lib/api-client"

// Mock apiClient methods
vi.mock("@/lib/api-client", () => ({
  apiClient: {
    getApplications: vi.fn(),
    getApprovals: vi.fn(),
    getApplicationDetail: vi.fn(),
    getApplicationTimeline: vi.fn(),
    approveApplication: vi.fn(),
    rejectApplication: vi.fn(),
  },
}))

describe("Applications Workspace & Approval Queue (Phase 3.3)", () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it("renders applications table with status badges and KPI metrics", async () => {
    vi.mocked(apiClient.getApplications).mockResolvedValueOnce({
      items: [
        {
          id: "app-test-101",
          job_id: "job-101",
          user_id: "usr-1",
          platform: "Greenhouse",
          external_id: "gh-acme-101",
          profile_version: "v1.0",
          autonomy_level: "L0",
          status: "AWAITING_APPROVAL",
          created_at: "2026-11-15T09:00:00Z",
          updated_at: "2026-11-15T09:01:00Z",
        },
      ],
      total: 1,
      limit: 100,
      offset: 0,
      has_more: false,
    })

    render(<ApplicationsPage />)

    await waitFor(() => {
      expect(screen.getByText("app-test-101")).toBeInTheDocument()
    })

    expect(screen.getByText("gh-acme-101")).toBeInTheDocument()
    expect(screen.getAllByText("AWAITING_APPROVAL").length).toBeGreaterThan(0)
  })

  it("filters applications by search query", async () => {
    vi.mocked(apiClient.getApplications).mockRejectedValueOnce(new Error("Offline mode"))

    render(<ApplicationsPage />)

    await waitFor(() => {
      expect(screen.getByText("app-001")).toBeInTheDocument()
    })

    const searchInput = screen.getByPlaceholderText(/Search by external ID/i)
    fireEvent.change(searchInput, { target: { value: "lev-dd-440192" } })

    expect(screen.getByText("app-002")).toBeInTheDocument()
    expect(screen.queryByText("app-001")).not.toBeInTheDocument()
  })

  it("renders approval queue and triggers approval confirmation modal", async () => {
    vi.mocked(apiClient.getApprovals).mockResolvedValueOnce([
      {
        id: "app-approve-99",
        job_id: "job-99",
        user_id: "usr-1",
        platform: "Greenhouse",
        external_id: "gh-stripe-core",
        profile_version: "v1.0",
        autonomy_level: "L0",
        status: "AWAITING_APPROVAL",
        created_at: "2026-11-15T09:00:00Z",
        updated_at: "2026-11-15T09:01:00Z",
      },
    ])

    render(<ApprovalsPage />)

    await waitFor(() => {
      expect(screen.getByText(/Human-in-the-Loop Approval Queue/i)).toBeInTheDocument()
    })

    expect(screen.getByText("gh-stripe-core")).toBeInTheDocument()

    // Click Approve button to open confirmation dialog
    const approveBtn = screen.getByRole("button", { name: /Approve for L0/i })
    fireEvent.click(approveBtn)

    expect(screen.getByText("Confirm Application Approval")).toBeInTheDocument()
    expect(screen.getByText(/Real submission gate is permanently locked disabled/i)).toBeInTheDocument()
  })

  it("renders application detail page with overview, form review, and timeline tabs", async () => {
    vi.mocked(apiClient.getApplicationDetail).mockRejectedValueOnce(new Error("Offline mode"))
    vi.mocked(apiClient.getApplicationTimeline).mockRejectedValueOnce(new Error("Offline mode"))

    render(<ApplicationDetailPage />)

    await waitFor(() => {
      expect(screen.getByText(/Application Review & Evidence/i)).toBeInTheDocument()
    })

    // Overview Tab
    expect(screen.getByText("Pre-Apply Safety Decisions")).toBeInTheDocument()

    // Switch to Form Review tab
    const formTab = screen.getByRole("tab", { name: /Form Review & Answers/i })
    fireEvent.click(formTab)
    expect(screen.getByText("Detected Fields & Fill Plan")).toBeInTheDocument()
    expect(screen.getByText("Desired Salary Range")).toBeInTheDocument()

    // Switch to Audit Timeline tab
    const historyTab = screen.getByRole("tab", { name: /Audit Timeline/i })
    fireEvent.click(historyTab)
    expect(screen.getByText("Append-Only State Transition History")).toBeInTheDocument()
  })
})
