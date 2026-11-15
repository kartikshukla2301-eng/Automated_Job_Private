"use client"

import * as React from "react"
import { ShieldAlert, ShieldCheck, Lock, AlertOctagon, Clock } from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { PageHeader } from "@/components/ui/page-header"

export default function AutomationPage() {
  const [killActive, setKillActive] = React.useState(false)

  return (
    <div className="space-y-6">
      <PageHeader
        title="Automation & Safety Control Center"
        description="Centralized kill switch, scheduler windows, rate caps, and fail-closed safety controls."
        breadcrumbs={[
          { label: "Overview", href: "/" },
          { label: "Automation" },
        ]}
        badge={
          <Badge variant="destructive" className="gap-1 font-semibold">
            <Lock className="size-3.5" />
            <span>REAL SUBMISSION LOCKED DISABLED</span>
          </Badge>
        }
      />

      {/* Emergency Kill Switch Bar */}
      <div className="rounded-xl border border-red-300 bg-red-50/70 p-5 shadow-xs flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div className="space-y-1">
          <div className="flex items-center gap-2 text-red-900 font-bold text-sm">
            <AlertOctagon className="size-5 text-red-600" />
            <span>Global Emergency Kill Switch</span>
          </div>
          <p className="text-xs text-red-800 max-w-xl">
            Tripping the kill switch immediately halts all background runner tasks, Playwright browser sessions, and scheduled discovery cycles with zero latency fail-closed.
          </p>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          {killActive ? (
            <Button
              variant="default"
              size="sm"
              onClick={() => setKillActive(false)}
              className="bg-emerald-600 hover:bg-emerald-700 text-white gap-1.5"
            >
              <ShieldCheck className="size-4" />
              <span>Reset Kill Switch</span>
            </Button>
          ) : (
            <Button
              variant="destructive"
              size="sm"
              onClick={() => setKillActive(true)}
              className="bg-red-600 hover:bg-red-700 text-white gap-1.5 font-bold shadow-xs"
            >
              <ShieldAlert className="size-4" />
              <span>TRIP EMERGENCY KILL SWITCH</span>
            </Button>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
        {/* Scheduler & Operating Window */}
        <div className="rounded-xl border border-slate-200/80 bg-white p-5 shadow-xs space-y-4">
          <h3 className="text-sm font-semibold text-slate-900 flex items-center gap-2">
            <Clock className="size-4 text-slate-400" />
            <span>Scheduler & Operating Window</span>
          </h3>

          <div className="space-y-2.5 text-xs text-slate-700">
            <div className="flex justify-between py-1.5 border-b border-slate-100">
              <span className="text-slate-500">Scheduler Engine</span>
              <span className="font-semibold text-slate-900">APScheduler (Local Windows)</span>
            </div>
            <div className="flex justify-between py-1.5 border-b border-slate-100">
              <span className="text-slate-500">Active Window</span>
              <span className="font-semibold text-slate-900">09:00 — 23:00 IST (Daily)</span>
            </div>
            <div className="flex justify-between py-1.5 border-b border-slate-100">
              <span className="text-slate-500">Jitter Delay</span>
              <span className="font-semibold text-slate-900">30s – 90s randomized</span>
            </div>
            <div className="flex justify-between py-1.5 border-b border-slate-100">
              <span className="text-slate-500">Single-Run Concurrency Lock</span>
              <Badge variant="success" size="sm">ACTIVE</Badge>
            </div>
          </div>
        </div>

        {/* Rate Limits & Caps */}
        <div className="rounded-xl border border-slate-200/80 bg-white p-5 shadow-xs space-y-4">
          <h3 className="text-sm font-semibold text-slate-900">
            Application Ceilings & Anti-Spam Bounds
          </h3>

          <div className="space-y-2.5 text-xs text-slate-700">
            <div className="flex justify-between py-1.5 border-b border-slate-100">
              <span className="text-slate-500">Active Daily Cap</span>
              <span className="font-bold text-slate-900">2 applications / day</span>
            </div>
            <div className="flex justify-between py-1.5 border-b border-slate-100">
              <span className="text-slate-500">Daily Cap Utilization</span>
              <span className="font-semibold text-emerald-600">0 / 2 used today</span>
            </div>
            <div className="flex justify-between py-1.5 border-b border-slate-100">
              <span className="text-slate-500">Company Anti-Spam Cooldown</span>
              <span className="font-semibold text-slate-900">30 days per company</span>
            </div>
            <div className="flex justify-between py-1.5 border-b border-slate-100">
              <span className="text-slate-500">Auto-Promotion</span>
              <Badge variant="outline" size="sm">DISABLED (Strict Owner Review)</Badge>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
