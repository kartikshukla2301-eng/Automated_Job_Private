"use client"

import * as React from "react"
import Link from "next/link"
import {
  Briefcase,
  CheckCircle2,
  Send,
  ShieldCheck,
  TrendingUp,
} from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { PageHeader } from "@/components/ui/page-header"
import { StatCard } from "@/components/ui/stat-card"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"

export default function OverviewPage() {
  return (
    <div className="space-y-6">
      <PageHeader
        title="Agent Overview"
        description="Autonomous job discovery, intelligent scoring, and supervised dry-run execution."
        badge={
          <Badge variant="warning" className="gap-1 font-semibold">
            <span>L0 Dry-Run Guard Active</span>
          </Badge>
        }
        actions={
          <div className="flex items-center gap-2">
            <Link href="/approvals">
              <Button variant="default" size="sm" className="gap-1.5 bg-blue-600 hover:bg-blue-700">
                <CheckCircle2 className="size-4" />
                <span>Review Approvals</span>
              </Button>
            </Link>
          </div>
        }
      />

      {/* Primary KPI Metrics */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          title="Jobs Discovered"
          value="48"
          subtitle="Across 6 active providers"
          icon={Briefcase}
          trend={{ value: "+12 today", isPositive: true }}
        />
        <StatCard
          title="Matched & Eligible"
          value="18"
          subtitle="Matching score >= 65%"
          icon={TrendingUp}
          trend={{ value: "37.5% match rate", neutral: true }}
        />
        <StatCard
          title="Pending Approval"
          value="4"
          subtitle="Awaiting human confirmation"
          icon={CheckCircle2}
          badge="Action Needed"
        />
        <StatCard
          title="Dry-Runs Completed"
          value="14"
          subtitle="L0 safe DOM inspections"
          icon={Send}
          trend={{ value: "0 live submissions", neutral: true }}
        />
      </div>

      {/* Grid: Recent Applications & System Health */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Left 2 Cols: Recent Applications Queue */}
        <div className="rounded-xl border border-slate-200/80 bg-white p-5 shadow-xs lg:col-span-2 space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-base font-semibold text-slate-900">
                Recent Applications
              </h2>
              <p className="text-xs text-slate-500">
                State machine transitions and verification audit trail.
              </p>
            </div>
            <Link href="/applications">
              <Button variant="outline" size="xs">
                View All
              </Button>
            </Link>
          </div>

          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Role & Company</TableHead>
                <TableHead>Platform</TableHead>
                <TableHead>Match</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="text-right">Action</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              <TableRow>
                <TableCell>
                  <div className="font-medium text-slate-900">
                    Senior Platform Engineer
                  </div>
                  <div className="text-xs text-slate-500">Stripe</div>
                </TableCell>
                <TableCell>
                  <Badge variant="secondary">Greenhouse</Badge>
                </TableCell>
                <TableCell>
                  <span className="font-semibold text-emerald-600">88%</span>
                </TableCell>
                <TableCell>
                  <Badge variant="warning">AWAITING_APPROVAL</Badge>
                </TableCell>
                <TableCell className="text-right">
                  <Link href="/approvals">
                    <Button variant="outline" size="xs">
                      Review
                    </Button>
                  </Link>
                </TableCell>
              </TableRow>

              <TableRow>
                <TableCell>
                  <div className="font-medium text-slate-900">
                    Staff Backend Architect
                  </div>
                  <div className="text-xs text-slate-500">Datadog</div>
                </TableCell>
                <TableCell>
                  <Badge variant="secondary">Lever</Badge>
                </TableCell>
                <TableCell>
                  <span className="font-semibold text-emerald-600">82%</span>
                </TableCell>
                <TableCell>
                  <Badge variant="success">DRY_RUN_DONE</Badge>
                </TableCell>
                <TableCell className="text-right">
                  <Link href="/applications">
                    <Button variant="ghost" size="xs">
                      Inspect
                    </Button>
                  </Link>
                </TableCell>
              </TableRow>

              <TableRow>
                <TableCell>
                  <div className="font-medium text-slate-900">
                    Distributed Systems Engineer
                  </div>
                  <div className="text-xs text-slate-500">Cloudflare</div>
                </TableCell>
                <TableCell>
                  <Badge variant="secondary">Ashby</Badge>
                </TableCell>
                <TableCell>
                  <span className="font-semibold text-emerald-600">76%</span>
                </TableCell>
                <TableCell>
                  <Badge variant="indigo">NEEDS_USER_INPUT</Badge>
                </TableCell>
                <TableCell className="text-right">
                  <Link href="/applications">
                    <Button variant="outline" size="xs">
                      Provide Answer
                    </Button>
                  </Link>
                </TableCell>
              </TableRow>
            </TableBody>
          </Table>
        </div>

        {/* Right Col: System Safety & Provider Health */}
        <div className="space-y-6">
          {/* Safety Status Card */}
          <div className="rounded-xl border border-slate-200/80 bg-white p-5 shadow-xs space-y-3">
            <h3 className="text-sm font-semibold text-slate-900">
              Safety & Autonomous Bounds
            </h3>

            <div className="space-y-2 text-xs">
              <div className="flex items-center justify-between py-1 border-b border-slate-100">
                <span className="text-slate-500">Real-Submit Gate</span>
                <Badge variant="destructive" size="sm">
                  DISABLED
                </Badge>
              </div>

              <div className="flex items-center justify-between py-1 border-b border-slate-100">
                <span className="text-slate-500">Kill Switch Status</span>
                <span className="font-medium text-emerald-600 flex items-center gap-1">
                  <ShieldCheck className="size-3.5" /> Normal
                </span>
              </div>

              <div className="flex items-center justify-between py-1 border-b border-slate-100">
                <span className="text-slate-500">Active Daily Cap</span>
                <span className="font-semibold text-slate-900">2 / 2 apps</span>
              </div>

              <div className="flex items-center justify-between py-1">
                <span className="text-slate-500">Active IST Window</span>
                <span className="font-medium text-slate-700">09:00 – 23:00 IST</span>
              </div>
            </div>

            <Link href="/automation" className="block pt-1">
              <Button variant="outline" size="sm" className="w-full text-xs">
                Open Safety Center
              </Button>
            </Link>
          </div>

          {/* Provider Status Card */}
          <div className="rounded-xl border border-slate-200/80 bg-white p-5 shadow-xs space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold text-slate-900">
                Provider Adapters (6)
              </h3>
              <Link href="/providers">
                <span className="text-xs text-blue-600 hover:underline">
                  Manage
                </span>
              </Link>
            </div>

            <div className="space-y-2 text-xs">
              {[
                { name: "Greenhouse", status: "HEALTHY", variant: "success" as const },
                { name: "Lever", status: "HEALTHY", variant: "success" as const },
                { name: "Ashby", status: "HEALTHY", variant: "success" as const },
                { name: "Naukri", status: "HEALTHY", variant: "success" as const },
                { name: "Wellfound", status: "HEALTHY", variant: "success" as const },
                { name: "LinkedIn", status: "RESTRICTED (L1)", variant: "warning" as const },
              ].map((p) => (
                <div
                  key={p.name}
                  className="flex items-center justify-between py-1 border-b border-slate-50 last:border-0"
                >
                  <span className="font-medium text-slate-700">{p.name}</span>
                  <Badge variant={p.variant} size="sm">
                    {p.status}
                  </Badge>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
