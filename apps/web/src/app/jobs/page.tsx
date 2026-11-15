"use client"

import * as React from "react"
import Link from "next/link"
import { Sparkles, MapPin, Building } from "lucide-react"
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

export default function JobsPage() {
  const [search, setSearch] = React.useState("")

  return (
    <div className="space-y-6">
      <PageHeader
        title="Job Discovery & Queue"
        description="Discovered jobs across supported boards with explainable matching scores and eligibility filters."
        breadcrumbs={[
          { label: "Overview", href: "/" },
          { label: "Job Queue" },
        ]}
        actions={
          <Button variant="default" size="sm" className="gap-1.5 bg-blue-600 hover:bg-blue-700">
            <Sparkles className="size-4" />
            <span>Discover New Jobs</span>
          </Button>
        }
      />

      {/* Filter and Search Bar */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between rounded-xl border border-slate-200/80 bg-white p-3.5 shadow-xs">
        <div className="w-full sm:max-w-sm">
          <SearchInput
            placeholder="Search job title, company, skills..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onClear={() => setSearch("")}
          />
        </div>

        <div className="flex items-center gap-2 overflow-x-auto">
          <select className="h-9 rounded-md border border-slate-200 bg-white px-2.5 text-xs text-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-600/20">
            <option value="">All Platforms</option>
            <option value="greenhouse">Greenhouse</option>
            <option value="lever">Lever</option>
            <option value="ashby">Ashby</option>
            <option value="naukri">Naukri</option>
            <option value="wellfound">Wellfound</option>
            <option value="linkedin">LinkedIn</option>
          </select>

          <select className="h-9 rounded-md border border-slate-200 bg-white px-2.5 text-xs text-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-600/20">
            <option value="">All Work Modes</option>
            <option value="remote">Remote</option>
            <option value="hybrid">Hybrid</option>
            <option value="onsite">On-Site</option>
          </select>

          <select className="h-9 rounded-md border border-slate-200 bg-white px-2.5 text-xs text-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-600/20">
            <option value="">Min Score: Any</option>
            <option value="75">75%+ (Strong Match)</option>
            <option value="65">65%+ (Eligible)</option>
            <option value="50">50%+ (Borderline)</option>
          </select>
        </div>
      </div>

      {/* Jobs Table */}
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Job Title & Company</TableHead>
            <TableHead>Location & Mode</TableHead>
            <TableHead>Platform</TableHead>
            <TableHead>Match Score</TableHead>
            <TableHead>Eligibility</TableHead>
            <TableHead className="text-right">Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {[
            {
              id: "job-001",
              title: "Senior Platform Infrastructure Engineer",
              company: "Stripe",
              location: "San Francisco, CA",
              workMode: "Remote",
              platform: "Greenhouse",
              score: 91,
              status: "ELIGIBLE",
              reason: "Strong Go, Kubernetes, Terraform overlap",
            },
            {
              id: "job-002",
              title: "Staff Distributed Systems Engineer",
              company: "Datadog",
              location: "New York, NY",
              workMode: "Hybrid",
              platform: "Lever",
              score: 84,
              status: "ELIGIBLE",
              reason: "Proven distributed database experience",
            },
            {
              id: "job-003",
              title: "Senior Backend Engineer (Python / FastAPI)",
              company: "Cloudflare",
              location: "Austin, TX",
              workMode: "Remote",
              platform: "Ashby",
              score: 78,
              status: "ELIGIBLE",
              reason: "High skill overlap on async Python & Redis",
            },
            {
              id: "job-004",
              title: "Lead Cloud Architect",
              company: "Legacy Retail Co",
              location: "Chicago, IL",
              workMode: "On-site",
              platform: "Naukri",
              score: 42,
              status: "EXCLUDED",
              reason: "Hard filter: on-site requirement conflicts with remote preference",
            },
          ].map((job) => (
            <TableRow key={job.id}>
              <TableCell>
                <Link
                  href={`/jobs/${job.id}`}
                  className="font-semibold text-slate-900 hover:text-blue-600 transition-colors"
                >
                  {job.title}
                </Link>
                <div className="text-xs text-slate-500 flex items-center gap-1.5 mt-0.5">
                  <Building className="size-3 text-slate-400" />
                  <span>{job.company}</span>
                </div>
              </TableCell>
              <TableCell>
                <div className="flex items-center gap-1 text-slate-700 text-xs">
                  <MapPin className="size-3 text-slate-400" />
                  <span>{job.location}</span>
                </div>
                <div className="text-[11px] text-slate-500 mt-0.5">
                  {job.workMode}
                </div>
              </TableCell>
              <TableCell>
                <Badge variant="secondary">{job.platform}</Badge>
              </TableCell>
              <TableCell>
                <div className="flex items-center gap-2">
                  <span
                    className={`font-bold text-sm ${
                      job.score >= 75
                        ? "text-emerald-600"
                        : job.score >= 60
                        ? "text-blue-600"
                        : "text-amber-600"
                    }`}
                  >
                    {job.score}%
                  </span>
                </div>
                <div className="text-[10px] text-slate-500 max-w-[200px] truncate">
                  {job.reason}
                </div>
              </TableCell>
              <TableCell>
                {job.status === "ELIGIBLE" ? (
                  <Badge variant="success">Eligible</Badge>
                ) : (
                  <Badge variant="destructive">Excluded</Badge>
                )}
              </TableCell>
              <TableCell className="text-right">
                <Link href={`/jobs/${job.id}`}>
                  <Button variant="outline" size="xs">
                    Inspect Match
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
