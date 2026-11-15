"use client"

import * as React from "react"
import Link from "next/link"
import { useParams } from "next/navigation"
import {
  ArrowLeft,
  CheckCircle2,
  Clock,
  FileCode,
  FileText,
  History,
  Image as ImageIcon,
} from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { PageHeader } from "@/components/ui/page-header"
import { Tabs } from "@/components/ui/tabs"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"

function ApplicationDetailContent() {
  const params = useParams()
  const appId = (params?.applicationId as string) || "app-001"
  const [activeTab, setActiveTab] = React.useState("overview")

  return (
    <div className="space-y-6">
      <PageHeader
        title="Application Review & Evidence"
        description="Audited lifecycle execution and fill plan for Senior Platform Infrastructure Engineer at Stripe"
        breadcrumbs={[
          { label: "Overview", href: "/" },
          { label: "Applications", href: "/applications" },
          { label: appId },
        ]}
        badge={<Badge variant="warning">AWAITING_APPROVAL</Badge>}
        actions={
          <div className="flex items-center gap-2">
            <Link href="/applications">
              <Button variant="outline" size="sm" className="gap-1">
                <ArrowLeft className="size-4" />
                <span>Back</span>
              </Button>
            </Link>
            <Link href="/approvals">
              <Button variant="default" size="sm" className="gap-1.5 bg-blue-600 hover:bg-blue-700">
                <CheckCircle2 className="size-4" />
                <span>Review & Approve</span>
              </Button>
            </Link>
          </div>
        }
      />

      {/* Tabs Strip */}
      <Tabs
        activeTab={activeTab}
        onChange={setActiveTab}
        tabs={[
          { id: "overview", label: "Overview", icon: FileText },
          { id: "form", label: "Form Review & Answers", count: 8, icon: FileCode },
          { id: "evidence", label: "Captured Evidence", icon: ImageIcon },
          { id: "history", label: "Audit Timeline", count: 4, icon: History },
        ]}
      />

      {/* Tab: Overview */}
      {activeTab === "overview" && (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          <div className="rounded-xl border border-slate-200/80 bg-white p-5 shadow-xs lg:col-span-2 space-y-4">
            <h3 className="text-sm font-semibold text-slate-900">
              Application Metadata
            </h3>
            <div className="grid grid-cols-2 gap-4 text-xs sm:grid-cols-3">
              <div>
                <span className="text-slate-500">Application ID</span>
                <p className="font-mono font-medium text-slate-900 mt-0.5">{appId}</p>
              </div>
              <div>
                <span className="text-slate-500">Platform</span>
                <p className="font-medium text-slate-900 mt-0.5">Greenhouse</p>
              </div>
              <div>
                <span className="text-slate-500">Autonomy Level</span>
                <p className="font-medium text-slate-900 mt-0.5">L0 (Dry-Run)</p>
              </div>
              <div>
                <span className="text-slate-500">Profile Version</span>
                <p className="font-mono text-slate-900 mt-0.5">v1.0-sha256-verified</p>
              </div>
              <div>
                <span className="text-slate-500">Matching Score</span>
                <p className="font-bold text-emerald-600 mt-0.5">91%</p>
              </div>
              <div>
                <span className="text-slate-500">Submission Gate</span>
                <p className="font-semibold text-amber-700 mt-0.5">LOCKED_DISABLED</p>
              </div>
            </div>
          </div>

          <div className="rounded-xl border border-slate-200/80 bg-white p-5 shadow-xs space-y-3">
            <h3 className="text-sm font-semibold text-slate-900">
              Pre-Apply Safety Decisions
            </h3>
            <div className="space-y-2 text-xs">
              <div className="flex items-center gap-2 text-emerald-700">
                <CheckCircle2 className="size-4 text-emerald-600 shrink-0" />
                <span>Kill switch disengaged and ready</span>
              </div>
              <div className="flex items-center gap-2 text-emerald-700">
                <CheckCircle2 className="size-4 text-emerald-600 shrink-0" />
                <span>Within daily global cap (2 max)</span>
              </div>
              <div className="flex items-center gap-2 text-emerald-700">
                <CheckCircle2 className="size-4 text-emerald-600 shrink-0" />
                <span>Company cooldown verified (0 in 30d)</span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Tab: Form Review */}
      {activeTab === "form" && (
        <div className="space-y-4">
          <div className="rounded-xl border border-slate-200/80 bg-white p-5 shadow-xs">
            <h3 className="text-sm font-semibold text-slate-900 mb-3">
              Detected Fields & Fill Plan
            </h3>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Field Label & Key</TableHead>
                  <TableHead>Proposed Answer</TableHead>
                  <TableHead>Source</TableHead>
                  <TableHead>Policy</TableHead>
                  <TableHead>Confidence</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {[
                  { label: "First Name", key: "first_name", value: "Jane", source: "profile", policy: "auto", conf: "1.0" },
                  { label: "Last Name", key: "last_name", value: "Doe", source: "profile", policy: "auto", conf: "1.0" },
                  { label: "Email Address", key: "email", value: "jane.doe@example.com", source: "profile", policy: "auto", conf: "1.0" },
                  { label: "Phone Number", key: "phone", value: "+1 (555) 019-2831", source: "profile", policy: "auto", conf: "1.0" },
                  { label: "LinkedIn URL", key: "linkedin_profile", value: "https://linkedin.com/in/janedoe", source: "answer_bank", policy: "auto", conf: "1.0" },
                  { label: "GitHub URL", key: "github_profile", value: "https://github.com/janedoe", source: "answer_bank", policy: "auto", conf: "1.0" },
                  { label: "US Work Authorization", key: "authorized_us", value: "Yes", source: "answer_bank", policy: "auto+log", conf: "1.0" },
                  { label: "Salary Expectation ($)", key: "salary_expectation", value: "$180,000", source: "user", policy: "always_ask", conf: "1.0" },
                ].map((f) => (
                  <TableRow key={f.key}>
                    <TableCell>
                      <div className="font-semibold text-slate-900">{f.label}</div>
                      <div className="font-mono text-[10px] text-slate-400">{f.key}</div>
                    </TableCell>
                    <TableCell className="font-mono text-xs text-slate-800">
                      {f.value}
                    </TableCell>
                    <TableCell>
                      <Badge variant="secondary">{f.source}</Badge>
                    </TableCell>
                    <TableCell>
                      <Badge variant={f.policy === "always_ask" ? "warning" : "default"}>
                        {f.policy}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-xs font-semibold text-emerald-600">
                      {f.conf}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </div>
      )}

      {/* Tab: Evidence */}
      {activeTab === "evidence" && (
        <div className="rounded-xl border border-slate-200/80 bg-white p-5 shadow-xs space-y-4">
          <h3 className="text-sm font-semibold text-slate-900">
            Cryptographic Evidence Bundle (L0 Dry-Run)
          </h3>
          <p className="text-xs text-slate-500">
            Immutable snapshots captured during Playwright inspection.
          </p>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <div className="rounded-lg border border-slate-200 p-4 bg-slate-50/50 space-y-2">
              <span className="text-xs font-semibold text-slate-700">Fill Plan</span>
              <p className="font-mono text-[10px] text-slate-500">fill_plan.json</p>
              <div className="text-[10px] text-emerald-600 font-mono">SHA-256 Verified</div>
            </div>

            <div className="rounded-lg border border-slate-200 p-4 bg-slate-50/50 space-y-2">
              <span className="text-xs font-semibold text-slate-700">Form DOM Snapshot</span>
              <p className="font-mono text-[10px] text-slate-500">form_schema.json</p>
              <div className="text-[10px] text-emerald-600 font-mono">SHA-256 Verified</div>
            </div>

            <div className="rounded-lg border border-slate-200 p-4 bg-slate-50/50 space-y-2">
              <span className="text-xs font-semibold text-slate-700">Visual Evidence</span>
              <p className="font-mono text-[10px] text-slate-500">evidence_screenshot.png</p>
              <div className="text-[10px] text-emerald-600 font-mono">PII Redacted</div>
            </div>
          </div>
        </div>
      )}

      {/* Tab: History */}
      {activeTab === "history" && (
        <div className="rounded-xl border border-slate-200/80 bg-white p-5 shadow-xs space-y-4">
          <h3 className="text-sm font-semibold text-slate-900">
            Immutable Audit Event Log
          </h3>
          <div className="space-y-3">
            {[
              { event: "STATE_TRANSITION", desc: "Transitioned from READY to AWAITING_APPROVAL", time: "10 mins ago" },
              { event: "FILL_PLAN_GENERATED", desc: "Generated fill plan for 8 fields without errors", time: "12 mins ago" },
              { event: "STATE_TRANSITION", desc: "Transitioned from MATCHED to READY", time: "15 mins ago" },
              { event: "CREATED", desc: "Application record created with idempotency key", time: "20 mins ago" },
            ].map((e, idx) => (
              <div key={idx} className="flex items-start gap-3 text-xs border-b border-slate-100 pb-2.5 last:border-0">
                <div className="flex size-6 items-center justify-center rounded-full bg-blue-50 text-blue-600 shrink-0 mt-0.5">
                  <Clock className="size-3" />
                </div>
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-slate-900">{e.event}</span>
                    <span className="text-slate-400 text-[11px]">{e.time}</span>
                  </div>
                  <p className="text-slate-600 mt-0.5">{e.desc}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

export default function ApplicationDetailPage() {
  return (
    <React.Suspense fallback={<div className="p-8 text-sm text-slate-500">Loading application details...</div>}>
      <ApplicationDetailContent />
    </React.Suspense>
  )
}
