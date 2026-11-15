"use client"

import * as React from "react"
import { CheckCircle2, ShieldCheck, Target, Award } from "lucide-react"
import { PageHeader } from "@/components/ui/page-header"
import { StatCard } from "@/components/ui/stat-card"
import { ChartContainer } from "@/components/ui/chart-container"

export default function AnalyticsPage() {
  return (
    <div className="space-y-6">
      <PageHeader
        title="Analytics & Application History"
        description="Transparent funnel analytics, matching calibration metrics, and answer bank effectiveness."
        breadcrumbs={[
          { label: "Overview", href: "/" },
          { label: "Analytics" },
        ]}
      />

      {/* KPI Cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          title="Reviewed Form Accuracy"
          value="100%"
          subtitle="0 wrong sensitive answers"
          icon={Award}
          trend={{ value: "Exceeds 98% target", isPositive: true }}
        />
        <StatCard
          title="Matching Precision"
          value="91.2%"
          subtitle="50 benchmark samples"
          icon={Target}
          trend={{ value: "FPR < 5%", isPositive: true }}
        />
        <StatCard
          title="Answer Bank Exact Match"
          value="84.6%"
          subtitle="Deterministic resolution"
          icon={CheckCircle2}
        />
        <StatCard
          title="Live Submissions"
          value="0"
          subtitle="Strict L0 compliance"
          icon={ShieldCheck}
          badge="Guarded"
        />
      </div>

      <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
        {/* Funnel Distribution Container */}
        <ChartContainer
          title="Application Lifecycle Funnel"
          description="Audited state distribution across discovered records."
          height={260}
        >
          <div className="h-full flex flex-col justify-around py-2">
            {[
              { stage: "Discovered", count: 48, pct: 100, color: "bg-blue-600" },
              { stage: "Matched & Eligible", count: 18, pct: 37.5, color: "bg-indigo-600" },
              { stage: "Awaiting Approval", count: 4, pct: 8.3, color: "bg-amber-500" },
              { stage: "Dry-Run Done (L0)", count: 14, pct: 29.2, color: "bg-emerald-600" },
              { stage: "Live Submissions", count: 0, pct: 0, color: "bg-slate-300" },
            ].map((s) => (
              <div key={s.stage} className="space-y-1">
                <div className="flex justify-between text-xs text-slate-700 font-medium">
                  <span>{s.stage}</span>
                  <span className="font-semibold text-slate-900">{s.count} ({s.pct}%)</span>
                </div>
                <div className="h-2 w-full rounded-full bg-slate-100 overflow-hidden">
                  <div
                    className={`h-full rounded-full ${s.color}`}
                    style={{ width: `${Math.max(s.pct, s.count > 0 ? 4 : 0)}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </ChartContainer>

        {/* Answer Bank Quality Breakdown */}
        <ChartContainer
          title="Answer Bank Resolution Quality"
          description="Resolution methods and human-review compliance."
          height={260}
        >
          <div className="h-full flex flex-col justify-around py-2 text-xs">
            <div className="flex justify-between items-center py-2 border-b border-slate-100">
              <span className="text-slate-600 font-medium">Exact Key Matches</span>
              <span className="font-bold text-emerald-600">84.6%</span>
            </div>
            <div className="flex justify-between items-center py-2 border-b border-slate-100">
              <span className="text-slate-600 font-medium">Normalized Alias Matches</span>
              <span className="font-bold text-blue-600">11.4%</span>
            </div>
            <div className="flex justify-between items-center py-2 border-b border-slate-100">
              <span className="text-slate-600 font-medium">Semantic / LLM Suggestions</span>
              <span className="font-bold text-amber-600">4.0% (Review Mandatory)</span>
            </div>
            <div className="flex justify-between items-center py-2 border-b border-slate-100">
              <span className="text-slate-600 font-medium">Sensitive Golden Questions</span>
              <span className="font-bold text-emerald-600">20 / 20 Fail-Closed (100%)</span>
            </div>
            <div className="flex justify-between items-center py-2">
              <span className="text-slate-600 font-medium">Unauthorized LLM Auto-Promotions</span>
              <span className="font-bold text-slate-900">0 (Strictly Blocked)</span>
            </div>
          </div>
        </ChartContainer>
      </div>
    </div>
  )
}
