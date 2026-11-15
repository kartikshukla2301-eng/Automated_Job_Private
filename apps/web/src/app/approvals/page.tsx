"use client"

import * as React from "react"
import Link from "next/link"
import {
  CheckCircle2,
  XCircle,
  FileText,
  Building,
  Eye,
} from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { PageHeader } from "@/components/ui/page-header"
import { Dialog } from "@/components/ui/dialog"

interface ApprovalItem {
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

export default function ApprovalsPage() {
  const [selectedApp, setSelectedApp] = React.useState<ApprovalItem | null>(null)
  const [dialogAction, setDialogAction] = React.useState<"approve" | "reject" | null>(null)

  return (
    <div className="space-y-6">
      <PageHeader
        title="Approval Queue"
        description="Review staged applications before dry-run execution. Real submission is locked disabled."
        breadcrumbs={[
          { label: "Overview", href: "/" },
          { label: "Approval Queue" },
        ]}
        badge={
          <Badge variant="warning" className="gap-1 font-semibold">
            <span>2 Awaiting Review</span>
          </Badge>
        }
      />

      <div className="space-y-4">
        {[
          {
            id: "app-001",
            title: "Senior Platform Infrastructure Engineer",
            company: "Stripe",
            platform: "Greenhouse",
            score: 91,
            matchedSkills: ["Kubernetes", "Terraform", "Go", "Docker"],
            flaggedAnswers: ["Salary Expectation: $180,000"],
            missingCount: 0,
            resume: "resume_platform_v2.pdf",
          },
          {
            id: "app-005",
            title: "Principal Site Reliability Engineer",
            company: "Figma",
            platform: "Lever",
            score: 87,
            matchedSkills: ["AWS", "Distributed Systems", "PostgreSQL"],
            flaggedAnswers: ["Work Authorization: US Citizen"],
            missingCount: 0,
            resume: "resume_platform_v2.pdf",
          },
        ].map((item) => (
          <div
            key={item.id}
            className="rounded-xl border border-slate-200/80 bg-white p-5 shadow-xs space-y-4"
          >
            <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <div className="flex items-center gap-2">
                  <h3 className="text-base font-semibold text-slate-900">
                    {item.title}
                  </h3>
                  <Badge variant="secondary">{item.platform}</Badge>
                </div>
                <div className="text-xs text-slate-500 flex items-center gap-1.5 mt-0.5">
                  <Building className="size-3 text-slate-400" />
                  <span>{item.company}</span>
                  <span>•</span>
                  <span>Fit Score:</span>
                  <span className="font-bold text-emerald-600">{item.score}%</span>
                </div>
              </div>

              {/* Action Buttons */}
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
                  className="gap-1 text-red-600 border-red-200 hover:bg-red-50 hover:text-red-700"
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
                  className="gap-1 bg-emerald-600 hover:bg-emerald-700 text-white"
                >
                  <CheckCircle2 className="size-3.5" />
                  <span>Approve Application</span>
                </Button>
              </div>
            </div>

            {/* Answer & Skills Summary */}
            <div className="grid grid-cols-1 gap-4 text-xs sm:grid-cols-3 pt-3 border-t border-slate-100 bg-slate-50/50 p-3 rounded-lg">
              <div>
                <span className="text-slate-500 font-medium">Selected Resume:</span>
                <p className="font-semibold text-slate-800 mt-0.5 flex items-center gap-1">
                  <FileText className="size-3 text-slate-400" />
                  {item.resume}
                </p>
              </div>

              <div>
                <span className="text-slate-500 font-medium">Review Answers:</span>
                <p className="text-slate-800 mt-0.5">
                  {item.flaggedAnswers.join(", ")}
                </p>
              </div>

              <div>
                <span className="text-slate-500 font-medium">Skill Overlap:</span>
                <div className="flex flex-wrap gap-1 mt-0.5">
                  {item.matchedSkills.map((s) => (
                    <span
                      key={s}
                      className="rounded bg-white px-1.5 py-0.2 border border-slate-200 text-slate-700 text-[10px]"
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

      {/* Confirmation Dialog */}
      {dialogAction && selectedApp && (
        <Dialog
          open={Boolean(dialogAction)}
          onClose={() => {
            setDialogAction(null)
            setSelectedApp(null)
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
              >
                Cancel
              </Button>
              <Button
                variant={dialogAction === "approve" ? "default" : "destructive"}
                size="sm"
                onClick={() => {
                  setDialogAction(null)
                  setSelectedApp(null)
                }}
                className={dialogAction === "approve" ? "bg-emerald-600 hover:bg-emerald-700 text-white" : ""}
              >
                {dialogAction === "approve" ? "Approve for L0 Dry-Run" : "Confirm Rejection"}
              </Button>
            </>
          }
        >
          <div className="space-y-3 text-xs text-slate-600">
            {dialogAction === "approve" ? (
              <>
                <p>
                  Approving transitions the state to <strong className="text-slate-900">READY</strong>.
                  The application will be queued for safe L0 form inspection.
                </p>
                <div className="rounded-lg border border-amber-200 bg-amber-50 p-2.5 text-amber-900 text-xs">
                  <strong>Notice:</strong> Real submission gate is permanently locked disabled. Approval will NOT submit the form externally.
                </div>
              </>
            ) : (
              <p>
                Rejecting transitions the application to <strong className="text-slate-900">REJECTED</strong>.
                It will be excluded from further dry-runs and automated processing.
              </p>
            )}
          </div>
        </Dialog>
      )}
    </div>
  )
}
