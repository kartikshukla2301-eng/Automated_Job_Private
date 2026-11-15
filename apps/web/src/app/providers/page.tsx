"use client"

import * as React from "react"
import { RefreshCw, Play } from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { PageHeader } from "@/components/ui/page-header"

export default function ProvidersPage() {
  return (
    <div className="space-y-6">
      <PageHeader
        title="Provider Adapters & Status"
        description="Supported job boards and ATS platforms with health monitoring, autonomy limits, and canary tests."
        breadcrumbs={[
          { label: "Overview", href: "/" },
          { label: "Providers" },
        ]}
        actions={
          <Button variant="outline" size="sm" className="gap-1.5">
            <RefreshCw className="size-4" />
            <span>Run All Canaries</span>
          </Button>
        }
      />

      <div className="grid grid-cols-1 gap-5 md:grid-cols-2 lg:grid-cols-3">
        {[
          {
            name: "Greenhouse",
            type: "ATS",
            status: "HEALTHY",
            autonomy: "L0 (Dry-Run)",
            risk: "Low",
            authModel: "Public Boards API",
            consecutiveFails: 0,
            lastInspection: "10 mins ago",
          },
          {
            name: "Lever",
            type: "ATS",
            status: "HEALTHY",
            autonomy: "L0 (Dry-Run)",
            risk: "Low",
            authModel: "Public Postings API",
            consecutiveFails: 0,
            lastInspection: "25 mins ago",
          },
          {
            name: "Ashby",
            type: "ATS",
            status: "HEALTHY",
            autonomy: "L0 (Dry-Run)",
            risk: "Low",
            authModel: "Public Boards API",
            consecutiveFails: 0,
            lastInspection: "1 hour ago",
          },
          {
            name: "Naukri",
            type: "Job Board",
            status: "HEALTHY",
            autonomy: "L0 (Dry-Run)",
            risk: "Medium",
            authModel: "Manual Session Cookies",
            consecutiveFails: 0,
            lastInspection: "3 hours ago",
          },
          {
            name: "Wellfound",
            type: "Startup Board",
            status: "HEALTHY",
            autonomy: "L0 (Dry-Run)",
            risk: "Medium",
            authModel: "Manual Session Cookies",
            consecutiveFails: 0,
            lastInspection: "5 hours ago",
          },
          {
            name: "LinkedIn",
            type: "Social Network",
            status: "RESTRICTED (L1)",
            autonomy: "L1 Capped",
            risk: "High (Restricted)",
            authModel: "Manual Session Cookies",
            consecutiveFails: 0,
            lastInspection: "Yesterday",
          },
        ].map((p) => (
          <div
            key={p.name}
            className="rounded-xl border border-slate-200/80 bg-white p-5 shadow-xs space-y-4"
          >
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-base font-semibold text-slate-900">
                  {p.name}
                </h3>
                <span className="text-xs text-slate-500">{p.type}</span>
              </div>
              <Badge
                variant={
                  p.status === "HEALTHY"
                    ? "success"
                    : "warning"
                }
              >
                {p.status}
              </Badge>
            </div>

            <div className="space-y-1.5 text-xs text-slate-600 border-t border-slate-100 pt-3">
              <div className="flex justify-between">
                <span className="text-slate-400">Autonomy Ceiling:</span>
                <span className="font-semibold text-slate-800">{p.autonomy}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Authentication:</span>
                <span className="text-slate-700">{p.authModel}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Risk Tier:</span>
                <span className="text-slate-700">{p.risk}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Last Inspection:</span>
                <span className="text-slate-700">{p.lastInspection}</span>
              </div>
            </div>

            <div className="flex items-center gap-2 pt-2 border-t border-slate-100">
              <Button variant="outline" size="xs" className="w-full gap-1">
                <Play className="size-3" />
                <span>Run Canary</span>
              </Button>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
