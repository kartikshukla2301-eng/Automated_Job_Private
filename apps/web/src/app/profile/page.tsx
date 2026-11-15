"use client"

import * as React from "react"
import { RefreshCw, Briefcase, Code2, CheckCircle2 } from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { PageHeader } from "@/components/ui/page-header"

export default function ProfilePage() {
  const [syncing, setSyncing] = React.useState(false)

  const handleSync = () => {
    setSyncing(true)
    setTimeout(() => setSyncing(false), 1000)
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Candidate Profile"
        description="Canonical profile facts sourced from DevLeveler. Values serve as the single source of truth for all form answers."
        breadcrumbs={[
          { label: "Overview", href: "/" },
          { label: "Profile" },
        ]}
        badge={
          <Badge variant="success" className="gap-1 font-semibold">
            <CheckCircle2 className="size-3.5" />
            <span>Profile Synced (v1.0)</span>
          </Badge>
        }
        actions={
          <Button
            onClick={handleSync}
            disabled={syncing}
            variant="default"
            size="sm"
            className="gap-1.5 bg-blue-600 hover:bg-blue-700"
          >
            <RefreshCw className={`size-4 ${syncing ? "animate-spin" : ""}`} />
            <span>{syncing ? "Syncing..." : "Sync from DevLeveler"}</span>
          </Button>
        }
      />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Left Column: Identity & Preferences */}
        <div className="space-y-6">
          <div className="rounded-xl border border-slate-200/80 bg-white p-5 shadow-xs space-y-4">
            <div className="flex items-center gap-3">
              <div className="flex size-12 items-center justify-center rounded-xl bg-blue-50 text-blue-600 font-bold text-lg border border-blue-100">
                JD
              </div>
              <div>
                <h3 className="text-base font-semibold text-slate-900">
                  Jane Doe
                </h3>
                <p className="text-xs text-slate-500">Staff Platform Engineer</p>
              </div>
            </div>

            <div className="space-y-2 text-xs border-t border-slate-100 pt-3">
              <div>
                <span className="text-slate-400">Email:</span>
                <p className="font-medium text-slate-900">jane.doe@example.com</p>
              </div>
              <div>
                <span className="text-slate-400">Phone:</span>
                <p className="font-medium text-slate-900">+1 (555) 019-2831</p>
              </div>
              <div>
                <span className="text-slate-400">Location:</span>
                <p className="font-medium text-slate-900">San Francisco, CA (US)</p>
              </div>
            </div>
          </div>

          <div className="rounded-xl border border-slate-200/80 bg-white p-5 shadow-xs space-y-3">
            <h4 className="text-sm font-semibold text-slate-900">
              Work Preferences
            </h4>
            <div className="space-y-2 text-xs text-slate-700">
              <div className="flex justify-between py-1 border-b border-slate-50">
                <span className="text-slate-500">Target Role</span>
                <span className="font-semibold">Platform / SRE / Backend</span>
              </div>
              <div className="flex justify-between py-1 border-b border-slate-50">
                <span className="text-slate-500">Work Mode</span>
                <span className="font-semibold">Remote or Hybrid (SF)</span>
              </div>
              <div className="flex justify-between py-1 border-b border-slate-50">
                <span className="text-slate-500">Min Base Salary</span>
                <span className="font-semibold">$175,000 / year</span>
              </div>
            </div>
          </div>
        </div>

        {/* Right 2 Columns: Experience, Education & Skills */}
        <div className="space-y-6 lg:col-span-2">
          {/* Experience */}
          <div className="rounded-xl border border-slate-200/80 bg-white p-5 shadow-xs space-y-4">
            <h3 className="text-sm font-semibold text-slate-900 flex items-center gap-2">
              <Briefcase className="size-4 text-slate-400" />
              <span>Work Experience</span>
            </h3>

            <div className="space-y-4 text-xs">
              <div className="border-l-2 border-blue-500 pl-3 space-y-1">
                <div className="flex items-center justify-between">
                  <span className="font-semibold text-slate-900 text-sm">
                    Senior Staff Platform Engineer
                  </span>
                  <span className="text-slate-400">2021 — Present</span>
                </div>
                <div className="text-blue-600 font-medium">CloudTech Solutions</div>
                <p className="text-slate-600 mt-1">
                  Scaled multi-region Kubernetes clusters handling 50k QPS. Reduced cloud spend by 35% through automated Karpenter capacity autoscaling.
                </p>
              </div>

              <div className="border-l-2 border-slate-200 pl-3 space-y-1">
                <div className="flex items-center justify-between">
                  <span className="font-semibold text-slate-900 text-sm">
                    Lead Infrastructure Engineer
                  </span>
                  <span className="text-slate-400">2018 — 2021</span>
                </div>
                <div className="text-slate-700 font-medium">FinScale Networks</div>
                <p className="text-slate-600 mt-1">
                  Architected infrastructure-as-code foundations in Terraform and Go for core payment transaction processing.
                </p>
              </div>
            </div>
          </div>

          {/* Skills Grid */}
          <div className="rounded-xl border border-slate-200/80 bg-white p-5 shadow-xs space-y-3">
            <h3 className="text-sm font-semibold text-slate-900 flex items-center gap-2">
              <Code2 className="size-4 text-slate-400" />
              <span>Verified Technical Skills</span>
            </h3>

            <div className="flex flex-wrap gap-1.5">
              {[
                "Kubernetes", "Docker", "Terraform", "Go", "Python",
                "AWS", "GCP", "FastAPI", "PostgreSQL", "Redis",
                "Kafka", "Prometheus", "Distributed Systems", "CI/CD",
              ].map((skill) => (
                <span
                  key={skill}
                  className="rounded-md border border-slate-200 bg-slate-50 px-2.5 py-1 text-xs font-medium text-slate-800"
                >
                  {skill}
                </span>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
