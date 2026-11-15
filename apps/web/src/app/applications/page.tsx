"use client"

import * as React from "react"
import Link from "next/link"
import { Eye } from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { PageHeader } from "@/components/ui/page-header"
import { SearchInput } from "@/components/ui/input"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"

export default function ApplicationsPage() {
  const [search, setSearch] = React.useState("")
  const [statusFilter, setStatusFilter] = React.useState("")

  return (
    <div className="space-y-6">
      <PageHeader
        title="Application Workspace"
        description="Audited lifecycle state machine and dry-run execution records."
        breadcrumbs={[
          { label: "Overview", href: "/" },
          { label: "Applications" },
        ]}
      />

      {/* Filter and Search Bar */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between rounded-xl border border-slate-200/80 bg-white p-3.5 shadow-xs">
        <div className="w-full sm:max-w-sm">
          <SearchInput
            placeholder="Search company, job title, ID..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onClear={() => setSearch("")}
          />
        </div>

        <div className="flex items-center gap-2 overflow-x-auto">
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="h-9 rounded-md border border-slate-200 bg-white px-2.5 text-xs text-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-600/20"
          >
            <option value="">All Statuses</option>
            <option value="AWAITING_APPROVAL">AWAITING_APPROVAL</option>
            <option value="DRY_RUN_DONE">DRY_RUN_DONE</option>
            <option value="NEEDS_USER_INPUT">NEEDS_USER_INPUT</option>
            <option value="MATCHED">MATCHED</option>
            <option value="ELIGIBLE">ELIGIBLE</option>
            <option value="REJECTED">REJECTED</option>
          </select>
        </div>
      </div>

      {/* Applications Table */}
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Role & Company</TableHead>
            <TableHead>Platform</TableHead>
            <TableHead>Autonomy</TableHead>
            <TableHead>Lifecycle Status</TableHead>
            <TableHead>Last Updated</TableHead>
            <TableHead className="text-right">Action</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {[
            {
              id: "app-001",
              title: "Senior Platform Infrastructure Engineer",
              company: "Stripe",
              platform: "Greenhouse",
              autonomy: "L0",
              status: "AWAITING_APPROVAL",
              statusVariant: "warning" as const,
              updatedAt: "10 mins ago",
            },
            {
              id: "app-002",
              title: "Staff Distributed Systems Engineer",
              company: "Datadog",
              platform: "Lever",
              autonomy: "L0",
              status: "DRY_RUN_DONE",
              statusVariant: "success" as const,
              updatedAt: "2 hours ago",
            },
            {
              id: "app-003",
              title: "Senior Backend Engineer",
              company: "Cloudflare",
              platform: "Ashby",
              autonomy: "L0",
              status: "NEEDS_USER_INPUT",
              statusVariant: "indigo" as const,
              updatedAt: "4 hours ago",
            },
            {
              id: "app-004",
              title: "Lead Cloud Architect",
              company: "Legacy Retail Co",
              platform: "Naukri",
              autonomy: "L0",
              status: "REJECTED",
              statusVariant: "destructive" as const,
              updatedAt: "1 day ago",
            },
          ].map((app) => (
            <TableRow key={app.id}>
              <TableCell>
                <Link
                  href={`/applications/${app.id}`}
                  className="font-semibold text-slate-900 hover:text-blue-600 transition-colors"
                >
                  {app.title}
                </Link>
                <div className="text-xs text-slate-500">{app.company}</div>
              </TableCell>
              <TableCell>
                <Badge variant="secondary">{app.platform}</Badge>
              </TableCell>
              <TableCell>
                <span className="font-mono text-xs font-semibold text-slate-700">
                  {app.autonomy}
                </span>
              </TableCell>
              <TableCell>
                <Badge variant={app.statusVariant}>{app.status}</Badge>
              </TableCell>
              <TableCell className="text-xs text-slate-500">
                {app.updatedAt}
              </TableCell>
              <TableCell className="text-right">
                <Link href={`/applications/${app.id}`}>
                  <Button variant="outline" size="xs" className="gap-1">
                    <Eye className="size-3.5" />
                    <span>View Detail</span>
                  </Button>
                </Link>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}
