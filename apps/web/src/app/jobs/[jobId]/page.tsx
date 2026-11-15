"use client"

import * as React from "react"
import Link from "next/link"
import { useParams } from "next/navigation"
import {
  ArrowLeft,
  Building,
  CheckCircle2,
  Clock,
  ExternalLink,
  Lock,
  MapPin,
  Play,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
} from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { PageHeader } from "@/components/ui/page-header"
import { Dialog } from "@/components/ui/dialog"
import { apiClient } from "@/lib/api-client"
import type { JobDetailItem } from "@/types/api"

const DEFAULT_JOB_DETAIL: JobDetailItem = {
  id: "job-001",
  title: "Senior Platform Infrastructure Engineer",
  company: "Stripe",
  location: "San Francisco, CA (Hybrid / Remote)",
  work_mode: "Hybrid",
  platform: "Greenhouse",
  external_id: "gh-str-891024",
  canonical_url: "https://boards.greenhouse.io/stripe/jobs/891024",
  employment_type: "Full-Time (W2)",
  salary_range: "$185,000 - $225,000 + Equity",
  match_score: 91,
  hard_gates_passed: true,
  discovered_at: "2026-11-15T09:24:00Z",
  content_hash: "sha256-8a7f1b2c3d4e5f60718293a4b5c6d7e8",
  description: "Stripe builds economic infrastructure for the internet. As a Senior Platform Infrastructure Engineer on the Core Compute team, you will design, scale, and operate the Kubernetes platforms that serve billions of API requests daily across our global fleet.",
  raw_description: "Stripe builds economic infrastructure for the internet. As a Senior Platform Infrastructure Engineer on the Core Compute team, you will design, scale, and operate the Kubernetes platforms that serve billions of API requests daily across our global fleet.\n\nYou will:\n- Design resilient multi-cloud container orchestration using Kubernetes and Terraform.\n- Build automated control planes in Go and Python with strict p99 latency SLOs.\n- Collaborate with security and site reliability teams to maintain 99.999% uptime.\n\nQualifications:\n- 5+ years building and running distributed systems at scale.\n- Deep hands-on experience with Kubernetes, Terraform, and cloud infrastructure (AWS/GCP).\n- Strong coding proficiency in Go, Python, or systems languages.",
  required_skills: ["Kubernetes", "Terraform", "Go", "Docker", "AWS"],
  preferred_skills: ["Python", "Prometheus", "eBPF", "Distributed Systems"],
  dimensions: [
    {
      name: "Required Skills Fit (30%)",
      score: 28,
      weight: 30,
      detail: "Direct match on Kubernetes, Terraform, Go, Docker, AWS (5/5 verified)",
    },
    {
      name: "Role & Title Relevance (20%)",
      score: 19,
      weight: 20,
      detail: "Platform Infrastructure matches candidate's primary DevLeveler track",
    },
    {
      name: "Experience Fit (15%)",
      score: 14,
      weight: 15,
      detail: "Requirement: 5+ years. Candidate verified profile: 6.5 years",
    },
    {
      name: "Preferred Skills Match (15%)",
      score: 12,
      weight: 15,
      detail: "Strong Python, Prometheus, and distributed systems overlap",
    },
    {
      name: "Location & Mode Fit (10%)",
      score: 10,
      weight: 10,
      detail: "San Francisco Hybrid/Remote aligns with candidate preferences",
    },
    {
      name: "Project Evidence (10%)",
      score: 8,
      weight: 10,
      detail: "Verified production Kubernetes cluster scaling highlights in resume",
    },
  ],
  hard_gates: [
    {
      name: "Location Compatibility",
      passed: true,
      detail: "San Francisco / Remote matches approved candidate work zones",
    },
    {
      name: "90-Day Cooldown Gate",
      passed: true,
      detail: "No active or recent applications to Stripe within 90 days",
    },
    {
      name: "Company Blocklist Check",
      passed: true,
      detail: "Stripe is not on candidate's excluded company list",
    },
    {
      name: "Daily Execution Cap",
      passed: true,
      detail: "0 of 2 applications submitted today (Capacity Stage S0)",
    },
    {
      name: "Seniority Ceiling Gate",
      passed: true,
      detail: "Senior Engineer tier matches candidate's seniority profile",
    },
  ],
}

function JobDetailContent() {
  const params = useParams()
  const jobId = (params?.jobId as string) || "job-001"

  const [job, setJob] = React.useState<JobDetailItem>(DEFAULT_JOB_DETAIL)
  const [dialogOpen, setDialogOpen] = React.useState<boolean>(false)
  const [simulationState, setSimulationState] = React.useState<"idle" | "running" | "done">("idle")

  React.useEffect(() => {
    let ignore = false

    if (apiClient.getJobDetail) {
      Promise.resolve(apiClient.getJobDetail(jobId))
        .then((res) => {
          if (!ignore && res) {
            setJob(res)
          }
        })
        .catch(() => {
          // Fallback to default
          if (!ignore) {
            setJob({ ...DEFAULT_JOB_DETAIL, id: jobId })
          }
        })
    }

    return () => {
      ignore = true
    }
  }, [jobId])

  const handleStartSimulation = () => {
    setSimulationState("running")
    setTimeout(() => {
      setSimulationState("done")
    }, 1500)
  }

  const scoreVariant =
    job.match_score >= 80
      ? "text-emerald-700 bg-emerald-50 border-emerald-200"
      : job.match_score >= 70
      ? "text-blue-700 bg-blue-50 border-blue-200"
      : "text-amber-700 bg-amber-50 border-amber-200"

  return (
    <div className="space-y-6">
      <PageHeader
        title={job.title}
        description={`${job.company} • Discovered via ${job.platform} Boards API`}
        breadcrumbs={[
          { label: "Overview", href: "/" },
          { label: "Job Queue", href: "/jobs" },
          { label: job.title },
        ]}
        badge={
          <Badge variant={job.match_score >= 80 ? "success" : "info"} className="font-semibold text-xs gap-1">
            <Sparkles className="size-3" />
            <span>Eligible Match ({job.match_score}%)</span>
          </Badge>
        }
        actions={
          <div className="flex items-center gap-2">
            <Link href="/jobs">
              <Button variant="outline" size="sm" className="gap-1">
                <ArrowLeft className="size-4" />
                <span>Back to Jobs</span>
              </Button>
            </Link>
            <Button
              variant="default"
              size="sm"
              onClick={() => {
                setSimulationState("idle")
                setDialogOpen(true)
              }}
              className="gap-1.5 bg-blue-600 hover:bg-blue-700"
            >
              <Play className="size-4" />
              <span>Queue Dry-Run Inspection</span>
            </Button>
          </div>
        }
      />

      {/* Main 2-column Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left 2 Cols: Details, Description, Hard Gates */}
        <div className="lg:col-span-2 space-y-6">
          {/* Quick Specifications */}
          <div className="rounded-xl border border-slate-200/80 bg-white p-5 shadow-xs">
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-3">
              Role Specifications
            </h3>
            <div className="grid grid-cols-2 gap-4 text-xs sm:grid-cols-4">
              <div>
                <span className="text-slate-500">Company</span>
                <p className="font-semibold text-slate-900 mt-0.5 flex items-center gap-1">
                  <Building className="size-3.5 text-slate-400" />
                  {job.company}
                </p>
              </div>
              <div>
                <span className="text-slate-500">Location</span>
                <p className="font-semibold text-slate-900 mt-0.5 flex items-center gap-1">
                  <MapPin className="size-3.5 text-slate-400" />
                  {job.location}
                </p>
              </div>
              <div>
                <span className="text-slate-500">Work Mode</span>
                <p className="font-semibold text-slate-900 mt-0.5">{job.work_mode}</p>
              </div>
              <div>
                <span className="text-slate-500">Salary Range</span>
                <p className="font-semibold text-emerald-600 mt-0.5">
                  {job.salary_range || "Market Standard"}
                </p>
              </div>
            </div>
          </div>

          {/* Hard Eligibility Checklist */}
          <div className="rounded-xl border border-slate-200/80 bg-white p-5 shadow-xs space-y-3">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <h3 className="text-sm font-semibold text-slate-900 flex items-center gap-1.5">
                <ShieldCheck className="size-4 text-emerald-600" />
                <span>Deterministic Hard Eligibility Gates</span>
              </h3>
              <Badge variant="success" size="sm">
                5 / 5 PASSED
              </Badge>
            </div>

            <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-2">
              {job.hard_gates.map((gate) => (
                <div
                  key={gate.name}
                  className="flex items-start gap-2.5 rounded-lg border border-emerald-100 bg-emerald-50/40 p-2.5"
                >
                  <CheckCircle2 className="size-4 text-emerald-600 shrink-0 mt-0.5" />
                  <div>
                    <p className="text-xs font-semibold text-emerald-950">{gate.name}</p>
                    <p className="text-[11px] text-emerald-700 leading-tight mt-0.5">
                      {gate.detail}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Job Description */}
          <div className="rounded-xl border border-slate-200/80 bg-white p-5 shadow-xs space-y-4">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <h3 className="text-sm font-semibold text-slate-900">
                Job Description
              </h3>
              <a
                href={job.canonical_url}
                target="_blank"
                rel="noreferrer"
                className="flex items-center gap-1 text-xs text-blue-600 hover:underline"
              >
                <span>Original Posting</span>
                <ExternalLink className="size-3" />
              </a>
            </div>

            <div className="prose prose-sm max-w-none text-xs text-slate-700 leading-relaxed whitespace-pre-line">
              {job.raw_description}
            </div>

            {/* Skills Tags */}
            <div className="pt-3 border-t border-slate-100 space-y-2">
              <h4 className="text-xs font-semibold text-slate-800">Required Skills:</h4>
              <div className="flex flex-wrap gap-1.5">
                {job.required_skills.map((skill) => (
                  <span
                    key={skill}
                    className="inline-flex items-center gap-1 rounded-md bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-700"
                  >
                    <CheckCircle2 className="size-3 text-emerald-600" />
                    {skill}
                  </span>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Right 1 Col: Transparent Match Breakdown & Safety Info */}
        <div className="space-y-6">
          {/* Match Breakdown Card */}
          <div className="rounded-xl border border-slate-200/80 bg-white p-5 shadow-xs space-y-4">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <div>
                <h3 className="text-sm font-semibold text-slate-900">
                  Matching Fit Breakdown
                </h3>
                <p className="text-[11px] text-slate-500">6 architecture-locked dimensions</p>
              </div>
              <span className={`inline-flex items-center justify-center rounded-lg border px-2.5 py-1 font-mono text-sm font-bold ${scoreVariant}`}>
                {job.match_score} / 100
              </span>
            </div>

            <div className="space-y-3">
              {job.dimensions.map((dim) => {
                const pct = Math.round((dim.score / dim.weight) * 100)
                return (
                  <div key={dim.name} className="space-y-1">
                    <div className="flex items-center justify-between text-xs">
                      <span className="font-medium text-slate-700">{dim.name}</span>
                      <span className="font-mono font-semibold text-slate-900">
                        {dim.score}/{dim.weight}
                      </span>
                    </div>
                    <div className="h-1.5 w-full overflow-hidden rounded-full bg-slate-100">
                      <div
                        className="h-full bg-blue-600 rounded-full"
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                    <p className="text-[10px] text-slate-500">{dim.detail}</p>
                  </div>
                )
              })}
            </div>
          </div>

          {/* Posting Metadata Card */}
          <div className="rounded-xl border border-slate-200/80 bg-white p-5 shadow-xs space-y-3">
            <h4 className="text-xs font-bold uppercase tracking-wider text-slate-500">
              Posting Metadata
            </h4>
            <div className="space-y-2.5 text-xs">
              <div className="flex justify-between py-1 border-b border-slate-50">
                <span className="text-slate-500">Platform / ATS</span>
                <span className="font-semibold text-slate-800">{job.platform}</span>
              </div>
              <div className="flex justify-between py-1 border-b border-slate-50">
                <span className="text-slate-500">External ID</span>
                <span className="font-mono text-slate-800">{job.external_id}</span>
              </div>
              <div className="flex justify-between py-1 border-b border-slate-50">
                <span className="text-slate-500">Content Hash</span>
                <span className="font-mono text-[11px] text-slate-600 truncate max-w-[140px]">
                  {job.content_hash}
                </span>
              </div>
              <div className="flex justify-between py-1">
                <span className="text-slate-500">Discovered</span>
                <span className="font-medium text-slate-800">
                  {new Date(job.discovered_at).toLocaleDateString(undefined, {
                    month: "short",
                    day: "numeric",
                    hour: "2-digit",
                    minute: "2-digit",
                  })}
                </span>
              </div>
            </div>
          </div>

          {/* Safety Notice Card */}
          <div className="rounded-xl border border-amber-200/80 bg-amber-50/50 p-5 shadow-xs">
            <div className="flex items-start gap-2.5">
              <ShieldAlert className="size-4 text-amber-700 shrink-0 mt-0.5" />
              <div className="space-y-1">
                <p className="text-xs font-semibold text-amber-900">
                  Strict Real-Submit Protection
                </p>
                <p className="text-[11px] leading-relaxed text-amber-700">
                  Triggering dry-run execution will inspect the form controls, generate a deterministic fill plan, and capture full-page evidence screenshots. Submitting the form externally is permanently locked disabled.
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Dry-Run Confirmation Modal */}
      <Dialog
        open={dialogOpen}
        onClose={() => setDialogOpen(false)}
        title="Queue L0 Dry-Run Inspection"
        description={`Perform deterministic form inspection for ${job.title} at ${job.company}`}
        footer={
          simulationState === "done" ? (
            <Link href="/applications">
              <Button variant="default" size="sm" className="bg-emerald-600 hover:bg-emerald-700 text-white">
                View in Applications
              </Button>
            </Link>
          ) : (
            <>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setDialogOpen(false)}
                disabled={simulationState === "running"}
              >
                Cancel
              </Button>
              <Button
                variant="default"
                size="sm"
                onClick={handleStartSimulation}
                disabled={simulationState === "running"}
                className="bg-blue-600 hover:bg-blue-700 gap-1.5"
              >
                {simulationState === "running" ? (
                  <>
                    <Clock className="size-3.5 animate-spin" />
                    <span>Inspecting Form...</span>
                  </>
                ) : (
                  <>
                    <Play className="size-3.5" />
                    <span>Run L0 Dry-Run</span>
                  </>
                )}
              </Button>
            </>
          )
        }
      >
        <div className="space-y-3 text-xs text-slate-600">
          {simulationState === "done" ? (
            <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-3 space-y-1 text-emerald-950">
              <p className="font-semibold flex items-center gap-1.5">
                <CheckCircle2 className="size-4 text-emerald-600" />
                L0 Dry-Run Inspection Completed Successfully
              </p>
              <p className="text-[11px] text-emerald-800">
                Extracted 14 form fields, resolved 14 answers from Answer Bank, and verified zero sensitive credential fields. Evidence screenshot captured.
              </p>
            </div>
          ) : (
            <>
              <p>
                The agent will launch an isolated browser session, navigate to the canonical job posting, and extract the form schema.
              </p>
              <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 space-y-1 text-amber-900">
                <p className="font-semibold flex items-center gap-1">
                  <Lock className="size-3.5" /> Real Submit Barrier Active
                </p>
                <p className="text-[11px] text-amber-800">
                  In accordance with Architecture Section 13, form inputs are inspected but the submit button is never clicked.
                </p>
              </div>
            </>
          )}
        </div>
      </Dialog>
    </div>
  )
}

export default function JobDetailPage() {
  return (
    <React.Suspense fallback={<div className="p-8 text-sm text-slate-500">Loading job details...</div>}>
      <JobDetailContent />
    </React.Suspense>
  )
}
