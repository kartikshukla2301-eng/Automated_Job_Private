import { describe, it, expect, vi } from "vitest"
import { render, screen } from "@testing-library/react"
import { Sidebar, navigationItems } from "./sidebar"

// Mock usePathname from next/navigation
vi.mock("next/navigation", () => ({
  usePathname: () => "/jobs",
}))

describe("Sidebar Navigation", () => {
  it("renders all 12 authoritative navigation items", () => {
    render(<Sidebar />)
    expect(navigationItems).toHaveLength(12)

    expect(screen.getByText("Overview")).toBeDefined()
    expect(screen.getByText("Job Queue")).toBeDefined()
    expect(screen.getByText("Applications")).toBeDefined()
    expect(screen.getByText("Approval Queue")).toBeDefined()
    expect(screen.getByText("Answer Bank")).toBeDefined()
    expect(screen.getByText("My Profile")).toBeDefined()
    expect(screen.getByText("Resumes")).toBeDefined()
    expect(screen.getByText("Providers")).toBeDefined()
    expect(screen.getByText("Sessions")).toBeDefined()
    expect(screen.getByText("Automation")).toBeDefined()
    expect(screen.getByText("Analytics")).toBeDefined()
    expect(screen.getByText("Settings")).toBeDefined()
  })

  it("renders brand title and safety indicator", () => {
    render(<Sidebar />)
    expect(screen.getByText("JobAgent AI")).toBeDefined()
    expect(screen.getByText("L0 Dry-Run Guard")).toBeDefined()
    expect(screen.getByText(/Real submissions locked/i)).toBeDefined()
  })

  it("handles collapsed state gracefully", () => {
    const { container } = render(<Sidebar collapsed={true} />)
    expect(container.querySelector("aside")).toBeDefined()
  })
})
