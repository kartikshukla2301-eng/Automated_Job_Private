"use client"

import * as React from "react"
import { Plus, Check } from "lucide-react"
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

export default function AnswerBankPage() {
  const [search, setSearch] = React.useState("")

  return (
    <div className="space-y-6">
      <PageHeader
        title="Candidate Answer Bank"
        description="Truthful answer repository with provenance tracking, freshness validation, and policy rules."
        breadcrumbs={[
          { label: "Overview", href: "/" },
          { label: "Answer Bank" },
        ]}
        actions={
          <Button variant="default" size="sm" className="gap-1.5 bg-blue-600 hover:bg-blue-700">
            <Plus className="size-4" />
            <span>Add Answer</span>
          </Button>
        }
      />

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between rounded-xl border border-slate-200/80 bg-white p-3.5 shadow-xs">
        <div className="w-full sm:max-w-sm">
          <SearchInput
            placeholder="Search questions, keys, categories..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onClear={() => setSearch("")}
          />
        </div>

        <div className="flex items-center gap-2 overflow-x-auto">
          <select className="h-9 rounded-md border border-slate-200 bg-white px-2.5 text-xs text-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-600/20">
            <option value="">All Categories</option>
            <option value="identity">Identity & Contact</option>
            <option value="work_auth">Work Authorization</option>
            <option value="compensation">Compensation</option>
            <option value="preferences">Work Preferences</option>
          </select>

          <select className="h-9 rounded-md border border-slate-200 bg-white px-2.5 text-xs text-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-600/20">
            <option value="">All Policies</option>
            <option value="auto">auto</option>
            <option value="auto+log">auto+log</option>
            <option value="always_ask">always_ask</option>
            <option value="never_fill">never_fill</option>
          </select>
        </div>
      </div>

      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Field Key & Aliases</TableHead>
            <TableHead>Canonical Answer</TableHead>
            <TableHead>Category</TableHead>
            <TableHead>Policy</TableHead>
            <TableHead>Source</TableHead>
            <TableHead>Freshness</TableHead>
            <TableHead className="text-right">Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {[
            {
              key: "work_authorization_us",
              aliases: ["authorized_us", "us_citizen", "legally_authorized"],
              value: "Yes",
              category: "work_authorization",
              policy: "auto+log",
              source: "user",
              verified: true,
              validUntil: "2027-12-31",
            },
            {
              key: "notice_period_days",
              aliases: ["notice_period", "earliest_start_date"],
              value: "30 days",
              category: "availability",
              policy: "auto",
              source: "profile",
              verified: true,
              validUntil: "2027-06-30",
            },
            {
              key: "salary_expectation_annual",
              aliases: ["target_comp", "desired_salary"],
              value: "$180,000",
              category: "compensation",
              policy: "always_ask",
              source: "user",
              verified: true,
              validUntil: "2027-01-01",
            },
            {
              key: "relocation_willingness",
              aliases: ["willing_to_relocate"],
              value: "Remote preferred; open to SF/NYC",
              category: "work_preferences",
              policy: "always_ask",
              source: "user",
              verified: true,
              validUntil: "2027-01-01",
            },
          ].map((item) => (
            <TableRow key={item.key}>
              <TableCell>
                <div className="font-mono font-semibold text-slate-900 text-xs">
                  {item.key}
                </div>
                <div className="text-[10px] text-slate-400 mt-0.5">
                  Aliases: {item.aliases.join(", ")}
                </div>
              </TableCell>
              <TableCell className="font-mono text-xs text-slate-800">
                {item.value}
              </TableCell>
              <TableCell>
                <Badge variant="secondary">{item.category}</Badge>
              </TableCell>
              <TableCell>
                <Badge
                  variant={
                    item.policy === "always_ask"
                      ? "warning"
                      : item.policy === "never_fill"
                      ? "destructive"
                      : "default"
                  }
                >
                  {item.policy}
                </Badge>
              </TableCell>
              <TableCell>
                <span className="text-xs text-slate-600 capitalize">{item.source}</span>
              </TableCell>
              <TableCell>
                <div className="flex items-center gap-1 text-xs text-emerald-600 font-medium">
                  <Check className="size-3.5" />
                  <span>Valid</span>
                </div>
                <div className="text-[10px] text-slate-400 mt-0.5">
                  until {item.validUntil}
                </div>
              </TableCell>
              <TableCell className="text-right">
                <Button variant="ghost" size="xs">
                  Edit
                </Button>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}
