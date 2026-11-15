"use client"

import * as React from "react"
import Link from "next/link"
import {
  CheckCircle2,
  Eye,
  FileText,
  Filter,
} from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { PageHeader } from "@/components/ui/page-header"
import { SearchInput } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import { EmptyState } from "@/components/ui/empty-state"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { apiClient } from "@/lib/api-client"
import type { ApplicationItem } from "@/types/api"

const FALLBACK_APPLICATIONS: ApplicationItem[] = [
  {
    id: "app-001",
    job_id: "job-001",
    user_id: "usr-local-demo",
    platform: "Greenhouse",
    external_id: "gh-str-891024",
    profile_version: "2026.11.15-v1",
    resume_version: "resume_platform_v2.pdf",
    autonomy_level: "L0",
    status: "AWAITING_APPROVAL",
    created_at: "2026-11-15T09:24:00Z",
    updated_at: "2026-11-15T09:25:00Z",
  },
  {
    id: "app-002",
    job_id: "job-002",
    user_id: "usr-local-demo",
    platform: "Lever",
    external_id: "lev-dd-440192",
    profile_version: "2026.11.15-v1",
    resume_version: "resume_platform_v2.pdf",
    autonomy_level: "L0",
    status: "DRY_RUN_DONE",
    created_at: "2026-11-15T08:10:00Z",
    updated_at: "2026-11-15T08:12:30Z",
  },
  {
    id: "app-003",
    job_id: "job-003",
    user_id: "usr-local-demo",
    platform: "Ashby",
    external_id: "ash-fg-330182",
    profile_version: "2026.11.15-v1",
    resume_version: "resume_platform_v2.pdf",
    autonomy_level: "L0",
    status: "NEEDS_USER_INPUT",
    created_at: "2026-11-15T07:45:00Z",
    updated_at: "2026-11-15T07:46:12Z",
  },
  {
    id: "app-004",
    job_id: "job-004",
    user_id: "usr-local-demo",
    platform: "Naukri",
    external_id: "nk-rz-990142",
    profile_version: "2026.11.15-v1",
    resume_version: "resume_backend_v1.pdf",
    autonomy_level: "L0",
    status: "APPROVED",
    created_at: "2026-11-15T07:15:00Z",
    updated_at: "2026-11-15T07:20:00Z",
  },
  {
    id: "app-005",
    job_id: "job-005",
    user_id: "usr-local-demo",
    platform: "Wellfound",
    external_id: "wf-sc-551029",
    profile_version: "2026.11.15-v1",
    resume_version: "resume_platform_v2.pdf",
    autonomy_level: "L0",
    status: "AWAITING_APPROVAL",
    created_at: "2026-11-15T06:50:00Z",
    updated_at: "2026-11-15T06:55:00Z",
  },
  {
    id: "app-006",
    job_id: "job-006",
    user_id: "usr-local-demo",
    platform: "LinkedIn",
    external_id: "li-cb-102948",
    profile_version: "2026.11.15-v1",
    resume_version: "resume_backend_v1.pdf",
    autonomy_level: "L0",
    status: "REJECTED",
    created_at: "2026-11-14T19:00:00Z",
    updated_at: "2026-11-14T19:05:00Z",
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

export default function ApplicationsPage() {
  const [applications, setApplications] = React.useState<ApplicationItem[]>(FALLBACK_APPLICATIONS)
  const [isLoading, setIsLoading] = React.useState<boolean>(true)
  const [search, setSearch] = React.useState<string>("")
  const [statusFilter, setStatusFilter] = React.useState<string>("all")
  const [platformFilter, setPlatformFilter] = React.useState<string>("all")

  React.useEffect(() => {
    let ignore = false

    apiClient
      .getApplications({ limit: 100 })
      .then((res) => {
        if (!ignore && res?.items && res.items.length > 0) {
          setApplications(res.items)
        }
      })
      .catch(() => {
        if (!ignore) setApplications(FALLBACK_APPLICATIONS)
      })
      .finally(() => {
        if (!ignore) setIsLoading(false)
      })

    return () => {
      ignore = true
    }
  }, [])

  const filteredApps = React.useMemo(() => {
    return applications.filter((app) => {
      if (statusFilter !== "all" && app.status.toLowerCase() !== statusFilter.toLowerCase()) {
        return false
      }
      if (platformFilter !== "all" && app.platform.toLowerCase() !== platformFilter.toLowerCase()) {
        return false
      }
      if (search.trim()) {
        const q = search.toLowerCase()
        const matchExt = app.external_id.toLowerCase().includes(q)
        const matchPlat = app.platform.toLowerCase().includes(q)
        const matchId = app.id.toLowerCase().includes(q)
        if (!matchExt && !matchPlat && !matchId) {
          return false
        }
      }
      return true
    })
  }, [applications, search, statusFilter, platformFilter])

  const awaitingCount = applications.filter((a) => a.status === "AWAITING_APPROVAL").length
  const dryRunDoneCount = applications.filter((a) => a.status === "DRY_RUN_DONE").length
  const needsInputCount = applications.filter((a) => a.status === "NEEDS_USER_INPUT").length

  return (
    <div className="space-y-6">
      <PageHeader
        title="Application Workspace"
        description="Audited lifecycle execution records, dry-run evidence, and state machine transitions."
        breadcrumbs={[
          { label: "Overview", href: "/" },
          { label: "Applications" },
        ]}
        badge={
          <Badge variant="outline" className="gap-1 font-mono text-xs">
            <span>{applications.length} Applications Total</span>
          </Badge>
        }
        actions={
          <Link href="/approvals">
            <Button variant="default" size="sm" className="gap-1.5 bg-blue-600 hover:bg-blue-700">
              <CheckCircle2 className="size-4" />
              <span>Approval Queue ({awaitingCount})</span>
            </Button>
          </Link>
        }
      />

      {/* Summary KPI Cards */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <div className="rounded-xl border border-slate-200/80 bg-white p-3.5 shadow-xs">
          <p className="text-xs text-slate-500 font-medium">Total Tracked</p>
          <p className="text-xl font-bold text-slate-900 mt-0.5">{applications.length}</p>
        </div>
        <div className="rounded-xl border border-slate-200/80 bg-white p-3.5 shadow-xs">
          <p className="text-xs text-slate-500 font-medium">Awaiting Approval</p>
          <p className="text-xl font-bold text-amber-600 mt-0.5">{awaitingCount}</p>
        </div>
        <div className="rounded-xl border border-slate-200/80 bg-white p-3.5 shadow-xs">
          <p className="text-xs text-slate-500 font-medium">Dry-Runs Completed</p>
          <p className="text-xl font-bold text-emerald-600 mt-0.5">{dryRunDoneCount}</p>
        </div>
        <div className="rounded-xl border border-slate-200/80 bg-white p-3.5 shadow-xs">
          <p className="text-xs text-slate-500 font-medium">Needs User Input</p>
          <p className="text-xl font-bold text-indigo-600 mt-0.5">{needsInputCount}</p>
        </div>
      </div>

      {/* Search and Filters */}
      <div className="flex flex-col gap-3 rounded-xl border border-slate-200/80 bg-white p-4 shadow-xs">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="w-full sm:max-w-md">
            <SearchInput
              placeholder="Search by external ID, application ID, platform..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              onClear={() => setSearch("")}
            />
          </div>

          <div className="flex flex-wrap items-center gap-2">
            {/* Status Filter */}
            <select
              aria-label="Filter by Status"
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="h-9 rounded-md border border-slate-200 bg-white px-2.5 text-xs text-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-600/20"
            >
              <option value="all">All Statuses</option>
              <option value="AWAITING_APPROVAL">AWAITING_APPROVAL</option>
              <option value="APPROVED">APPROVED</option>
              <option value="DRY_RUN_DONE">DRY_RUN_DONE</option>
              <option value="NEEDS_USER_INPUT">NEEDS_USER_INPUT</option>
              <option value="MATCHED">MATCHED</option>
              <option value="ELIGIBLE">ELIGIBLE</option>
              <option value="REJECTED">REJECTED</option>
            </select>

            {/* Platform Filter */}
            <select
              aria-label="Filter by Platform"
              value={platformFilter}
              onChange={(e) => setPlatformFilter(e.target.value)}
              className="h-9 rounded-md border border-slate-200 bg-white px-2.5 text-xs text-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-600/20"
            >
              <option value="all">All Platforms</option>
              <option value="greenhouse">Greenhouse</option>
              <option value="lever">Lever</option>
              <option value="ashby">Ashby</option>
              <option value="naukri">Naukri</option>
              <option value="wellfound">Wellfound</option>
              <option value="linkedin">LinkedIn</option>
            </select>
          </div>
        </div>

        {/* Active Filters */}
        {(statusFilter !== "all" || platformFilter !== "all" || search) && (
          <div className="flex flex-wrap items-center gap-1.5 pt-2 border-t border-slate-100 text-xs">
            <span className="text-slate-500 text-[11px] font-medium flex items-center gap-1">
              <Filter className="size-3" /> Filters:
            </span>
            {statusFilter !== "all" && (
              <Badge variant="secondary" className="gap-1">
                <span>Status: {statusFilter}</span>
                <button
                  type="button"
                  onClick={() => setStatusFilter("all")}
                  className="hover:text-slate-900"
                >
                  ×
                </button>
              </Badge>
            )}
            {platformFilter !== "all" && (
              <Badge variant="secondary" className="gap-1">
                <span>Platform: {platformFilter}</span>
                <button
                  type="button"
                  onClick={() => setPlatformFilter("all")}
                  className="hover:text-slate-900"
                >
                  ×
                </button>
              </Badge>
            )}
            {search && (
              <Badge variant="secondary" className="gap-1">
                <span>Query: &quot;{search}&quot;</span>
                <button
                  type="button"
                  onClick={() => setSearch("")}
                  className="hover:text-slate-900"
                >
                  ×
                </button>
              </Badge>
            )}
            <button
              type="button"
              onClick={() => {
                setStatusFilter("all")
                setPlatformFilter("all")
                setSearch("")
              }}
              className="text-[11px] text-blue-600 hover:underline ml-1"
            >
              Reset
            </button>
          </div>
        )}
      </div>

      {/* Applications Table */}
      <div className="rounded-xl border border-slate-200/80 bg-white p-5 shadow-xs space-y-4">
        {isLoading ? (
          <div className="space-y-3 py-4">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="flex items-center justify-between py-2 border-b border-slate-100">
                <div className="space-y-1.5">
                  <Skeleton className="h-4 w-52" />
                  <Skeleton className="h-3 w-32" />
                </div>
                <Skeleton className="h-6 w-24 rounded-full" />
              </div>
            ))}
          </div>
        ) : filteredApps.length === 0 ? (
          <EmptyState
            icon={FileText}
            title="No applications found"
            description="No applications match the selected status or platform filters."
            action={
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  setStatusFilter("all")
                  setPlatformFilter("all")
                  setSearch("")
                }}
              >
                Reset Filters
              </Button>
            }
          />
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Application ID & External Reference</TableHead>
                <TableHead>Platform</TableHead>
                <TableHead>Autonomy</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Created</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredApps.map((app) => (
                <TableRow key={app.id}>
                  <TableCell>
                    <Link
                      href={`/applications/${app.id}`}
                      className="font-mono text-xs font-semibold text-slate-900 hover:text-blue-600 hover:underline"
                    >
                      {app.id}
                    </Link>
                    <div className="text-[11px] text-slate-500 font-mono mt-0.5">
                      {app.external_id}
                    </div>
                  </TableCell>

                  <TableCell>
                    <Badge variant="secondary" size="sm">
                      {app.platform}
                    </Badge>
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
                    <div className="flex items-center justify-end gap-1.5">
                      {app.status === "AWAITING_APPROVAL" ? (
                        <Link href="/approvals">
                          <Button variant="default" size="xs" className="bg-amber-600 hover:bg-amber-700 text-white gap-1">
                            <CheckCircle2 className="size-3" />
                            <span>Review</span>
                          </Button>
                        </Link>
                      ) : (
                        <Link href={`/applications/${app.id}`}>
                          <Button variant="outline" size="xs" className="gap-1">
                            <Eye className="size-3" />
                            <span>Inspect</span>
                          </Button>
                        </Link>
                      )}
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </div>
    </div>
  )
}
