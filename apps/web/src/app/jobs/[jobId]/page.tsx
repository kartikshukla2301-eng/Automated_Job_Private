"use client"

import * as React from "react"
import Link from "next/link"
import { useParams } from "next/navigation"
import {
  ArrowLeft,
  CheckCircle2,
  ExternalLink,
  Play,
} from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { PageHeader } from "@/components/ui/page-header"

function JobDetailContent() {
  const params = useParams()
  const jobId = (params?.jobId as string) || "job-001"

  return (
    <div className="space-y-6">
      <PageHeader
        title="Senior Platform Infrastructure Engineer"
        description="Stripe • Discovered via Greenhouse Boards API"
        breadcrumbs={[
          { label: "Overview", href: "/" },
          { label: "Job Queue", href: "/jobs" },
          { label: `Job: ${jobId}` },
        ]}
        badge={<Badge variant="success">Eligible Match (91%)</Badge>}
        actions={
          <div className="flex items-center gap-2">
            <Link href="/jobs">
              <Button variant="outline" size="sm" className="gap-1">
                <ArrowLeft className="size-4" />
                <span>Back to Jobs</span>
              </Button>
            </Link>
            <Button variant="default" size="sm" className="gap-1.5 bg-blue-600 hover:bg-blue-700">
              <Play className="size-4" />
              <span>Simulate L0 Dry-Run</span>
            </Button>
          </div>
        }
      />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Left 2 Cols: Job Details and Content */}
        <div className="space-y-6 lg:col-span-2">
          {/* Metadata Card */}
          <div className="rounded-xl border border-slate-200/80 bg-white p-5 shadow-xs space-y-4">
            <h2 className="text-base font-semibold text-slate-900">
              Role Specifications
            </h2>
            <div className="grid grid-cols-2 gap-4 text-xs sm:grid-cols-4">
              <div>
                <span className="text-slate-500">Company</span>
                <p className="font-semibold text-slate-900 mt-0.5">Stripe</p>
              </div>
              <div>
                <span className="text-slate-500">Location</span>
                <p className="font-semibold text-slate-900 mt-0.5">San Francisco, CA</p>
              </div>
              <div>
                <span className="text-slate-500">Work Mode</span>
                <p className="font-semibold text-slate-900 mt-0.5">Remote (US)</p>
              </div>
              <div>
                <span className="text-slate-500">Platform</span>
                <p className="font-semibold text-slate-900 mt-0.5">Greenhouse</p>
              </div>
            </div>
          </div>

          {/* Job Description (Untrusted content sanitized) */}
          <div className="rounded-xl border border-slate-200/80 bg-white p-5 shadow-xs space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-base font-semibold text-slate-900">
                Job Description
              </h2>
              <a
                href="https://boards.greenhouse.io/stripe/jobs/example"
                target="_blank"
                rel="noopener noreferrer"
                className="text-xs text-blue-600 hover:underline flex items-center gap-1"
              >
                <span>Original Posting</span>
                <ExternalLink className="size-3" />
              </a>
            </div>

            <div className="prose prose-sm text-slate-700 space-y-3 text-xs leading-relaxed max-w-none">
              <p>
                Stripe is building the economic infrastructure for the internet.
                We are looking for a Senior Platform Infrastructure Engineer to scale our core Kubernetes and cloud infrastructure fleets.
              </p>
              <h4 className="font-bold text-slate-900">What you will do:</h4>
              <ul className="list-disc pl-4 space-y-1">
                <li>Architect scalable service meshes and container orchestrations on AWS & GCP.</li>
                <li>Build resilient CI/CD delivery pipelines using Terraform and Go.</li>
                <li>Partner with application teams on reliability, observability, and latency SLAs.</li>
              </ul>
              <h4 className="font-bold text-slate-900">Qualifications:</h4>
              <ul className="list-disc pl-4 space-y-1">
                <li>5+ years of software engineering in distributed systems or platform engineering.</li>
                <li>Production expertise with Kubernetes, Docker, and infrastructure-as-code.</li>
                <li>Proficiency in Go, Python, or systems languages.</li>
              </ul>
            </div>
          </div>
        </div>

        {/* Right Col: Transparent Match Breakdown */}
        <div className="space-y-6">
          <div className="rounded-xl border border-slate-200/80 bg-white p-5 shadow-xs space-y-4">
            <h3 className="text-sm font-semibold text-slate-900 flex items-center justify-between">
              <span>Matching Fit Breakdown</span>
              <span className="text-emerald-600 font-bold text-base">91 / 100</span>
            </h3>

            {/* Score Weights */}
            <div className="space-y-2.5 text-xs">
              {[
                { factor: "Required Skills (30%)", score: "28/30", pct: 93 },
                { factor: "Role Relevance (20%)", score: "19/20", pct: 95 },
                { factor: "Experience Fit (15%)", score: "14/15", pct: 93 },
                { factor: "Preferred Skills (15%)", score: "12/15", pct: 80 },
                { factor: "Location & Mode (10%)", score: "10/10", pct: 100 },
                { factor: "Project Evidence (10%)", score: "8/10", pct: 80 },
              ].map((item) => (
                <div key={item.factor} className="space-y-1">
                  <div className="flex justify-between text-slate-600">
                    <span>{item.factor}</span>
                    <span className="font-semibold text-slate-900">{item.score}</span>
                  </div>
                  <div className="h-1.5 w-full rounded-full bg-slate-100 overflow-hidden">
                    <div
                      className="h-full bg-blue-600 rounded-full"
                      style={{ width: `${item.pct}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>

            {/* Skills Detected */}
            <div className="pt-2 border-t border-slate-100 space-y-2">
              <span className="text-xs font-semibold text-slate-900">
                Verified Candidate Skills:
              </span>
              <div className="flex flex-wrap gap-1.5">
                {["Kubernetes", "Terraform", "Go", "Docker", "AWS", "Python"].map((s) => (
                  <span
                    key={s}
                    className="inline-flex items-center gap-1 rounded-md bg-emerald-50 px-2 py-0.5 text-[11px] font-medium text-emerald-700 border border-emerald-200"
                  >
                    <CheckCircle2 className="size-3 text-emerald-600" />
                    {s}
                  </span>
                ))}
              </div>
            </div>

            {/* Hard Filter Verification */}
            <div className="pt-2 border-t border-slate-100">
              <span className="text-xs font-semibold text-slate-900">
                Hard Eligibility Filters:
              </span>
              <div className="mt-1.5 flex items-center gap-1.5 text-xs text-emerald-700">
                <CheckCircle2 className="size-4 text-emerald-600 shrink-0" />
                <span>Passed all hard filters (Location, Cooldown, Company Blocklist).</span>
              </div>
            </div>
          </div>
        </div>
      </div>
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
