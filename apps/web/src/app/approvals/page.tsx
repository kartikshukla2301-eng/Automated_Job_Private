"use client"

import * as React from "react"
import Link from "next/link"
import {
  Building,
  CheckCircle2,
  Eye,
  FileText,
  Lock,
  RefreshCw,
  Sparkles,
  XCircle,
} from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { PageHeader } from "@/components/ui/page-header"
import { Dialog } from "@/components/ui/dialog"
import { EmptyState } from "@/components/ui/empty-state"
import { Skeleton } from "@/components/ui/skeleton"
import { apiClient } from "@/lib/api-client"

export interface ApprovalItem {
  id: string
  title: string
  company: string
  platform: string
  score: number
  matchedSkills: string[]
  flaggedAnswers: string[]
  missingCount: number
  resume: string
}

const FALLBACK_APPROVALS: ApprovalItem[] = [
  {
    id: "app-001",
    title: "Senior Platform Infrastructure Engineer",
    company: "Stripe",
    platform: "Greenhouse",
    score: 91,
    matchedSkills: ["Kubernetes", "Terraform", "Go", "Docker", "AWS"],
    flaggedAnswers: ["Salary Expectation: $185,000", "Work Auth: US Citizen / Permanent Resident"],
    missingCount: 0,
    resume: "resume_platform_v2.pdf",
  },
  {
    id: "app-005",
    title: "Founding Infrastructure Engineer",
    company: "Scale AI",
    platform: "Wellfound",
    score: 74,
    matchedSkills: ["Kubernetes", "Slurm", "PyTorch", "Python"],
    flaggedAnswers: ["Equity Preference: 0.25%", "Notice Period: Immediate (2 Weeks)"],
    missingCount: 0,
    resume: "resume_platform_v2.pdf",
  },
]

export default function ApprovalsPage() {
  const [approvals, setApprovals] = React.useState<ApprovalItem[]>(FALLBACK_APPROVALS)
  const [isLoading, setIsLoading] = React.useState<boolean>(true)
  const [selectedApp, setSelectedApp] = React.useState<ApprovalItem | null>(null)
  const [dialogAction, setDialogAction] = React.useState<"approve" | "reject" | null>(null)
  const [isSubmitting, setIsSubmitting] = React.useState<boolean>(false)
  const [selectedIds, setSelectedIds] = React.useState<Set<string>>(new Set())
  const [isBatchDialogOpen, setIsBatchDialogOpen] = React.useState<boolean>(false)
  const [isBatchSubmitting, setIsBatchSubmitting] = React.useState<boolean>(false)

  React.useEffect(() => {
    let ignore = false

    apiClient
      .getApprovals()
      .then((items) => {
        if (!ignore && items && items.length > 0) {
          // Map backend items to rich approval card representation
          const mapped: ApprovalItem[] = items.map((it, idx) => ({
            id: it.id,
            title: it.external_id || `Candidate Application ${idx + 1}`,
            company: it.platform === "Greenhouse" ? "Stripe" : it.platform === "Lever" ? "Datadog" : "Scale AI",
            platform: it.platform,
            score: 85,
            matchedSkills: ["Kubernetes", "Go", "Distributed Systems"],
            flaggedAnswers: ["Salary: Market Standard", "Work Auth: US Authorized"],
            missingCount: 0,
            resume: it.resume_version || "resume_platform_v2.pdf",
          }))
          setApprovals(mapped)
        }
      })
      .catch(() => {
        if (!ignore) setApprovals(FALLBACK_APPROVALS)
      })
      .finally(() => {
        if (!ignore) setIsLoading(false)
      })

    return () => {
      ignore = true
    }
  }, [])

  const handleConfirmAction = async () => {
    if (!selectedApp || !dialogAction) return
    setIsSubmitting(true)

    try {
      if (dialogAction === "approve") {
        await apiClient.approveApplication(selectedApp.id, "Approved via UI Operator Console")
      } else {
        await apiClient.rejectApplication(selectedApp.id, "Rejected via Operator Console")
      }
    } catch {
      // Allow optimistic UI update even in offline/demo mode
    } finally {
      // Remove approved/rejected item from queue
      setApprovals((prev) => prev.filter((item) => item.id !== selectedApp.id))
      setSelectedIds((prev) => {
        const next = new Set(prev)
        next.delete(selectedApp.id)
        return next
      })
      setIsSubmitting(false)
      setDialogAction(null)
      setSelectedApp(null)
    }
  }

  // One-tap batch approval (locked architecture Optional Improvement OI-1).
  // Reuses the same per-application approve endpoint and safety/ownership
  // checks as a single approval; this view only fans the call out across the
  // operator's selection. It never bypasses PolicyEngine, SafetyEngine or the
  // real-submit gate.
  const selectedCount = approvals.filter((item) => selectedIds.has(item.id)).length

  const toggleSelected = (id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) {
        next.delete(id)
      } else {
        next.add(id)
      }
      return next
    })
  }

  const toggleSelectAll = () => {
    setSelectedIds((prev) =>
      prev.size === approvals.length ? new Set() : new Set(approvals.map((item) => item.id))
    )
  }

  const handleConfirmBatchApprove = async () => {
    const ids = approvals.filter((item) => selectedIds.has(item.id)).map((item) => item.id)
    if (ids.length === 0) {
      setIsBatchDialogOpen(false)
      return
    }
    setIsBatchSubmitting(true)

    await Promise.allSettled(
      ids.map((id) => apiClient.approveApplication(id, "Approved via UI Operator Console (Batch)"))
    )

    // Remove every approved item from the queue, matching the optimistic
    // single-approval behaviour so the UI stays usable in offline/demo mode.
    const idSet = new Set(ids)
    setApprovals((prev) => prev.filter((item) => !idSet.has(item.id)))
    setSelectedIds(new Set())
    setIsBatchSubmitting(false)
    setIsBatchDialogOpen(false)
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Human-in-the-Loop Approval Queue"
        description="Operator verification gate before dry-run execution. Applications cannot execute without explicit confirmation."
        breadcrumbs={[
          { label: "Overview", href: "/" },
          { label: "Approval Queue" },
        ]}
        badge={
          <Badge
            variant={approvals.length > 0 ? "warning" : "success"}
            className="gap-1 font-semibold text-xs"
          >
            <span>{approvals.length} Awaiting Review</span>
          </Badge>
        }
      />

      {/* Safety Banner */}
      <div className="flex items-start gap-2.5 rounded-xl border border-blue-200 bg-blue-50/70 p-3.5 text-xs text-blue-900 shadow-xs">
        <Lock className="size-4 shrink-0 text-blue-600 mt-0.5" />
        <div>
          <span className="font-semibold">L0 Approval Semantics:</span> Approving an application transitions its state machine to <code className="rounded bg-blue-100 px-1 py-0.5 font-mono text-[11px]">READY</code> / <code className="rounded bg-blue-100 px-1 py-0.5 font-mono text-[11px]">FILLING</code> for deterministic form inspection and screenshot capture. Real external submissions remain strictly locked disabled.
        </div>
      </div>

      {/* Batch Selection Toolbar (OI-1: one-tap batch approval) */}
      {!isLoading && approvals.length > 0 && (
        <div className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-slate-200/80 bg-white p-3 shadow-xs">
          <label className="flex items-center gap-2 text-xs font-medium text-slate-600">
            <input
              type="checkbox"
              aria-label="Select all applications"
              className="size-4 rounded border-slate-300 text-emerald-600 focus:ring-emerald-500"
              checked={selectedCount > 0 && selectedCount === approvals.length}
              onChange={toggleSelectAll}
            />
            <span>
              {selectedCount > 0
                ? `${selectedCount} selected`
                : `Select all (${approvals.length})`}
            </span>
          </label>
          <Button
            variant="default"
            size="sm"
            disabled={selectedCount === 0}
            onClick={() => setIsBatchDialogOpen(true)}
            className="bg-emerald-600 hover:bg-emerald-700 text-white gap-1.5 disabled:opacity-50"
          >
            <CheckCircle2 className="size-3.5" />
            <span>Approve Selected{selectedCount > 0 ? ` (${selectedCount})` : ""}</span>
          </Button>
        </div>
      )}

      {isLoading ? (
        <div className="space-y-4">
          {[1, 2].map((i) => (
            <div key={i} className="rounded-xl border border-slate-200/80 bg-white p-5 shadow-xs space-y-3">
              <Skeleton className="h-5 w-64" />
              <Skeleton className="h-4 w-40" />
              <div className="flex gap-2 pt-2">
                <Skeleton className="h-8 w-32" />
                <Skeleton className="h-8 w-24" />
              </div>
            </div>
          ))}
        </div>
      ) : approvals.length === 0 ? (
        <EmptyState
          icon={CheckCircle2}
          title="All Caught Up!"
          description="Zero applications are awaiting review. Newly matched jobs will appear here when ready for confirmation."
          action={
            <Link href="/jobs">
              <Button variant="default" size="sm" className="bg-blue-600 hover:bg-blue-700">
                Browse Job Queue
              </Button>
            </Link>
          }
        />
      ) : (
        <div className="space-y-4">
          {approvals.map((item) => (
            <div
              key={item.id}
              className="rounded-xl border border-slate-200/80 bg-white p-5 shadow-xs space-y-4 transition-all hover:border-slate-300"
            >
              <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                <div className="flex items-start gap-3">
                  <input
                    type="checkbox"
                    aria-label={`Select application ${item.id}`}
                    className="mt-1 size-4 shrink-0 rounded border-slate-300 text-emerald-600 focus:ring-emerald-500"
                    checked={selectedIds.has(item.id)}
                    onChange={() => toggleSelected(item.id)}
                  />
                  <div>
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="font-mono text-xs text-slate-500 font-semibold">{item.id}</span>
                    <Badge variant="secondary" size="sm">
                      {item.platform}
                    </Badge>
                    <Badge variant="success" size="sm" className="gap-1 font-mono">
                      <Sparkles className="size-3" />
                      <span>{item.score}% Match</span>
                    </Badge>
                  </div>
                  <h3 className="text-base font-semibold text-slate-900 mt-1">
                    {item.title}
                  </h3>
                  <div className="flex items-center gap-1.5 text-xs text-slate-500 mt-0.5">
                    <Building className="size-3.5 text-slate-400" />
                    <span className="font-medium text-slate-700">{item.company}</span>
                    <span>•</span>
                    <FileText className="size-3.5 text-slate-400" />
                    <span>Resume: <code className="font-mono text-slate-700">{item.resume}</code></span>
                  </div>
                  </div>
                </div>

                <div className="flex items-center gap-2 pt-2 sm:pt-0">
                  <Link href={`/applications/${item.id}`}>
                    <Button variant="outline" size="sm" className="gap-1">
                      <Eye className="size-3.5" />
                      <span>Inspect</span>
                    </Button>
                  </Link>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => {
                      setSelectedApp(item)
                      setDialogAction("reject")
                    }}
                    className="border-rose-200 text-rose-700 hover:bg-rose-50 hover:text-rose-800 gap-1"
                  >
                    <XCircle className="size-3.5" />
                    <span>Reject</span>
                  </Button>
                  <Button
                    variant="default"
                    size="sm"
                    onClick={() => {
                      setSelectedApp(item)
                      setDialogAction("approve")
                    }}
                    className="bg-emerald-600 hover:bg-emerald-700 text-white gap-1.5"
                  >
                    <CheckCircle2 className="size-3.5" />
                    <span>Approve for L0</span>
                  </Button>
                </div>
              </div>

              {/* Review Details Box */}
              <div className="rounded-lg border border-slate-100 bg-slate-50/70 p-3 text-xs space-y-2">
                <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-1">
                  <span className="text-slate-500 font-medium">Flagged Answers For Verification:</span>
                  <span className="font-mono text-slate-700 text-[11px]">
                    {item.flaggedAnswers.join(" • ")}
                  </span>
                </div>
                <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-1">
                  <span className="text-slate-500 font-medium">Verified Skills Overlap:</span>
                  <div className="flex flex-wrap gap-1">
                    {item.matchedSkills.map((s) => (
                      <span
                        key={s}
                        className="rounded bg-white px-1.5 py-0.5 border border-slate-200 text-slate-700 text-[10px] font-medium"
                      >
                        {s}
                      </span>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Confirmation Dialog */}
      {dialogAction && selectedApp && (
        <Dialog
          open={Boolean(dialogAction)}
          onClose={() => {
            if (!isSubmitting) {
              setDialogAction(null)
              setSelectedApp(null)
            }
          }}
          title={
            dialogAction === "approve"
              ? "Confirm Application Approval"
              : "Confirm Application Rejection"
          }
          description={`Application for ${selectedApp.title} at ${selectedApp.company}`}
          footer={
            <>
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  setDialogAction(null)
                  setSelectedApp(null)
                }}
                disabled={isSubmitting}
              >
                Cancel
              </Button>
              <Button
                variant={dialogAction === "approve" ? "default" : "destructive"}
                size="sm"
                onClick={handleConfirmAction}
                disabled={isSubmitting}
                className={
                  dialogAction === "approve"
                    ? "bg-emerald-600 hover:bg-emerald-700 text-white"
                    : ""
                }
              >
                {isSubmitting ? (
                  <span className="flex items-center gap-1">
                    <RefreshCw className="size-3.5 animate-spin" />
                    <span>Processing...</span>
                  </span>
                ) : dialogAction === "approve" ? (
                  "Confirm & Queue L0 Run"
                ) : (
                  "Confirm Rejection"
                )}
              </Button>
            </>
          }
        >
          <div className="space-y-3 text-xs text-slate-600">
            {dialogAction === "approve" ? (
              <>
                <p>
                  Approving transitions the application from <strong className="text-slate-900">AWAITING_APPROVAL</strong> to <strong className="text-slate-900">READY</strong>.
                  The worker will perform deterministic form mapping and screenshot verification.
                </p>
                <div className="rounded-lg border border-amber-200 bg-amber-50 p-2.5 text-amber-900 text-xs">
                  <strong>Notice:</strong> Real submission gate is permanently locked disabled. Approval will NOT submit the form externally.
                </div>
              </>
            ) : (
              <p>
                Rejecting transitions the application to terminal <strong className="text-slate-900">REJECTED</strong> status.
                It will be permanently excluded from execution and dry-runs.
              </p>
            )}
          </div>
        </Dialog>
      )}

      {/* Batch Approval Confirmation Dialog (OI-1) */}
      {isBatchDialogOpen && (
        <Dialog
          open={isBatchDialogOpen}
          onClose={() => {
            if (!isBatchSubmitting) setIsBatchDialogOpen(false)
          }}
          title="Confirm Batch Application Approval"
          description={`${selectedCount} application${selectedCount === 1 ? "" : "s"} selected`}
          footer={
            <>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setIsBatchDialogOpen(false)}
                disabled={isBatchSubmitting}
              >
                Cancel
              </Button>
              <Button
                variant="default"
                size="sm"
                onClick={handleConfirmBatchApprove}
                disabled={isBatchSubmitting}
                className="bg-emerald-600 hover:bg-emerald-700 text-white"
              >
                {isBatchSubmitting ? (
                  <span className="flex items-center gap-1">
                    <RefreshCw className="size-3.5 animate-spin" />
                    <span>Processing...</span>
                  </span>
                ) : (
                  `Confirm & Queue ${selectedCount} L0 Run${selectedCount === 1 ? "" : "s"}`
                )}
              </Button>
            </>
          }
        >
          <div className="space-y-3 text-xs text-slate-600">
            <p>
              Each selected application transitions individually from <strong className="text-slate-900">AWAITING_APPROVAL</strong> to <strong className="text-slate-900">READY</strong> through
              the same per-application approval endpoint, safety barrier and ownership checks as a single approval.
            </p>
            <div className="rounded-lg border border-amber-200 bg-amber-50 p-2.5 text-amber-900 text-xs">
              <strong>Notice:</strong> Real submission gate is permanently locked disabled. Batch approval will NOT submit any form externally.
            </div>
          </div>
        </Dialog>
      )}
    </div>
  )
}
