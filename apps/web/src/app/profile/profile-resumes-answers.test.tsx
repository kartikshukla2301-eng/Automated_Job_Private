import * as React from "react"
import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen, fireEvent, waitFor } from "@testing-library/react"
import ProfilePage from "./page"
import ResumesPage from "../resumes/page"
import AnswerBankPage from "../answer-bank/page"
import { apiClient } from "@/lib/api-client"

// Mock apiClient methods
vi.mock("@/lib/api-client", () => ({
  apiClient: {
    syncProfile: vi.fn(),
    getResumes: vi.fn(),
    getAnswerBank: vi.fn(),
  },
}))

describe("Profile, Resume & Answer Bank Workspace (Phase 3.4)", () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it("renders candidate profile and triggers DevLeveler sync", async () => {
    vi.mocked(apiClient.syncProfile).mockResolvedValueOnce({
      status: "SYNCED",
      profile_version: "2026.11.15-v2.5",
      candidate_name: "Kartik Shukla",
      synced_at: "2026-11-15T10:00:00Z",
    })

    render(<ProfilePage />)

    expect(screen.getByText("Kartik Shukla")).toBeInTheDocument()
    expect(screen.getByText("Staff Platform & Distributed Systems Engineer")).toBeInTheDocument()
    expect(screen.getByText("Verified Technical Skills")).toBeInTheDocument()

    // Trigger sync button
    const syncButton = screen.getByRole("button", { name: /Sync from DevLeveler/i })
    fireEvent.click(syncButton)

    await waitFor(() => {
      expect(screen.getByText(/Profile successfully updated from DevLeveler/i)).toBeInTheDocument()
    })
  })

  it("renders versioned resumes with role family badges and SHA-256 hashes", async () => {
    vi.mocked(apiClient.getResumes).mockResolvedValueOnce([
      {
        id: "res-test-1",
        filename: "Test_Platform_Resume.pdf",
        role_family: "platform",
        sha256_hash: "11223344556677889900aabbccddeeff11223344556677889900aabbccddeeff",
        size_bytes: 120000,
        created_at: "2026-11-15T08:00:00Z",
        is_active: true,
        highlights: ["Designed Kubernetes clusters"],
      },
    ])

    render(<ResumesPage />)

    await waitFor(() => {
      expect(screen.getByText("Test_Platform_Resume.pdf")).toBeInTheDocument()
    })

    expect(screen.getByText("platform")).toBeInTheDocument()
    expect(screen.getByText("Active Default")).toBeInTheDocument()
  })

  it("renders Answer Bank repository with categories and policy badges", async () => {
    vi.mocked(apiClient.getAnswerBank).mockResolvedValueOnce([
      {
        id: "ans-test-1",
        category: "Work Authorization",
        question_pattern: "Eligible to work in US?",
        answer_text: "Yes, US Citizen",
        policy: "auto",
        aliases: ["work_auth"],
        updated_at: "2026-11-15T08:00:00Z",
      },
    ])

    render(<AnswerBankPage />)

    await waitFor(() => {
      expect(screen.getByText("Candidate Answer Bank")).toBeInTheDocument()
    })

    expect(screen.getByText("Eligible to work in US?")).toBeInTheDocument()
    expect(screen.getByText("Yes, US Citizen")).toBeInTheDocument()
    expect(screen.getByText("auto")).toBeInTheDocument()

    // Verify security warning banner
    expect(screen.getByText(/Section 13 Security Policy/i)).toBeInTheDocument()
  })
})
