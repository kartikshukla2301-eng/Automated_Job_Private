import * as React from "react"
import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen, fireEvent, waitFor } from "@testing-library/react"
import AutomationPage from "./page"
import SettingsPage from "../settings/page"
import { apiClient } from "@/lib/api-client"
import type { DashboardOverview, KillSwitchStatus } from "@/types/api"

// Mock apiClient methods
vi.mock("@/lib/api-client", () => ({
  apiClient: {
    getOverview: vi.fn(),
    tripKillSwitch: vi.fn(),
    resetKillSwitch: vi.fn(),
  },
}))

const mockOverview: DashboardOverview = {
  user_id: "usr_default",
  generated_at: "2026-11-15T12:00:00Z",
  jobs_discovered: 10,
  jobs_matched: 5,
  eligible_jobs: 4,
  applications_awaiting_approval: 2,
  applications_needing_input: 1,
  dry_runs_completed: 8,
  rejected_jobs: 1,
  skipped_applications: 0,
  failed_runs: 0,
  kill_switch_active: false,
  real_submit_gate_locked: true,
  provider_health: { greenhouse: "healthy", lever: "healthy" },
}

describe("Automation & Safety Control Center (Phase 3.6)", () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it("renders emergency kill switch, active capacity limits, and locked submit gate banner", async () => {
    vi.mocked(apiClient.getOverview).mockResolvedValueOnce(mockOverview)

    render(<AutomationPage />)

    await waitFor(() => {
      expect(screen.getByText("Automation & Safety Control Center")).toBeInTheDocument()
    })

    // Verify locked submit gate badge
    expect(screen.getByText("REAL SUBMISSIONS PERMANENTLY DISABLED")).toBeInTheDocument()

    // Verify S0 rate cap
    expect(screen.getByText("Capacity Stage S0 (Locked Daily Limits)")).toBeInTheDocument()

    // Verify scheduler window
    expect(screen.getByText(/09:00/)).toBeInTheDocument()
    expect(screen.getByText(/23:00 IST/)).toBeInTheDocument()

    // Verify kill switch button
    expect(screen.getByRole("button", { name: /TRIP EMERGENCY KILL SWITCH/i })).toBeInTheDocument()
  })

  it("trips the kill switch upon user confirmation in dialog", async () => {
    vi.mocked(apiClient.getOverview).mockResolvedValueOnce(mockOverview)
    const tripResult: KillSwitchStatus = {
      kill_switch_active: true,
      status: "TRIPPED",
      reason: "Operator engaged emergency stop via UI",
      updated_at: "2026-11-15T12:00:00Z",
    }
    vi.mocked(apiClient.tripKillSwitch).mockResolvedValueOnce(tripResult)

    render(<AutomationPage />)

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /TRIP EMERGENCY KILL SWITCH/i })).toBeInTheDocument()
    })

    // Click trip button
    fireEvent.click(screen.getByRole("button", { name: /TRIP EMERGENCY KILL SWITCH/i }))

    // Expect dialog to open
    expect(screen.getByText("Confirm Emergency Kill Switch Trip")).toBeInTheDocument()

    // Confirm trip in dialog
    const confirmButtons = screen.getAllByRole("button", { name: /Confirm Immediate Stop/i })
    fireEvent.click(confirmButtons[0])

    await waitFor(() => {
      expect(apiClient.tripKillSwitch).toHaveBeenCalledWith("Operator engaged emergency stop via UI")
    })
  })

  it("resets the kill switch when currently active", async () => {
    vi.mocked(apiClient.getOverview).mockResolvedValueOnce({
      ...mockOverview,
      kill_switch_active: true,
    })
    const resetResult: KillSwitchStatus = {
      kill_switch_active: false,
      status: "ARMED",
      reason: "Manual reset via operator action",
      updated_at: "2026-11-15T12:05:00Z",
    }
    vi.mocked(apiClient.resetKillSwitch).mockResolvedValueOnce(resetResult)

    render(<AutomationPage />)

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /Reset Kill Switch/i })).toBeInTheDocument()
    })

    fireEvent.click(screen.getByRole("button", { name: /Reset Kill Switch/i }))

    // Dialog appears
    expect(screen.getByText("Confirm Emergency Kill Switch Reset")).toBeInTheDocument()

    // Confirm reset
    const confirmButtons = screen.getAllByRole("button", { name: /Confirm Reset & Arm/i })
    fireEvent.click(confirmButtons[0])

    await waitFor(() => {
      expect(apiClient.resetKillSwitch).toHaveBeenCalled()
    })
  })

  it("renders Settings page with connectivity, budget limits, and security invariants", () => {
    render(<SettingsPage />)

    expect(screen.getByText("Settings & Platform Configuration")).toBeInTheDocument()
    expect(screen.getByDisplayValue("http://127.0.0.1:8000")).toBeInTheDocument()
    expect(screen.getByDisplayValue("Supabase PostgreSQL (db.supabase.co)")).toBeInTheDocument()
    expect(screen.getByText("Telegram Bot Notifications")).toBeInTheDocument()
    expect(screen.getByDisplayValue("0.50")).toBeInTheDocument()
    expect(screen.getByText("Architecture v1.0 Locked")).toBeInTheDocument()
    expect(screen.getByText("ZERO Passwords")).toBeInTheDocument()

    // Test saving settings
    const saveButton = screen.getByRole("button", { name: /Save Configuration/i })
    fireEvent.click(saveButton)

    expect(screen.getByText("Local configuration saved successfully. Runtime parameters synced.")).toBeInTheDocument()
  })
})
