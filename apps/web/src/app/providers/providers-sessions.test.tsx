import * as React from "react"
import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen, fireEvent, waitFor } from "@testing-library/react"
import ProvidersPage from "./page"
import SessionsPage from "../sessions/page"
import { apiClient } from "@/lib/api-client"

// Mock apiClient methods
vi.mock("@/lib/api-client", () => ({
  apiClient: {
    getProviderStatus: vi.fn(),
    runCanary: vi.fn(),
    getSessions: vi.fn(),
    verifySession: vi.fn(),
    clearSession: vi.fn(),
  },
}))

describe("Providers & Browser Session Management Workspace (Phase 3.5)", () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it("renders 6 provider cards with risk tiers and LinkedIn L1 cap", async () => {
    vi.mocked(apiClient.getProviderStatus).mockRejectedValueOnce(new Error("Offline mode"))

    render(<ProvidersPage />)

    await waitFor(() => {
      expect(screen.getByText("Greenhouse")).toBeInTheDocument()
    })

    expect(screen.getByText("Lever")).toBeInTheDocument()
    expect(screen.getByText("Ashby")).toBeInTheDocument()
    expect(screen.getByText("Naukri")).toBeInTheDocument()
    expect(screen.getByText("Wellfound")).toBeInTheDocument()
    expect(screen.getByText("LinkedIn (Easy Apply)")).toBeInTheDocument()

    // Verify LinkedIn L1 cap is displayed
    expect(screen.getByText("Capped at L1 Max")).toBeInTheDocument()
  })

  it("triggers canary health check and renders success banner", async () => {
    vi.mocked(apiClient.getProviderStatus).mockRejectedValueOnce(new Error("Offline mode"))
    vi.mocked(apiClient.runCanary).mockResolvedValueOnce({
      provider: "greenhouse",
      success: true,
      status: "PASSED",
      fields_detected: 14,
      duration_ms: 780,
      timestamp: "2026-11-15T10:00:00Z",
    })

    render(<ProvidersPage />)

    await waitFor(() => {
      expect(screen.getByText("Greenhouse")).toBeInTheDocument()
    })

    // Find and click Run Canary button for Greenhouse
    const canaryButtons = screen.getAllByRole("button", { name: /Run Canary/i })
    fireEvent.click(canaryButtons[0])

    await waitFor(() => {
      expect(screen.getByText(/Canary Passed: 14 fields detected/i)).toBeInTheDocument()
    })
  })

  it("renders browser sessions and displays zero credential storage banner", async () => {
    vi.mocked(apiClient.getSessions).mockRejectedValueOnce(new Error("Offline mode"))
    vi.mocked(apiClient.verifySession).mockResolvedValueOnce({ status: "VERIFIED" })

    render(<SessionsPage />)

    await waitFor(() => {
      expect(screen.getByText("Browser Sessions & Authentication")).toBeInTheDocument()
    })

    // Verify security banner
    expect(screen.getByText(/Zero Plaintext Credential Protocol/i)).toBeInTheDocument()

    // Verify session cards exist
    expect(screen.getByText("naukri")).toBeInTheDocument()
    expect(screen.getByText("wellfound")).toBeInTheDocument()
    expect(screen.getByText("linkedin")).toBeInTheDocument()

    // Trigger verify session button
    const verifyButtons = screen.getAllByRole("button", { name: /Verify Freshness/i })
    fireEvent.click(verifyButtons[0])

    await waitFor(() => {
      expect(screen.getByText(/verified fresh and active/i)).toBeInTheDocument()
    })
  })
})
