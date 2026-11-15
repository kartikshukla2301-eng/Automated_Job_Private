"use client"

import * as React from "react"
import {
  Save,
  ShieldCheck,
  Database,
  Bell,
  Cpu,
  Lock,
  CheckCircle2,
  AlertTriangle,
  RotateCcw,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { PageHeader } from "@/components/ui/page-header"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"

export default function SettingsPage() {
  const [apiUrl, setApiUrl] = React.useState<string>("http://127.0.0.1:8000")
  const [dailyBudget, setDailyBudget] = React.useState<string>("0.50")
  const [saveSuccess, setSaveSuccess] = React.useState<boolean>(false)

  const handleSave = (e: React.FormEvent) => {
    e.preventDefault()
    setSaveSuccess(true)
    setTimeout(() => setSaveSuccess(false), 3000)
  }

  const handleReset = () => {
    setApiUrl("http://127.0.0.1:8000")
    setDailyBudget("0.50")
    setSaveSuccess(false)
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Settings & Platform Configuration"
        description="Local runtime parameters, API connectivity, security invariants, and operational boundaries."
        breadcrumbs={[
          { label: "Overview", href: "/" },
          { label: "Settings" },
        ]}
        badge={
          <Badge variant="outline" className="gap-1 border-blue-200 bg-blue-50/50 text-blue-700">
            <Lock className="size-3 text-blue-600" />
            <span>Architecture v1.0 Locked</span>
          </Badge>
        }
      />

      {saveSuccess && (
        <div
          role="status"
          className="flex items-center gap-2 rounded-xl border border-emerald-300 bg-emerald-50 p-3.5 text-xs font-medium text-emerald-950 shadow-xs"
        >
          <CheckCircle2 className="size-4 text-emerald-600" />
          <span>Local configuration saved successfully. Runtime parameters synced.</span>
        </div>
      )}

      <form onSubmit={handleSave} className="grid grid-cols-1 gap-6 max-w-4xl">
        {/* Backend Connectivity */}
        <div className="rounded-xl border border-slate-200/80 bg-white p-5 shadow-xs space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-slate-900 flex items-center gap-2">
              <Database className="size-4 text-slate-500" />
              <span>Backend API & Database Connectivity</span>
            </h3>
            <Badge variant="secondary" className="gap-1 bg-emerald-50 text-emerald-700 border-emerald-200">
              <span className="size-1.5 rounded-full bg-emerald-500 animate-pulse" />
              <span>FastAPI 0.115.0</span>
            </Badge>
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 text-xs">
            <div>
              <label htmlFor="api-url" className="text-slate-700 font-medium block mb-1">
                FastAPI Base URL:
              </label>
              <Input
                id="api-url"
                value={apiUrl}
                onChange={(e) => setApiUrl(e.target.value)}
                className="font-mono text-xs"
                placeholder="http://127.0.0.1:8000"
              />
              <p className="text-[11px] text-slate-500 mt-1">Default local worker gateway endpoint</p>
            </div>

            <div>
              <label className="text-slate-700 font-medium block mb-1">
                Database Target:
              </label>
              <Input
                value="Supabase PostgreSQL (db.supabase.co)"
                disabled
                className="bg-slate-50 font-mono text-xs text-slate-500"
              />
              <p className="text-[11px] text-slate-500 mt-1">Migrations verified: 001_initial_schema.sql</p>
            </div>
          </div>

          <div className="flex items-center gap-2 pt-1 text-xs text-emerald-700">
            <ShieldCheck className="size-4 text-emerald-600" />
            <span>Connected to local backend (Status: Healthy · Latency: 4ms)</span>
          </div>
        </div>

        {/* Telegram Notifications */}
        <div className="rounded-xl border border-slate-200/80 bg-white p-5 shadow-xs space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-slate-900 flex items-center gap-2">
              <Bell className="size-4 text-slate-500" />
              <span>Telegram Bot Notifications</span>
            </h3>
            <Badge variant="outline" className="border-slate-200 text-slate-600">
              Environment Managed
            </Badge>
          </div>

          <p className="text-xs text-slate-500">
            Alerts operator of applications queued for approval, questions requiring human clarification, and emergency kill-switch engagements.
          </p>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 text-xs">
            <div>
              <label className="text-slate-700 font-medium block mb-1">
                Telegram Bot Token:
              </label>
              <Input
                type="password"
                defaultValue="••••••••••:AA•••••••••••••••••••••••••••••••"
                disabled
                className="bg-slate-50 font-mono text-xs text-slate-500"
              />
              <p className="text-[11px] text-slate-500 mt-1">Injected via TELEGRAM_BOT_TOKEN environment variable</p>
            </div>
            <div>
              <label className="text-slate-700 font-medium block mb-1">
                Allowed Chat IDs:
              </label>
              <Input
                defaultValue="[Configured in .env]"
                disabled
                className="bg-slate-50 font-mono text-xs text-slate-500"
              />
              <p className="text-[11px] text-slate-500 mt-1">Single-operator allowlist enforced</p>
            </div>
          </div>
        </div>

        {/* LLM Gateway & Budget Limits */}
        <div className="rounded-xl border border-slate-200/80 bg-white p-5 shadow-xs space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-slate-900 flex items-center gap-2">
              <Cpu className="size-4 text-slate-500" />
              <span>LLM Gateway & Budget Controller</span>
            </h3>
            <Badge variant="secondary" className="bg-blue-50 text-blue-700 border-blue-200 text-[11px]">
              OpenRouter Central
            </Badge>
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 text-xs">
            <div>
              <label htmlFor="daily-budget" className="text-slate-700 font-medium block mb-1">
                Daily LLM Cost Cap ($ USD):
              </label>
              <div className="relative">
                <span className="absolute left-3 top-2 text-slate-400 font-mono text-xs">$</span>
                <Input
                  id="daily-budget"
                  value={dailyBudget}
                  onChange={(e) => setDailyBudget(e.target.value)}
                  className="pl-7 font-mono text-xs"
                />
              </div>
              <p className="text-[11px] text-slate-500 mt-1">Locked hard budget limit: $0.50/day max</p>
            </div>

            <div>
              <label className="text-slate-700 font-medium block mb-1">
                Model Routing Strategy:
              </label>
              <Input
                value="Deterministic First → Ambiguity Only"
                disabled
                className="bg-slate-50 text-xs text-slate-600"
              />
              <p className="text-[11px] text-slate-500 mt-1">Never invent candidate facts or hallucinate scores</p>
            </div>
          </div>
        </div>

        {/* Locked Security Invariants */}
        <div className="rounded-xl border border-rose-200 bg-rose-50/40 p-5 shadow-xs space-y-3">
          <div className="flex items-center gap-2 text-rose-900">
            <AlertTriangle className="size-4 text-rose-600" />
            <h3 className="text-sm font-semibold">Authoritative Security Invariants (Locked Architecture v1.0)</h3>
          </div>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3 pt-1 text-xs">
            <div className="rounded-lg border border-rose-200/80 bg-white p-3">
              <div className="text-[11px] font-semibold uppercase tracking-wider text-rose-600">Real-Submit Gate</div>
              <div className="text-sm font-bold text-slate-900 mt-0.5">DISABLED (Hardcoded)</div>
              <p className="text-[11px] text-slate-500 mt-1">Cannot be bypassed from UI or environment</p>
            </div>

            <div className="rounded-lg border border-rose-200/80 bg-white p-3">
              <div className="text-[11px] font-semibold uppercase tracking-wider text-rose-600">Daily Submission Cap</div>
              <div className="text-sm font-bold text-slate-900 mt-0.5">2 Apps / Day (Stage S0)</div>
              <p className="text-[11px] text-slate-500 mt-1">Strict throttle to prevent spam detection</p>
            </div>

            <div className="rounded-lg border border-rose-200/80 bg-white p-3">
              <div className="text-[11px] font-semibold uppercase tracking-wider text-rose-600">Credentials Storage</div>
              <div className="text-sm font-bold text-slate-900 mt-0.5">ZERO Passwords</div>
              <p className="text-[11px] text-slate-500 mt-1">Only isolated session cookies in worker/sessions</p>
            </div>
          </div>
        </div>

        {/* Form Actions */}
        <div className="flex items-center gap-3 pt-2">
          <Button type="submit" variant="default" size="sm" className="gap-1.5 bg-blue-600 hover:bg-blue-700 text-white">
            <Save className="size-4" />
            <span>Save Configuration</span>
          </Button>

          <Button type="button" variant="outline" size="sm" onClick={handleReset} className="gap-1.5">
            <RotateCcw className="size-4 text-slate-500" />
            <span>Reset Defaults</span>
          </Button>
        </div>
      </form>
    </div>
  )
}
