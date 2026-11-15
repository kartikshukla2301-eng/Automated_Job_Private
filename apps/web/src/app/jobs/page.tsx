"use client"

import * as React from "react"
import Link from "next/link"
import {
  ArrowUpDown,
  Building,
  CheckCircle2,
  ExternalLink,
  Eye,
  Filter,
  MapPin,
  Sparkles,
  XCircle,
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
import type { JobItem } from "@/types/api"

const FALLBACK_JOBS: JobItem[] = [
  {
    id: "job-001",
    title: "Senior Platform Infrastructure Engineer",
    company: "Stripe",
    location: "San Francisco, CA (Hybrid / Remote)",
    work_mode: "Hybrid",
    platform: "Greenhouse",
    external_id: "gh-str-891024",
    canonical_url: "https://boards.greenhouse.io/stripe/jobs/891024",
    employment_type: "Full-Time (W2)",
    salary_range: "$185,000 - $225,000",
    match_score: 91,
    hard_gates_passed: true,
    discovered_at: "2026-11-15T09:24:00Z",
    description: "Design and scale multi-cloud Kubernetes orchestration platforms and high-throughput microservices.",
    required_skills: ["Kubernetes", "Terraform", "Go", "Docker", "AWS"],
  },
  {
    id: "job-002",
    title: "Staff Distributed Systems Engineer",
    company: "Datadog",
    location: "New York, NY (Remote)",
    work_mode: "Remote",
    platform: "Lever",
    external_id: "lev-dd-440192",
    canonical_url: "https://jobs.lever.co/datadog/440192",
    employment_type: "Full-Time (W2)",
    salary_range: "$210,000 - $250,000",
    match_score: 87,
    hard_gates_passed: true,
    discovered_at: "2026-11-15T08:15:00Z",
    description: "Build ultra-low-latency real-time telemetry pipelines processing billions of metrics per second.",
    required_skills: ["Go", "Distributed Systems", "Kafka", "PostgreSQL", "Linux"],
  },
  {
    id: "job-003",
    title: "Principal Site Reliability Engineer",
    company: "Figma",
    location: "San Francisco, CA (Remote)",
    work_mode: "Remote",
    platform: "Ashby",
    external_id: "ash-fg-330182",
    canonical_url: "https://jobs.ashbyhq.com/figma/330182",
    employment_type: "Full-Time (W2)",
    salary_range: "$220,000 - $265,000",
    match_score: 84,
    hard_gates_passed: true,
    discovered_at: "2026-11-15T07:45:00Z",
    description: "Lead platform resilience, incident response automation, and multi-region compute infrastructure.",
    required_skills: ["Kubernetes", "AWS", "Observability", "Python", "CI/CD"],
  },
  {
    id: "job-004",
    title: "Lead Backend Infrastructure Engineer",
    company: "Razorpay",
    location: "Bengaluru, India (Hybrid)",
    work_mode: "Hybrid",
    platform: "Naukri",
    external_id: "nk-rz-990142",
    canonical_url: "https://www.naukri.com/job-listings-990142",
    employment_type: "Full-Time (Permanent)",
    salary_range: "₹45,00,000 - ₹65,00,000",
    match_score: 79,
    hard_gates_passed: true,
    discovered_at: "2026-11-15T06:30:00Z",
    description: "Architect high-availability banking gateways, financial ledger engines, and fraud prevention microservices.",
    required_skills: ["Java", "Distributed Transactions", "PostgreSQL", "Kafka", "Redis"],
  },
  {
    id: "job-005",
    title: "Founding Infrastructure Engineer",
    company: "Scale AI",
    location: "San Francisco, CA (On-site)",
    work_mode: "On-site",
    platform: "Wellfound",
    external_id: "wf-sc-551029",
    canonical_url: "https://wellfound.com/jobs/551029",
    employment_type: "Full-Time (W2)",
    salary_range: "$190,000 - $240,000 + 0.25% Equity",
    match_score: 74,
    hard_gates_passed: true,
    discovered_at: "2026-11-14T18:00:00Z",
    description: "Build GPU cluster orchestration, LLM inference pipelines, and automated dataset processing infrastructure.",
    required_skills: ["Kubernetes", "Slurm", "PyTorch", "Python", "GCP"],
  },
  {
    id: "job-006",
    title: "Senior Backend Engineer (Easy Apply)",
    company: "Coinbase",
    location: "Remote (US)",
    work_mode: "Remote",
    platform: "LinkedIn",
    external_id: "li-cb-102948",
    canonical_url: "https://www.linkedin.com/jobs/view/102948",
    employment_type: "Full-Time (W2)",
    salary_range: "$175,000 - $215,000",
    match_score: 68,
    hard_gates_passed: true,
    discovered_at: "2026-11-14T14:20:00Z",
    description: "Develop digital currency trading microservices, custodial wallets, and secure settlement protocols.",
    required_skills: ["Go", "Docker", "PostgreSQL", "Security", "Distributed Systems"],
  },
]

export default function JobsPage() {
  const [jobs, setJobs] = React.useState<JobItem[]>(FALLBACK_JOBS)
  const [isLoading, setIsLoading] = React.useState<boolean>(true)
  const [search, setSearch] = React.useState<string>("")
  const [platformFilter, setPlatformFilter] = React.useState<string>("all")
  const [workModeFilter, setWorkModeFilter] = React.useState<string>("all")
  const [minScoreFilter, setMinScoreFilter] = React.useState<number>(0)
  const [sortBy, setSortBy] = React.useState<"score" | "newest" | "company">("score")
  const [isDiscovering, setIsDiscovering] = React.useState<boolean>(false)

  React.useEffect(() => {
    let ignore = false

    apiClient
      .getJobs()
      .then((res) => {
        if (!ignore && res?.items && res.items.length > 0) {
          setJobs(res.items)
        }
      })
      .catch(() => {
        // Fallback to snapshot dataset
        if (!ignore) setJobs(FALLBACK_JOBS)
      })
      .finally(() => {
        if (!ignore) setIsLoading(false)
      })

    return () => {
      ignore = true
    }
  }, [])

  const handleTriggerDiscovery = () => {
    setIsDiscovering(true)
    setTimeout(() => {
      setIsDiscovering(false)
    }, 1200)
  }

  // Filter & Sort Logic
  const filteredJobs = React.useMemo(() => {
    return jobs
      .filter((job) => {
        if (platformFilter !== "all" && job.platform.toLowerCase() !== platformFilter.toLowerCase()) {
          return false
        }
        if (workModeFilter !== "all" && job.work_mode.toLowerCase() !== workModeFilter.toLowerCase()) {
          return false
        }
        if (job.match_score < minScoreFilter) {
          return false
        }
        if (search.trim()) {
          const q = search.toLowerCase()
          const matchesTitle = job.title.toLowerCase().includes(q)
          const matchesCompany = job.company.toLowerCase().includes(q)
          const matchesSkills = job.required_skills?.some((s) => s.toLowerCase().includes(q))
          if (!matchesTitle && !matchesCompany && !matchesSkills) {
            return false
          }
        }
        return true
      })
      .sort((a, b) => {
        if (sortBy === "score") return b.match_score - a.match_score
        if (sortBy === "newest") return new Date(b.discovered_at).getTime() - new Date(a.discovered_at).getTime()
        if (sortBy === "company") return a.company.localeCompare(b.company)
        return 0
      })
  }, [jobs, search, platformFilter, workModeFilter, minScoreFilter, sortBy])

  const highMatchCount = jobs.filter((j) => j.match_score >= 80).length
  const eligibleCount = jobs.filter((j) => j.match_score >= 65).length

  return (
    <div className="space-y-6">
      <PageHeader
        title="Job Discovery & Queue"
        description="Discovered jobs across supported boards with explainable 6-dimension matching scores and deterministic hard gates."
        breadcrumbs={[
          { label: "Overview", href: "/" },
          { label: "Job Queue" },
        ]}
        badge={
          <Badge variant="outline" className="gap-1 font-mono text-xs">
            <span>{jobs.length} Jobs Total</span>
          </Badge>
        }
        actions={
          <Button
            variant="default"
            size="sm"
            onClick={handleTriggerDiscovery}
            disabled={isDiscovering}
            className="gap-1.5 bg-blue-600 hover:bg-blue-700"
          >
            <Sparkles className={`size-4 ${isDiscovering ? "animate-spin" : ""}`} />
            <span>{isDiscovering ? "Discovering..." : "Scan Boards Now"}</span>
          </Button>
        }
      />

      {/* KPI Summary Strip */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <div className="rounded-xl border border-slate-200/80 bg-white p-3.5 shadow-xs">
          <p className="text-xs text-slate-500 font-medium">Discovered Jobs</p>
          <p className="text-xl font-bold text-slate-900 mt-0.5">{jobs.length}</p>
        </div>
        <div className="rounded-xl border border-slate-200/80 bg-white p-3.5 shadow-xs">
          <p className="text-xs text-slate-500 font-medium">High Matches (&gt;=80%)</p>
          <p className="text-xl font-bold text-emerald-600 mt-0.5">{highMatchCount}</p>
        </div>
        <div className="rounded-xl border border-slate-200/80 bg-white p-3.5 shadow-xs">
          <p className="text-xs text-slate-500 font-medium">Eligible (&gt;=65%)</p>
          <p className="text-xl font-bold text-blue-600 mt-0.5">{eligibleCount}</p>
        </div>
        <div className="rounded-xl border border-slate-200/80 bg-white p-3.5 shadow-xs">
          <p className="text-xs text-slate-500 font-medium">Hard Gates Passed</p>
          <p className="text-xl font-bold text-slate-900 mt-0.5">
            {jobs.filter((j) => j.hard_gates_passed).length}
          </p>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="flex flex-col gap-3 rounded-xl border border-slate-200/80 bg-white p-4 shadow-xs">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="w-full sm:max-w-md">
            <SearchInput
              placeholder="Search by job title, company, or skills..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              onClear={() => setSearch("")}
            />
          </div>

          <div className="flex flex-wrap items-center gap-2">
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

            {/* Work Mode Filter */}
            <select
              aria-label="Filter by Work Mode"
              value={workModeFilter}
              onChange={(e) => setWorkModeFilter(e.target.value)}
              className="h-9 rounded-md border border-slate-200 bg-white px-2.5 text-xs text-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-600/20"
            >
              <option value="all">All Work Modes</option>
              <option value="remote">Remote Only</option>
              <option value="hybrid">Hybrid</option>
              <option value="on-site">On-site</option>
            </select>

            {/* Min Score Filter */}
            <select
              aria-label="Filter by Min Score"
              value={minScoreFilter}
              onChange={(e) => setMinScoreFilter(Number(e.target.value))}
              className="h-9 rounded-md border border-slate-200 bg-white px-2.5 text-xs text-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-600/20"
            >
              <option value={0}>All Scores</option>
              <option value={80}>&gt;= 80% (High Match)</option>
              <option value={70}>&gt;= 70% (Eligible)</option>
              <option value={60}>&gt;= 60% (Moderate)</option>
            </select>

            {/* Sort Order */}
            <div className="flex items-center gap-1 border-l border-slate-200 pl-2">
              <ArrowUpDown className="size-3.5 text-slate-400" />
              <select
                aria-label="Sort Order"
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value as "score" | "newest" | "company")}
                className="h-9 rounded-md border border-slate-200 bg-white px-2.5 text-xs text-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-600/20"
              >
                <option value="score">Score: High to Low</option>
                <option value="newest">Discovered: Newest</option>
                <option value="company">Company: A to Z</option>
              </select>
            </div>
          </div>
        </div>

        {/* Active Filter Pills */}
        {(platformFilter !== "all" || workModeFilter !== "all" || minScoreFilter > 0 || search) && (
          <div className="flex flex-wrap items-center gap-1.5 pt-2 border-t border-slate-100 text-xs">
            <span className="text-slate-500 text-[11px] font-medium flex items-center gap-1">
              <Filter className="size-3" /> Active Filters:
            </span>
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
            {workModeFilter !== "all" && (
              <Badge variant="secondary" className="gap-1">
                <span>Mode: {workModeFilter}</span>
                <button
                  type="button"
                  onClick={() => setWorkModeFilter("all")}
                  className="hover:text-slate-900"
                >
                  ×
                </button>
              </Badge>
            )}
            {minScoreFilter > 0 && (
              <Badge variant="secondary" className="gap-1">
                <span>Min Score: {minScoreFilter}%</span>
                <button
                  type="button"
                  onClick={() => setMinScoreFilter(0)}
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
                setPlatformFilter("all")
                setWorkModeFilter("all")
                setMinScoreFilter(0)
                setSearch("")
              }}
              className="text-[11px] text-blue-600 hover:underline ml-1"
            >
              Reset all
            </button>
          </div>
        )}
      </div>

      {/* Jobs Table List */}
      <div className="rounded-xl border border-slate-200/80 bg-white p-5 shadow-xs space-y-4">
        {isLoading ? (
          <div className="space-y-3 py-4">
            {[1, 2, 3, 4, 5].map((i) => (
              <div key={i} className="flex items-center justify-between py-2 border-b border-slate-100">
                <div className="space-y-1.5">
                  <Skeleton className="h-4 w-64" />
                  <Skeleton className="h-3 w-40" />
                </div>
                <Skeleton className="h-7 w-24 rounded-full" />
              </div>
            ))}
          </div>
        ) : filteredJobs.length === 0 ? (
          <EmptyState
            icon={Building}
            title="No matching jobs discovered"
            description="No job postings matched your current search filters. Try widening the score range or platform filters."
            action={
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  setPlatformFilter("all")
                  setWorkModeFilter("all")
                  setMinScoreFilter(0)
                  setSearch("")
                }}
              >
                Clear All Filters
              </Button>
            }
          />
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Role & Company</TableHead>
                <TableHead>Location & Mode</TableHead>
                <TableHead>Platform</TableHead>
                <TableHead>Match Score</TableHead>
                <TableHead>Hard Gates</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredJobs.map((job) => {
                const scoreVariant =
                  job.match_score >= 80
                    ? "text-emerald-700 bg-emerald-50 border-emerald-200"
                    : job.match_score >= 70
                    ? "text-blue-700 bg-blue-50 border-blue-200"
                    : job.match_score >= 60
                    ? "text-amber-700 bg-amber-50 border-amber-200"
                    : "text-rose-700 bg-rose-50 border-rose-200"

                return (
                  <TableRow key={job.id}>
                    <TableCell>
                      <Link
                        href={`/jobs/${job.id}`}
                        className="font-medium text-slate-900 hover:text-blue-600 hover:underline"
                      >
                        {job.title}
                      </Link>
                      <div className="text-xs text-slate-500 flex items-center gap-2 mt-0.5">
                        <span className="font-medium text-slate-700">{job.company}</span>
                        {job.salary_range && (
                          <span className="text-emerald-600 font-medium">
                            • {job.salary_range}
                          </span>
                        )}
                      </div>
                      {job.required_skills && job.required_skills.length > 0 && (
                        <div className="flex flex-wrap gap-1 mt-1.5">
                          {job.required_skills.slice(0, 4).map((skill) => (
                            <span
                              key={skill}
                              className="rounded bg-slate-100 px-1.5 py-0.5 text-[10px] font-medium text-slate-600"
                            >
                              {skill}
                            </span>
                          ))}
                          {job.required_skills.length > 4 && (
                            <span className="text-[10px] text-slate-400">
                              +{job.required_skills.length - 4} more
                            </span>
                          )}
                        </div>
                      )}
                    </TableCell>

                    <TableCell>
                      <div className="text-xs font-medium text-slate-700 flex items-center gap-1">
                        <MapPin className="size-3 text-slate-400 shrink-0" />
                        <span className="truncate max-w-[160px]">{job.location}</span>
                      </div>
                      <Badge variant="outline" size="sm" className="mt-1 text-[10px]">
                        {job.work_mode}
                      </Badge>
                    </TableCell>

                    <TableCell>
                      <Badge variant="secondary" size="sm">
                        {job.platform}
                      </Badge>
                    </TableCell>

                    <TableCell>
                      <div className="flex items-center gap-2">
                        <span
                          className={`inline-flex items-center justify-center rounded-lg border px-2 py-0.5 font-mono text-xs font-bold ${scoreVariant}`}
                        >
                          {job.match_score}%
                        </span>
                        <div className="h-1.5 w-14 overflow-hidden rounded-full bg-slate-100 hidden sm:block">
                          <div
                            className={`h-full rounded-full ${
                              job.match_score >= 80
                                ? "bg-emerald-500"
                                : job.match_score >= 70
                                ? "bg-blue-600"
                                : "bg-amber-500"
                            }`}
                            style={{ width: `${job.match_score}%` }}
                          />
                        </div>
                      </div>
                    </TableCell>

                    <TableCell>
                      {job.hard_gates_passed ? (
                        <div className="flex items-center gap-1 text-xs text-emerald-700 font-medium">
                          <CheckCircle2 className="size-4 text-emerald-600 shrink-0" />
                          <span>Passed</span>
                        </div>
                      ) : (
                        <div className="flex items-center gap-1 text-xs text-rose-700 font-medium">
                          <XCircle className="size-4 text-rose-600 shrink-0" />
                          <span>Failed</span>
                        </div>
                      )}
                    </TableCell>

                    <TableCell className="text-right">
                      <div className="flex items-center justify-end gap-1.5">
                        <Link href={`/jobs/${job.id}`}>
                          <Button variant="outline" size="xs" className="gap-1">
                            <Eye className="size-3.5" />
                            <span>Breakdown</span>
                          </Button>
                        </Link>
                        <a
                          href={job.canonical_url}
                          target="_blank"
                          rel="noreferrer"
                          className="inline-flex size-7 items-center justify-center rounded-md border border-slate-200 text-slate-600 hover:bg-slate-50"
                          title="Open original job posting"
                        >
                          <ExternalLink className="size-3.5" />
                        </a>
                      </div>
                    </TableCell>
                  </TableRow>
                )
              })}
            </TableBody>
          </Table>
        )}
      </div>
    </div>
  )
}
