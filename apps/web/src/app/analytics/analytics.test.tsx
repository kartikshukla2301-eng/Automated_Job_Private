import * as React from "react"
import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen, fireEvent, waitFor } from "@testing-library/react"
import AnalyticsPage from "./page"
import { apiClient } from "@/lib/api-client"
import type { FunnelAnalytics } from "@/types/api"

// Mock apiClient
vi.mock("@/lib/api-client", () => ({
  apiClient: {
    getAnalytics: vi.fn(),
  },
}))

const mockFunnel: FunnelAnalytics = {
  discovered: 50,
  matched: 30,
  eligible: 25,
  ready: 20,
  awaiting_approval: 5,
  approved_and_filling: 3,
  dry_run_done: 12,
  applied_live: 0,
}

describe("Analytics & Outcome Dashboard (Phase 3.7)", () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it("renders KPI cards and live lifecycle conversion funnel", async () => {
    vi.mocked(apiClient.getAnalytics).mockResolvedValueOnce(mockFunnel)

    render(<AnalyticsPage />)

    await waitFor(() => {
      expect(screen.getByText("Analytics & Application History")).toBeInTheDocument()
    })

    // Verify KPI cards
    expect(screen.getByText("Reviewed Form Accuracy")).toBeInTheDocument()
    expect(screen.getByText("100%")).toBeInTheDocument()
    expect(screen.getByText("Matching Precision")).toBeInTheDocument()
    expect(screen.getAllByText("96.2%").length).toBeGreaterThan(0)
    expect(screen.getByText("Locked Disabled")).toBeInTheDocument()

    // Verify funnel stages
    expect(screen.getByText("Discovered Jobs")).toBeInTheDocument()
    expect(screen.getByText("Matched (Score >= 75)")).toBeInTheDocument()
    expect(screen.getByText("Passed Hard Gates")).toBeInTheDocument()
    expect(screen.getByText("Ready for Review")).toBeInTheDocument()
    expect(screen.getByText("Awaiting Human Approval")).toBeInTheDocument()
    expect(screen.getByText("Dry-Run Done (L0 Supervised)")).toBeInTheDocument()
    expect(screen.getByText("Applied Live (Real Submit)")).toBeInTheDocument()
  })

  it("toggles time range filters without crashing", async () => {
    vi.mocked(apiClient.getAnalytics).mockResolvedValueOnce(mockFunnel)

    render(<AnalyticsPage />)

    await waitFor(() => {
      expect(screen.getByText("Analytics & Application History")).toBeInTheDocument()
    })

    const sevenDaysBtn = screen.getByRole("button", { name: "7 Days" })
    const thirtyDaysBtn = screen.getByRole("button", { name: "30 Days" })
    const allTimeBtn = screen.getByRole("button", { name: "All Time" })

    fireEvent.click(sevenDaysBtn)
    expect(sevenDaysBtn).toHaveClass("bg-slate-100")

    fireEvent.click(thirtyDaysBtn)
    expect(thirtyDaysBtn).toHaveClass("bg-slate-100")

    fireEvent.click(allTimeBtn)
    expect(allTimeBtn).toHaveClass("bg-slate-100")
  })

  it("renders matching calibration, answer quality, and post-submission outcome sections", async () => {
    vi.mocked(apiClient.getAnalytics).mockResolvedValueOnce(mockFunnel)

    render(<AnalyticsPage />)

    await waitFor(() => {
      expect(screen.getByText("Matching Calibration & Benchmark Accuracy")).toBeInTheDocument()
    })

    // Role families
    expect(screen.getByText("Platform Engineer")).toBeInTheDocument()
    expect(screen.getByText("Backend Engineer")).toBeInTheDocument()
    expect(screen.getByText("Full-Stack Engineer")).toBeInTheDocument()

    // Answer Bank Quality
    expect(screen.getByText("Exact Key Matches (Zero LLM)")).toBeInTheDocument()
    expect(screen.getByText("20 / 20 (100%)")).toBeInTheDocument()
    expect(screen.getByText("Unauthorized LLM Auto-Promotions")).toBeInTheDocument()

    // Outcome tracking
    expect(screen.getByText("Post-Submission Outcome Tracking")).toBeInTheDocument()
    expect(screen.getByText("Supervised L0 Operational Mode Active")).toBeInTheDocument()
  })

  it("gracefully falls back to offline mock funnel if backend is unreachable", async () => {
    vi.mocked(apiClient.getAnalytics).mockRejectedValueOnce(new Error("Network Error"))

    render(<AnalyticsPage />)

    await waitFor(() => {
      expect(screen.getByText("Discovered Jobs")).toBeInTheDocument()
    })

    expect(screen.getByText("Applied Live (Real Submit)")).toBeInTheDocument()
  })
})
