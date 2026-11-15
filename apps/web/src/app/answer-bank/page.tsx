"use client"

import * as React from "react"
import {
  Filter,
  Plus,
  ShieldAlert,
} from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { PageHeader } from "@/components/ui/page-header"
import { SearchInput } from "@/components/ui/input"
import { Dialog } from "@/components/ui/dialog"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { apiClient } from "@/lib/api-client"
import type { AnswerBankItem } from "@/types/api"

const FALLBACK_ANSWERS: AnswerBankItem[] = [
  {
    id: "ans-001",
    category: "Contact & Identity",
    question_pattern: "Full Name / Legal Name",
    answer_text: "Kartik Shukla",
    policy: "auto",
    aliases: ["first_name", "last_name", "legal_name", "full_name"],
    updated_at: "2026-11-15T08:00:00Z",
  },
  {
    id: "ans-002",
    category: "Contact & Identity",
    question_pattern: "Primary Email Address",
    answer_text: "kartik.shukla@example.com",
    policy: "auto",
    aliases: ["email", "email_address", "contact_email"],
    updated_at: "2026-11-15T08:00:00Z",
  },
  {
    id: "ans-003",
    category: "Work Authorization",
    question_pattern: "Are you authorized to work in the US?",
    answer_text: "Yes, authorized to work in the United States without restriction.",
    policy: "auto",
    aliases: ["work_auth", "us_work_authorization", "eligible_to_work_us"],
    updated_at: "2026-11-15T08:00:00Z",
  },
  {
    id: "ans-004",
    category: "Work Authorization",
    question_pattern: "Will you now or in the future require visa sponsorship?",
    answer_text: "No",
    policy: "auto+log",
    aliases: ["requires_sponsorship", "visa_sponsorship", "need_sponsorship"],
    updated_at: "2026-11-15T08:00:00Z",
  },
  {
    id: "ans-005",
    category: "Compensation",
    question_pattern: "Desired Annual Base Salary",
    answer_text: "$185,000 - $225,000",
    policy: "always_ask",
    aliases: ["salary_expectation", "desired_salary", "compensation_target"],
    updated_at: "2026-11-15T08:00:00Z",
  },
  {
    id: "ans-006",
    category: "Notice Period",
    question_pattern: "What is your earliest availability / notice period?",
    answer_text: "2 weeks from offer acceptance",
    policy: "auto+log",
    aliases: ["notice_period", "availability", "start_date"],
    updated_at: "2026-11-15T08:00:00Z",
  },
  {
    id: "ans-007",
    category: "Experience",
    question_pattern: "Years of experience with Kubernetes and distributed systems?",
    answer_text: "6+ years designing and running multi-cluster production Kubernetes.",
    policy: "auto",
    aliases: ["k8s_experience", "kubernetes_years", "distributed_systems_exp"],
    updated_at: "2026-11-15T08:00:00Z",
  },
  {
    id: "ans-008",
    category: "Relocation",
    question_pattern: "Are you open to relocation?",
    answer_text: "Open to San Francisco Bay Area and Seattle for hybrid platform roles.",
    policy: "always_ask",
    aliases: ["relocation", "willing_to_relocate", "relocate_ok"],
    updated_at: "2026-11-15T08:00:00Z",
  },
  {
    id: "ans-009",
    category: "Equal Opportunity",
    question_pattern: "Voluntary Equal Opportunity Demographics",
    answer_text: "I do not wish to self-identify",
    policy: "auto+log",
    aliases: ["gender", "race_ethnicity", "veteran_status", "disability_status"],
    updated_at: "2026-11-15T08:00:00Z",
  },
  {
    id: "ans-010",
    category: "Sensitive / Prohibited",
    question_pattern: "Account Passwords, SSN, OTPs, or Credit Card Numbers",
    answer_text: "[BLOCKED BY POLICY ENGINE — NEVER FILL]",
    policy: "never_fill",
    aliases: ["password", "ssn", "social_security", "otp", "credit_card", "bank_account"],
    updated_at: "2026-11-15T08:00:00Z",
  },
]

export default function AnswerBankPage() {
  const [answers, setAnswers] = React.useState<AnswerBankItem[]>(FALLBACK_ANSWERS)
  const [search, setSearch] = React.useState<string>("")
  const [categoryFilter, setCategoryFilter] = React.useState<string>("all")
  const [policyFilter, setPolicyFilter] = React.useState<string>("all")
  const [modalOpen, setModalOpen] = React.useState<boolean>(false)
  const [newQuestion, setNewQuestion] = React.useState<string>("")
  const [newAnswer, setNewAnswer] = React.useState<string>("")
  const [newCategory, setNewCategory] = React.useState<string>("Contact & Identity")
  const [newPolicy, setNewPolicy] = React.useState<"auto" | "auto+log" | "always_ask">("auto")

  React.useEffect(() => {
    let ignore = false

    if (apiClient.getAnswerBank) {
      Promise.resolve(apiClient.getAnswerBank())
        .then((items) => {
          if (!ignore && items && items.length > 0) {
            setAnswers(items)
          }
        })
        .catch(() => {
          if (!ignore) setAnswers(FALLBACK_ANSWERS)
        })
    }

    return () => {
      ignore = true
    }
  }, [])

  const filteredAnswers = React.useMemo(() => {
    return answers.filter((item) => {
      if (categoryFilter !== "all" && item.category !== categoryFilter) {
        return false
      }
      if (policyFilter !== "all" && item.policy !== policyFilter) {
        return false
      }
      if (search.trim()) {
        const q = search.toLowerCase()
        const matchQ = item.question_pattern.toLowerCase().includes(q)
        const matchA = item.answer_text.toLowerCase().includes(q)
        const matchAliases = item.aliases.some((a) => a.toLowerCase().includes(q))
        if (!matchQ && !matchA && !matchAliases) return false
      }
      return true
    })
  }, [answers, search, categoryFilter, policyFilter])

  const handleAddAnswer = () => {
    if (!newQuestion.trim() || !newAnswer.trim()) return

    const newItem: AnswerBankItem = {
      id: `ans-${Date.now().toString().slice(-4)}`,
      category: newCategory,
      question_pattern: newQuestion.trim(),
      answer_text: newAnswer.trim(),
      policy: newPolicy,
      aliases: [newQuestion.toLowerCase().replace(/[^a-z0-9]/g, "_").slice(0, 20)],
      updated_at: new Date().toISOString(),
    }

    setAnswers((prev) => [newItem, ...prev])
    setNewQuestion("")
    setNewAnswer("")
    setModalOpen(false)
  }

  const categories = Array.from(new Set(answers.map((a) => a.category)))

  return (
    <div className="space-y-6">
      <PageHeader
        title="Candidate Answer Bank"
        description="Truthful answer repository with provenance tracking, freshness validation, and code-enforced PolicyEngine rules."
        breadcrumbs={[
          { label: "Overview", href: "/" },
          { label: "Answer Bank" },
        ]}
        badge={
          <Badge variant="outline" className="gap-1 font-mono text-xs">
            <span>{answers.length} Answers Managed</span>
          </Badge>
        }
        actions={
          <Button
            variant="default"
            size="sm"
            onClick={() => setModalOpen(true)}
            className="gap-1.5 bg-blue-600 hover:bg-blue-700"
          >
            <Plus className="size-4" />
            <span>Add Answer</span>
          </Button>
        }
      />

      {/* Sensitive Questions Security Warning */}
      <div className="flex items-start gap-2.5 rounded-xl border border-rose-200 bg-rose-50/70 p-3.5 text-xs text-rose-900 shadow-xs">
        <ShieldAlert className="size-4 shrink-0 text-rose-600 mt-0.5" />
        <div>
          <span className="font-semibold">Section 13 Security Policy:</span> Storing or automating account passwords, SSNs, credit card numbers, or OTP codes is permanently forbidden. Any field identified by PolicyEngine matching credential patterns triggers an automatic <code className="rounded bg-rose-100 px-1 py-0.5 font-mono text-[11px]">never_fill</code> barrier halting execution.
        </div>
      </div>

      {/* Search & Filter Bar */}
      <div className="flex flex-col gap-3 rounded-xl border border-slate-200/80 bg-white p-4 shadow-xs">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="w-full sm:max-w-md">
            <SearchInput
              placeholder="Search question prompt, answer text, or alias..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              onClear={() => setSearch("")}
            />
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <select
              aria-label="Filter by Category"
              value={categoryFilter}
              onChange={(e) => setCategoryFilter(e.target.value)}
              className="h-9 rounded-md border border-slate-200 bg-white px-2.5 text-xs text-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-600/20"
            >
              <option value="all">All Categories ({categories.length})</option>
              {categories.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>

            <select
              aria-label="Filter by Policy"
              value={policyFilter}
              onChange={(e) => setPolicyFilter(e.target.value)}
              className="h-9 rounded-md border border-slate-200 bg-white px-2.5 text-xs text-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-600/20"
            >
              <option value="all">All Policies</option>
              <option value="auto">auto (Standard Fill)</option>
              <option value="auto+log">auto+log (Audited Fill)</option>
              <option value="always_ask">always_ask (Requires Approval)</option>
              <option value="never_fill">never_fill (Blocked Credentials)</option>
            </select>
          </div>
        </div>

        {/* Active Filters Strip */}
        {(categoryFilter !== "all" || policyFilter !== "all" || search) && (
          <div className="flex flex-wrap items-center gap-1.5 pt-2 border-t border-slate-100 text-xs">
            <span className="text-slate-500 text-[11px] font-medium flex items-center gap-1">
              <Filter className="size-3" /> Filters:
            </span>
            {categoryFilter !== "all" && (
              <Badge variant="secondary" className="gap-1">
                <span>Category: {categoryFilter}</span>
                <button
                  type="button"
                  onClick={() => setCategoryFilter("all")}
                  className="hover:text-slate-900"
                >
                  ×
                </button>
              </Badge>
            )}
            {policyFilter !== "all" && (
              <Badge variant="secondary" className="gap-1">
                <span>Policy: {policyFilter}</span>
                <button
                  type="button"
                  onClick={() => setPolicyFilter("all")}
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
                setCategoryFilter("all")
                setPolicyFilter("all")
                setSearch("")
              }}
              className="text-[11px] text-blue-600 hover:underline ml-1"
            >
              Reset
            </button>
          </div>
        )}
      </div>

      {/* Answers Table */}
      <div className="rounded-xl border border-slate-200/80 bg-white p-5 shadow-xs space-y-4">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Category</TableHead>
              <TableHead>Question Pattern & Aliases</TableHead>
              <TableHead>Resolved Answer</TableHead>
              <TableHead>Policy Rule</TableHead>
              <TableHead className="text-right">Last Verified</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {filteredAnswers.map((item) => (
              <TableRow key={item.id}>
                <TableCell>
                  <Badge variant="secondary" size="sm">
                    {item.category}
                  </Badge>
                </TableCell>

                <TableCell>
                  <div className="font-semibold text-slate-900 text-xs">
                    {item.question_pattern}
                  </div>
                  <div className="flex flex-wrap gap-1 mt-1">
                    {item.aliases.map((alias) => (
                      <span
                        key={alias}
                        className="rounded bg-slate-100 px-1.5 py-0.2 font-mono text-[10px] text-slate-500"
                      >
                        {alias}
                      </span>
                    ))}
                  </div>
                </TableCell>

                <TableCell>
                  <div className="font-mono text-xs text-slate-800 max-w-md truncate">
                    {item.answer_text}
                  </div>
                </TableCell>

                <TableCell>
                  <Badge
                    variant={
                      item.policy === "auto"
                        ? "success"
                        : item.policy === "auto+log"
                        ? "info"
                        : item.policy === "always_ask"
                        ? "warning"
                        : "destructive"
                    }
                    size="sm"
                    className="font-mono"
                  >
                    {item.policy}
                  </Badge>
                </TableCell>

                <TableCell className="text-right text-xs text-slate-500">
                  {new Date(item.updated_at).toLocaleDateString(undefined, {
                    month: "short",
                    day: "numeric",
                  })}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      {/* Add Answer Modal */}
      {modalOpen && (
        <Dialog
          open={modalOpen}
          onClose={() => setModalOpen(false)}
          title="Add Verified Answer"
          description="Register a truthful candidate answer for deterministic form filling."
          footer={
            <>
              <Button variant="outline" size="sm" onClick={() => setModalOpen(false)}>
                Cancel
              </Button>
              <Button
                variant="default"
                size="sm"
                onClick={handleAddAnswer}
                disabled={!newQuestion.trim() || !newAnswer.trim()}
                className="bg-blue-600 hover:bg-blue-700"
              >
                Save Answer
              </Button>
            </>
          }
        >
          <div className="space-y-3 text-xs text-slate-700">
            <div className="space-y-1">
              <label className="font-medium text-slate-700">Category Taxonomy</label>
              <select
                value={newCategory}
                onChange={(e) => setNewCategory(e.target.value)}
                className="w-full h-8 rounded-md border border-slate-200 bg-white px-2 text-xs"
              >
                {categories.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
            </div>

            <div className="space-y-1">
              <label className="font-medium text-slate-700">Question Pattern / Label</label>
              <input
                type="text"
                placeholder="e.g. Willingness to Travel"
                value={newQuestion}
                onChange={(e) => setNewQuestion(e.target.value)}
                className="w-full h-8 rounded-md border border-slate-200 px-2 text-xs focus:outline-none focus:ring-2 focus:ring-blue-600/20"
              />
            </div>

            <div className="space-y-1">
              <label className="font-medium text-slate-700">Canonical Answer</label>
              <textarea
                rows={3}
                placeholder="e.g. Yes, up to 15% travel for key customer architecture reviews."
                value={newAnswer}
                onChange={(e) => setNewAnswer(e.target.value)}
                className="w-full rounded-md border border-slate-200 p-2 text-xs focus:outline-none focus:ring-2 focus:ring-blue-600/20"
              />
            </div>

            <div className="space-y-1">
              <label className="font-medium text-slate-700">Policy Engine Rule</label>
              <select
                value={newPolicy}
                onChange={(e) => setNewPolicy(e.target.value as "auto" | "auto+log" | "always_ask")}
                className="w-full h-8 rounded-md border border-slate-200 bg-white px-2 text-xs"
              >
                <option value="auto">auto — Fill deterministically</option>
                <option value="auto+log">auto+log — Fill with audit log</option>
                <option value="always_ask">always_ask — Require operator confirmation</option>
              </select>
            </div>
          </div>
        </Dialog>
      )}
    </div>
  )
}
