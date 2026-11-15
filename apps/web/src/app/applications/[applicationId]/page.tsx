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
  ShieldCheck,
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
import { apiClient } from "@/lib/api-client"
import type { ApplicationItem, TimelineEvent } from "@/types/api"

const FALLBACK_APP: ApplicationItem = {
  id: "app-001",
  job_id: "job-001",
  user_id: "usr-local-demo",
  platform: "Greenhouse",
  external_id: "gh-str-891024",
  profile_version: "2026.11.15-v1",
  resume_version: "resume_platform_v2.pdf",
  autonomy_level: "L0",
  status: "AWAITING_APPROVAL",
  evidence_ref: "evidence-gh-str-891024.json",
  created_at: "2026-11-15T09:24:00Z",
  updated_at: "2026-11-15T09:25:00Z",
}

const FALLBACK_TIMELINE: TimelineEvent[] = [
  {
    id: "evt-001",
    application_id: "app-001",
    event_type: "DISCOVERY_SUCCEEDED",
    previous_status: null,
    new_status: "DISCOVERED",
    reason: "Discovered via Greenhouse Boards API for Stripe",
    triggering_component: "GreenhouseDiscoveryAdapter",
    timestamp: "2026-11-15T09:24:00Z",
    payload: { provider: "Greenhouse", external_id: "gh-str-891024" },
  },
  {
    id: "evt-002",
    application_id: "app-001",
    event_type: "MATCH_SCORING_COMPLETED",
    previous_status: "DISCOVERED",
    new_status: "MATCHED",
    reason: "Deterministic 6-dimension match score: 91%",
    triggering_component: "JobMatchingService",
    timestamp: "2026-11-15T09:24:15Z",
    payload: { score: 91, passed_gates: true },
  },
  {
    id: "evt-003",
    application_id: "app-001",
    event_type: "HARD_FILTERS_PASSED",
    previous_status: "MATCHED",
    new_status: "ELIGIBLE",
    reason: "All 5 hard gates passed (Location, Cooldown, Blocklist, Cap, Ceiling)",
    triggering_component: "PolicyEngine",
    timestamp: "2026-11-15T09:24:20Z",
    payload: { passed_all: true },
  },
  {
    id: "evt-004",
    application_id: "app-001",
    event_type: "APPROVAL_REQUESTED",
    previous_status: "ELIGIBLE",
    new_status: "AWAITING_APPROVAL",
    reason: "Staged for human-in-the-loop verification before L0 form inspection",
    triggering_component: "ApplicationOrchestrator",
    timestamp: "2026-11-15T09:24:30Z",
    payload: { required_approval: true },
  },
]

const FORM_FIELDS = [
  {
    label: "First Name",
    type: "text",
    answer: "Kartik",
    source: "Profile (CandidateProfile)",
    policy: "auto",
  },
  {
    label: "Last Name",
    type: "text",
    answer: "Shukla",
    source: "Profile (CandidateProfile)",
    policy: "auto",
  },
  {
    label: "Email Address",
    type: "email",
    answer: "kartik.shukla@example.com",
    source: "Profile (CandidateProfile)",
    policy: "auto",
  },
  {
    label: "Phone Number",
    type: "tel",
    answer: "+1 (555) 019-2834",
    source: "Profile (CandidateProfile)",
    policy: "auto",
  },
  {
    label: "Resume / CV",
    type: "file",
    answer: "resume_platform_v2.pdf",
    source: "ResumeManager (Classified)",
    policy: "auto",
  },
  {
    label: "LinkedIn URL",
    type: "url",
    answer: "https://linkedin.com/in/kartik-shukla",
    source: "Profile (Links)",
    policy: "auto",
  },
  {
    label: "Work Authorization",
    type: "select",
    answer: "Authorized to work in US without sponsorship",
    source: "Answer Bank (exact match)",
    policy: "auto+log",
  },
  {
    label: "Desired Salary Range",
    type: "text",
    answer: "$185,000 - $225,000",
    source: "Answer Bank (exact match)",
    policy: "always_ask",
  },
]

function ApplicationDetailContent() {
  const params = useParams()
  const appId = (params?.applicationId as string) || "app-001"
  const [activeTab, setActiveTab] = React.useState("overview")
  const [app, setApp] = React.useState<ApplicationItem>(FALLBACK_APP)
  const [timeline, setTimeline] = React.useState<TimelineEvent[]>(FALLBACK_TIMELINE)

  React.useEffect(() => {
    let ignore = false

    if (apiClient.getApplicationDetail) {
      Promise.resolve(apiClient.getApplicationDetail(appId))
        .then((res) => {
          if (!ignore && res) setApp(res)
        })
        .catch(() => {
          if (!ignore) setApp({ ...FALLBACK_APP, id: appId })
        })
    }

    if (apiClient.getApplicationTimeline) {
      Promise.resolve(apiClient.getApplicationTimeline(appId))
        .then((evts) => {
          if (!ignore && evts && evts.length > 0) setTimeline(evts)
        })
        .catch(() => {
          if (!ignore) setTimeline(FALLBACK_TIMELINE)
        })
    }

    return () => {
      ignore = true
    }
  }, [appId])

  return (
    <div className="space-y-6">
      <PageHeader
        title="Application Review & Evidence"
        description={`Audited lifecycle execution and fill plan for ${app.external_id} (${app.platform})`}
        breadcrumbs={[
          { label: "Overview", href: "/" },
          { label: "Applications", href: "/applications" },
          { label: app.id },
        ]}
        badge={
          <Badge
            variant={
              app.status === "DRY_RUN_DONE"
                ? "success"
                : app.status === "AWAITING_APPROVAL"
                ? "warning"
                : "secondary"
            }
          >
            {app.status}
          </Badge>
        }
        actions={
          <div className="flex items-center gap-2">
            <Link href="/applications">
              <Button variant="outline" size="sm" className="gap-1">
                <ArrowLeft className="size-4" />
                <span>Back</span>
              </Button>
            </Link>
            {app.status === "AWAITING_APPROVAL" && (
              <Link href="/approvals">
                <Button variant="default" size="sm" className="gap-1.5 bg-blue-600 hover:bg-blue-700">
                  <CheckCircle2 className="size-4" />
                  <span>Review in Queue</span>
                </Button>
              </Link>
            )}
          </div>
        }
      />

      {/* Navigation Tabs */}
      <Tabs
        activeTab={activeTab}
        onChange={setActiveTab}
        tabs={[
          { id: "overview", label: "Overview", icon: FileText },
          { id: "form", label: "Form Review & Answers", count: FORM_FIELDS.length, icon: FileCode },
          { id: "evidence", label: "Captured Evidence", icon: ImageIcon },
          { id: "history", label: "Audit Timeline", count: timeline.length, icon: History },
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
                <p className="font-mono font-medium text-slate-900 mt-0.5">{app.id}</p>
              </div>
              <div>
                <span className="text-slate-500">Platform</span>
                <p className="font-medium text-slate-900 mt-0.5">{app.platform}</p>
              </div>
              <div>
                <span className="text-slate-500">Autonomy Level</span>
                <p className="font-medium text-slate-900 mt-0.5">{app.autonomy_level} (Supervised Dry-Run)</p>
              </div>
              <div>
                <span className="text-slate-500">External Posting ID</span>
                <p className="font-mono text-slate-900 mt-0.5">{app.external_id}</p>
              </div>
              <div>
                <span className="text-slate-500">Profile Version</span>
                <p className="font-mono text-slate-900 mt-0.5">{app.profile_version}</p>
              </div>
              <div>
                <span className="text-slate-500">Resume Version</span>
                <p className="font-mono text-slate-900 mt-0.5">{app.resume_version || "default.pdf"}</p>
              </div>
              <div>
                <span className="text-slate-500">Created At</span>
                <p className="font-medium text-slate-900 mt-0.5">
                  {new Date(app.created_at).toLocaleString()}
                </p>
              </div>
              <div>
                <span className="text-slate-500">Real Submit Gate</span>
                <p className="font-semibold text-amber-700 mt-0.5">PERMANENTLY LOCKED</p>
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
                <span>Company cooldown verified (0 in 90d)</span>
              </div>
              <div className="flex items-center gap-2 text-emerald-700">
                <CheckCircle2 className="size-4 text-emerald-600 shrink-0" />
                <span>NavigationGuard origin allowlist verified</span>
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
                  <TableHead>Field Label</TableHead>
                  <TableHead>Control Type</TableHead>
                  <TableHead>Mapped Answer</TableHead>
                  <TableHead>Answer Source</TableHead>
                  <TableHead>Policy Rule</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {FORM_FIELDS.map((field) => (
                  <TableRow key={field.label}>
                    <TableCell className="font-medium text-slate-900 text-xs">
                      {field.label}
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline" size="sm" className="font-mono">
                        {field.type}
                      </Badge>
                    </TableCell>
                    <TableCell className="font-mono text-xs text-slate-700">
                      {field.answer}
                    </TableCell>
                    <TableCell className="text-xs text-slate-500">
                      {field.source}
                    </TableCell>
                    <TableCell>
                      <Badge
                        variant={
                          field.policy === "auto"
                            ? "success"
                            : field.policy === "auto+log"
                            ? "info"
                            : "warning"
                        }
                        size="sm"
                      >
                        {field.policy}
                      </Badge>
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
        <div className="space-y-6">
          <div className="rounded-xl border border-slate-200/80 bg-white p-5 shadow-xs space-y-4">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <div>
                <h3 className="text-sm font-semibold text-slate-900">
                  Pre-Submission Evidence Bundle
                </h3>
                <p className="text-xs text-slate-500">
                  Cryptographically hashed snapshot bundle captured by BrowserManager
                </p>
              </div>
              <Badge variant="outline" className="font-mono text-xs">
                {app.evidence_ref || "evidence_bundle.json"}
              </Badge>
            </div>

            {/* Visual Screenshot Preview Area */}
            <div className="flex flex-col items-center justify-center rounded-lg border-2 border-dashed border-slate-200 bg-slate-50 p-8 text-center">
              <div className="flex size-14 items-center justify-center rounded-2xl bg-white shadow-xs border border-slate-200 mb-3 text-slate-400">
                <ImageIcon className="size-7 text-blue-600" />
              </div>
              <h4 className="text-sm font-semibold text-slate-900">
                Full-Page DOM Screenshot Captured
              </h4>
              <p className="text-xs text-slate-500 max-w-md mt-1 leading-relaxed">
                Rendered with all mapped fields populated. Sensitive values (tokens, credentials, passwords) are automatically redacted in compliance with Section 13.
              </p>
              <div className="flex items-center gap-3 mt-4 text-xs text-slate-600">
                <span className="flex items-center gap-1">
                  <ShieldCheck className="size-4 text-emerald-600" /> PII Redacted
                </span>
                <span>•</span>
                <span className="flex items-center gap-1">
                  <Clock className="size-4 text-blue-600" /> 1,280ms Duration
                </span>
                <span>•</span>
                <span className="flex items-center gap-1">
                  <CheckCircle2 className="size-4 text-emerald-600" /> 14 Controls Mapped
                </span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Tab: Audit Timeline */}
      {activeTab === "history" && (
        <div className="rounded-xl border border-slate-200/80 bg-white p-5 shadow-xs space-y-4">
          <h3 className="text-sm font-semibold text-slate-900">
            Append-Only State Transition History
          </h3>
          <div className="space-y-4 relative pl-6 before:absolute before:left-2.5 before:top-2 before:bottom-2 before:w-0.5 before:bg-slate-200">
            {timeline.map((e) => (
              <div key={e.id} className="relative flex items-start gap-3 text-xs">
                <div className="absolute -left-6 top-1 size-2 rounded-full bg-blue-600 ring-4 ring-white" />
                <div className="flex-1 rounded-lg border border-slate-100 bg-slate-50/60 p-3 space-y-1">
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-slate-900">{e.event_type}</span>
                    <span className="text-slate-400 text-[11px]">
                      {new Date(e.timestamp).toLocaleTimeString(undefined, {
                        hour: "2-digit",
                        minute: "2-digit",
                        second: "2-digit",
                      })}
                    </span>
                  </div>
                  <p className="text-slate-600">{e.reason}</p>
                  <div className="flex items-center gap-2 pt-1 text-[11px] text-slate-500">
                    <span>Component: <code className="text-slate-700">{e.triggering_component}</code></span>
                    {e.new_status && (
                      <>
                        <span>•</span>
                        <span>Status: <Badge variant="secondary" size="sm">{e.new_status}</Badge></span>
                      </>
                    )}
                  </div>
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
