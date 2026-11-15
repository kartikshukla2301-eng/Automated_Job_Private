"use client"

import * as React from "react"
import Link from "next/link"
import {
  Briefcase,
  CheckCircle2,
  RefreshCw,
  Send,
  ShieldAlert,
  ShieldCheck,
  TrendingUp,
  Wifi,
  WifiOff,
} from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { PageHeader } from "@/components/ui/page-header"
import { StatCard } from "@/components/ui/stat-card"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { apiClient } from "@/lib/api-client"
import type { ApplicationItem, DashboardOverview } from "@/types/api"

const FALLBACK_OVERVIEW: DashboardOverview = {
  user_id: "usr-local-demo",
  generated_at: new Date().toISOString(),
  jobs_discovered: 48,
  jobs_matched: 24,
  eligible_jobs: 18,
  applications_awaiting_approval: 2,
  applications_needing_input: 1,
  dry_runs_completed: 14,
  rejected_jobs: 6,
  skipped_applications: 0,
  failed_runs: 0,
  kill_switch_active: false,
  real_submit_gate_locked: true,
  provider_health: {
    greenhouse: "HEALTHY",
    lever: "HEALTHY",
    ashby: "HEALTHY",
    naukri: "HEALTHY",
    wellfound: "HEALTHY",
    linkedin: "RESTRICTED",
  },
}

const FALLBACK_RECENT_APPS: ApplicationItem[] = [
  {
    id: "app-001",
    job_id: "job-str-891024",
    user_id: "usr-local-demo",
    platform: "Greenhouse",
    external_id: "gh-str-891024",
    profile_version: "2026.11.15-v1",
    autonomy_level: "L0",
    status: "AWAITING_APPROVAL",
    created_at: "2026-11-15T09:24:00Z",
    updated_at: "2026-11-15T09:25:00Z",
  },
  {
    id: "app-002",
    job_id: "job-dd-440192",
    user_id: "usr-local-demo",
    platform: "Lever",
    external_id: "lev-dd-440192",
    profile_version: "2026.11.15-v1",
    autonomy_level: "L0",
    status: "DRY_RUN_DONE",
    created_at: "2026-11-15T08:10:00Z",
    updated_at: "2026-11-15T08:12:30Z",
  },
  {
    id: "app-003",
    job_id: "job-cf-330182",
    user_id: "usr-local-demo",
    platform: "Ashby",
    external_id: "ash-cf-330182",
    profile_version: "2026.11.15-v1",
    autonomy_level: "L0",
    status: "NEEDS_USER_INPUT",
    created_at: "2026-11-15T07:45:00Z",
    updated_at: "2026-11-15T07:46:12Z",
  },
  {
    id: "app-004",
    job_id: "job-fg-119203",
    user_id: "usr-local-demo",
    platform: "Lever",
    external_id: "lev-fg-119203",
    profile_version: "2026.11.15-v1",
    autonomy_level: "L0",
    status: "APPROVED",
    created_at: "2026-11-15T07:15:00Z",
    updated_at: "2026-11-15T07:20:00Z",
  },
]

function getStatusBadgeVariant(status: string) {
  switch (status) {
    case "DRY_RUN_DONE":
    case "APPROVED":
    case "ELIGIBLE":
      return "success" as const
    case "AWAITING_APPROVAL":
    case "PENDING":
      return "warning" as const
    case "NEEDS_USER_INPUT":
      return "indigo" as const
    case "REJECTED":
    case "FAILED":
      return "destructive" as const
    default:
      return "secondary" as const
  }
}

export default function OverviewPage() {
  const [overview, setOverview] = React.useState<DashboardOverview>(FALLBACK_OVERVIEW)
  const [recentApps, setRecentApps] = React.useState<ApplicationItem[]>(FALLBACK_RECENT_APPS)
  const [isLoading, setIsLoading] = React.useState<boolean>(true)
  const [isDemoMode, setIsDemoMode] = React.useState<boolean>(false)
  const [isRefreshing, setIsRefreshing] = React.useState<boolean>(false)

  const handleRefresh = React.useCallback(async () => {
    setIsRefreshing(true)
    try {
      const [overviewRes, appsRes] = await Promise.all([
        apiClient.getOverview(),
        apiClient.getApplications({ limit: 5 }).catch(() => null),
      ])

      setOverview(overviewRes)
      if (appsRes?.items && appsRes.items.length > 0) {
        setRecentApps(appsRes.items)
      }
      setIsDemoMode(false)
    } catch {
      setIsDemoMode(true)
      setOverview(FALLBACK_OVERVIEW)
      setRecentApps(FALLBACK_RECENT_APPS)
    } finally {
      setIsRefreshing(false)
    }
  }, [])

  React.useEffect(() => {
    let ignore = false

    apiClient
      .getOverview()
      .then(async (overviewRes) => {
        if (ignore) return
        setOverview(overviewRes)
        setIsDemoMode(false)

        try {
          const appsRes = await apiClient.getApplications({ limit: 5 })
          if (!ignore && appsRes?.items && appsRes.items.length > 0) {
            setRecentApps(appsRes.items)
          }
        } catch {
          // ignore auxiliary error
        }
      })
      .catch(() => {
        if (ignore) return
        setIsDemoMode(true)
        setOverview(FALLBACK_OVERVIEW)
        setRecentApps(FALLBACK_RECENT_APPS)
      })
      .finally(() => {
        if (!ignore) {
          setIsLoading(false)
        }
      })

    return () => {
      ignore = true
    }
  }, [])

  return (
    <div className="space-y-6">
      {/* Offline / Live Connectivity Banner */}
      {isDemoMode && (
        <div
          role="alert"
          className="flex items-center justify-between rounded-xl border border-amber-200 bg-amber-50/80 px-4 py-3 text-xs text-amber-900 shadow-xs"
        >
          <div className="flex items-center gap-2.5">
            <WifiOff className="size-4 shrink-0 text-amber-700" />
            <div>
              <span className="font-semibold">Offline Demo Mode:</span> Backend at{" "}
              <code className="rounded bg-amber-100 px-1 py-0.5 font-mono text-[11px]">
                http://127.0.0.1:8000
              </code>{" "}
              is unreachable. Displaying cached operational snapshot.
            </div>
          </div>
          <Button
            variant="outline"
            size="xs"
            onClick={handleRefresh}
            disabled={isRefreshing}
            className="border-amber-300 bg-white hover:bg-amber-100 text-amber-900 gap-1.5"
          >
            <RefreshCw className={`size-3.5 ${isRefreshing ? "animate-spin" : ""}`} />
            <span>{isRefreshing ? "Connecting..." : "Retry Connection"}</span>
          </Button>
        </div>
      )}

      {!isDemoMode && !isLoading && (
        <div className="flex items-center justify-between rounded-xl border border-emerald-200 bg-emerald-50/60 px-4 py-2.5 text-xs text-emerald-900 shadow-xs">
          <div className="flex items-center gap-2">
            <Wifi className="size-4 shrink-0 text-emerald-600" />
            <span className="font-medium">
              Connected to live FastAPI backend at{" "}
              <code className="rounded bg-emerald-100 px-1 py-0.5 font-mono text-[11px]">
                127.0.0.1:8000
              </code>
            </span>
          </div>
          <Button
            variant="ghost"
            size="xs"
            onClick={handleRefresh}
            disabled={isRefreshing}
            className="text-emerald-700 hover:bg-emerald-100 gap-1"
          >
            <RefreshCw className={`size-3.5 ${isRefreshing ? "animate-spin" : ""}`} />
            <span>Sync</span>
          </Button>
        </div>
      )}

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
                <span>Review Approvals ({overview.applications_awaiting_approval})</span>
              </Button>
            </Link>
          </div>
        }
      />

      {/* Primary KPI Metrics */}
      {isLoading ? (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="rounded-xl border border-slate-200/80 bg-white p-5 shadow-xs space-y-3">
              <Skeleton className="h-4 w-28" />
              <Skeleton className="h-8 w-16" />
              <Skeleton className="h-3 w-36" />
            </div>
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard
            title="Jobs Discovered"
            value={overview.jobs_discovered}
            subtitle="Across 6 configured providers"
            icon={Briefcase}
            trend={{ value: `${overview.jobs_matched} scored`, isPositive: true }}
          />
          <StatCard
            title="Matched & Eligible"
            value={overview.eligible_jobs}
            subtitle="Deterministic score >= 65%"
            icon={TrendingUp}
            trend={{
              value: overview.jobs_discovered > 0
                ? `${Math.round((overview.eligible_jobs / overview.jobs_discovered) * 100)}% eligible`
                : "0%",
              neutral: true,
            }}
          />
          <StatCard
            title="Pending Approval"
            value={overview.applications_awaiting_approval}
            subtitle="Awaiting human confirmation"
            icon={CheckCircle2}
            badge={overview.applications_awaiting_approval > 0 ? "Action Needed" : undefined}
          />
          <StatCard
            title="Dry-Runs Completed"
            value={overview.dry_runs_completed}
            subtitle="L0 safe form inspections"
            icon={Send}
            trend={{ value: "0 live submissions", neutral: true }}
          />
        </div>
      )}

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

          {isLoading ? (
            <div className="space-y-3 py-2">
              {[1, 2, 3].map((i) => (
                <div key={i} className="flex items-center justify-between py-2 border-b border-slate-100">
                  <div className="space-y-1.5">
                    <Skeleton className="h-4 w-48" />
                    <Skeleton className="h-3 w-24" />
                  </div>
                  <Skeleton className="h-6 w-20 rounded-full" />
                </div>
              ))}
            </div>
          ) : recentApps.length === 0 ? (
            <div className="py-8 text-center text-xs text-slate-500">
              No recent applications recorded.
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>External ID & Platform</TableHead>
                  <TableHead>Autonomy</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Created</TableHead>
                  <TableHead className="text-right">Action</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {recentApps.map((app) => (
                  <TableRow key={app.id}>
                    <TableCell>
                      <div className="font-mono text-xs font-medium text-slate-900">
                        {app.external_id}
                      </div>
                      <div className="text-[11px] text-slate-500">{app.platform}</div>
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline" size="sm" className="font-mono">
                        {app.autonomy_level}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <Badge variant={getStatusBadgeVariant(app.status)}>
                        {app.status}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-xs text-slate-500">
                      {new Date(app.created_at).toLocaleDateString(undefined, {
                        month: "short",
                        day: "numeric",
                        hour: "2-digit",
                        minute: "2-digit",
                      })}
                    </TableCell>
                    <TableCell className="text-right">
                      {app.status === "AWAITING_APPROVAL" ? (
                        <Link href="/approvals">
                          <Button variant="outline" size="xs">
                            Review
                          </Button>
                        </Link>
                      ) : (
                        <Link href={`/applications/${app.id}`}>
                          <Button variant="ghost" size="xs">
                            Inspect
                          </Button>
                        </Link>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
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
                <Badge variant="destructive" size="sm" className="font-mono">
                  {overview.real_submit_gate_locked ? "LOCKED DISABLED" : "ACTIVE"}
                </Badge>
              </div>

              <div className="flex items-center justify-between py-1 border-b border-slate-100">
                <span className="text-slate-500">Kill Switch Status</span>
                {overview.kill_switch_active ? (
                  <Badge variant="destructive" size="sm" className="gap-1">
                    <ShieldAlert className="size-3" />
                    <span>TRIPPED</span>
                  </Badge>
                ) : (
                  <span className="font-medium text-emerald-600 flex items-center gap-1">
                    <ShieldCheck className="size-3.5" /> Normal
                  </span>
                )}
              </div>

              <div className="flex items-center justify-between py-1 border-b border-slate-100">
                <span className="text-slate-500">Active Daily Cap</span>
                <span className="font-semibold text-slate-900">2 / 2 apps (Locked S0)</span>
              </div>

              <div className="flex items-center justify-between py-1 border-b border-slate-100">
                <span className="text-slate-500">Active IST Window</span>
                <span className="font-medium text-slate-700">09:00 – 23:00 IST</span>
              </div>

              <div className="flex items-center justify-between py-1">
                <span className="text-slate-500">Action Needed</span>
                <span className="font-medium text-amber-700">
                  {overview.applications_awaiting_approval + overview.applications_needing_input} items
                </span>
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
                Provider Adapters ({Object.keys(overview.provider_health || {}).length || 6})
              </h3>
              <Link href="/providers">
                <span className="text-xs text-blue-600 hover:underline">
                  Manage
                </span>
              </Link>
            </div>

            <div className="space-y-2 text-xs">
              {[
                { key: "greenhouse", name: "Greenhouse", note: "Direct Board" },
                { key: "lever", name: "Lever", note: "Direct Postings" },
                { key: "ashby", name: "Ashby", note: "Direct Board" },
                { key: "naukri", name: "Naukri", note: "Session Required" },
                { key: "wellfound", name: "Wellfound", note: "Session Required" },
                { key: "linkedin", name: "LinkedIn", note: "Restricted (L1 Max)" },
              ].map((p) => {
                const health = overview.provider_health?.[p.key] || "HEALTHY"
                const isRestricted = p.key === "linkedin" || health === "RESTRICTED"
                const variant = isRestricted ? "warning" : health === "DEGRADED" ? "warning" : "success"

                return (
                  <div
                    key={p.key}
                    className="flex items-center justify-between py-1 border-b border-slate-50 last:border-0"
                  >
                    <div>
                      <span className="font-medium text-slate-800">{p.name}</span>
                      <span className="text-[10px] text-slate-400 ml-1.5">{p.note}</span>
                    </div>
                    <Badge variant={variant} size="sm">
                      {health}
                    </Badge>
                  </div>
                )
              })}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
