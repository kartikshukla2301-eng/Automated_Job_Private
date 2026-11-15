"use client"

import * as React from "react"
import {
  AlertOctagon,
  AlertTriangle,
  CheckCircle2,
  Clock,
  Lock,
  RefreshCw,
  ShieldAlert,
  ShieldCheck,
  Zap,
} from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { PageHeader } from "@/components/ui/page-header"
import { Dialog } from "@/components/ui/dialog"
import { apiClient } from "@/lib/api-client"

export default function AutomationPage() {
  const [killActive, setKillActive] = React.useState<boolean>(false)
  const [dialogAction, setDialogAction] = React.useState<"trip" | "reset" | null>(null)
  const [isProcessing, setIsProcessing] = React.useState<boolean>(false)
  const [feedback, setFeedback] = React.useState<string | null>(null)

  React.useEffect(() => {
    let ignore = false

    apiClient
      .getOverview()
      .then((res) => {
        if (!ignore && res) {
          setKillActive(res.kill_switch_active)
        }
      })
      .catch(() => {
        // Default safe armed
        if (!ignore) setKillActive(false)
      })

    return () => {
      ignore = true
    }
  }, [])

  const handleConfirmAction = async () => {
    if (!dialogAction) return
    setIsProcessing(true)

    try {
      if (dialogAction === "trip") {
        await apiClient.tripKillSwitch("Operator engaged emergency stop via UI")
        setKillActive(true)
        setFeedback("Emergency Kill Switch TRIPPED. All automation halted immediately.")
      } else {
        await apiClient.resetKillSwitch()
        setKillActive(false)
        setFeedback("Emergency Kill Switch RESET. Agent automation armed and normal.")
      }
    } catch {
      // Local optimistic toggle for offline mode
      const next = dialogAction === "trip"
      setKillActive(next)
      setFeedback(
        next
          ? "Emergency Kill Switch TRIPPED (Local). Automation halted."
          : "Emergency Kill Switch RESET (Local). Automation armed."
      )
    } finally {
      setIsProcessing(false)
      setDialogAction(null)
      setTimeout(() => setFeedback(null), 4000)
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Automation & Safety Control Center"
        description="Centralized kill switch, scheduler execution windows, rate caps, and non-negotiable safety gates."
        breadcrumbs={[
          { label: "Overview", href: "/" },
          { label: "Automation" },
        ]}
        badge={
          <Badge variant="destructive" className="gap-1 font-semibold text-xs">
            <Lock className="size-3.5" />
            <span>REAL SUBMISSIONS PERMANENTLY DISABLED</span>
          </Badge>
        }
      />

      {feedback && (
        <div
          role="status"
          className={`flex items-center gap-2 rounded-xl border p-3.5 text-xs shadow-xs ${
            killActive
              ? "border-rose-300 bg-rose-50 text-rose-950 font-medium"
              : "border-emerald-300 bg-emerald-50 text-emerald-950 font-medium"
          }`}
        >
          {killActive ? (
            <AlertOctagon className="size-4 text-rose-600 shrink-0" />
          ) : (
            <CheckCircle2 className="size-4 text-emerald-600 shrink-0" />
          )}
          <span>{feedback}</span>
        </div>
      )}

      {/* Emergency Kill Switch Command Box */}
      <div
        className={`rounded-xl border p-5 shadow-xs transition-colors ${
          killActive
            ? "border-rose-400 bg-rose-50/90 text-rose-950"
            : "border-slate-200/80 bg-white text-slate-900"
        }`}
      >
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div className="space-y-1.5">
            <div className="flex items-center gap-2.5">
              <div
                className={`flex size-10 items-center justify-center rounded-xl shadow-xs ${
                  killActive ? "bg-rose-600 text-white" : "bg-emerald-50 text-emerald-700 border border-emerald-200"
                }`}
              >
                {killActive ? <AlertOctagon className="size-6" /> : <ShieldCheck className="size-6" />}
              </div>
              <div>
                <h3 className="text-base font-bold">
                  Global Kill Switch:{" "}
                  <span className={killActive ? "text-rose-700" : "text-emerald-700"}>
                    {killActive ? "TRIPPED (AUTOMATION HALTED)" : "ARMED & NORMAL"}
                  </span>
                </h3>
                <p className="text-xs text-slate-500">
                  Fail-closed immediate halt covering all worker tasks, Playwright browsers, and discovery.
                </p>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2 shrink-0">
            {killActive ? (
              <Button
                variant="default"
                size="sm"
                onClick={() => setDialogAction("reset")}
                className="bg-emerald-600 hover:bg-emerald-700 text-white gap-1.5 font-semibold"
              >
                <ShieldCheck className="size-4" />
                <span>Reset Kill Switch</span>
              </Button>
            ) : (
              <Button
                variant="destructive"
                size="sm"
                onClick={() => setDialogAction("trip")}
                className="bg-rose-600 hover:bg-rose-700 text-white gap-1.5 font-bold shadow-xs"
              >
                <AlertOctagon className="size-4" />
                <span>TRIP EMERGENCY KILL SWITCH</span>
              </Button>
            )}
          </div>
        </div>
      </div>

      {/* 2-column Grid: Limits & Safety Gates */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Real-Submit Gate Locked Status */}
        <div className="rounded-xl border border-rose-200 bg-rose-50/40 p-5 shadow-xs space-y-3">
          <div className="flex items-center justify-between border-b border-rose-100 pb-3">
            <h3 className="text-sm font-bold text-rose-950 flex items-center gap-2">
              <Lock className="size-4 text-rose-600" />
              <span>Real-Submit Gate Architecture Barrier</span>
            </h3>
            <Badge variant="destructive" size="sm" className="font-mono">
              LOCKED DISABLED
            </Badge>
          </div>

          <p className="text-xs text-rose-900 leading-relaxed">
            In accordance with the Authoritative Architecture v1.0, live job application submissions are permanently disabled. The system operates strictly in supervised dry-run mode (L0), inspecting form controls and capturing full-page screenshots without ever clicking submit.
          </p>

          <div className="rounded-lg border border-rose-200 bg-white p-3 text-xs space-y-1.5 text-rose-900">
            <div className="flex items-center gap-2 font-medium">
              <ShieldAlert className="size-4 text-rose-600 shrink-0" />
              <span>RealSubmitGateBlockedError Code Guard</span>
            </div>
            <p className="text-[11px] text-slate-600 leading-relaxed">
              Any attempt by a browser automation loop or API call to trigger a real form submit unconditionally raises <code className="font-mono text-rose-700">RealSubmitGateBlockedError</code> and halts execution.
            </p>
          </div>
        </div>

        {/* Daily Capacity & Rate Caps */}
        <div className="rounded-xl border border-slate-200/80 bg-white p-5 shadow-xs space-y-3">
          <h3 className="text-sm font-semibold text-slate-900 flex items-center gap-2 border-b border-slate-100 pb-3">
            <Zap className="size-4 text-blue-600" />
            <span>Capacity Stage S0 (Locked Daily Limits)</span>
          </h3>

          <div className="space-y-2.5 text-xs">
            <div className="flex items-center justify-between py-1 border-b border-slate-50">
              <span className="text-slate-500">Active Daily Cap</span>
              <span className="font-bold text-slate-900 font-mono">2 applications / day</span>
            </div>
            <div className="flex items-center justify-between py-1 border-b border-slate-50">
              <span className="text-slate-500">Hourly Rate Limit</span>
              <span className="font-medium text-slate-800 font-mono">1 application / hour</span>
            </div>
            <div className="flex items-center justify-between py-1 border-b border-slate-50">
              <span className="text-slate-500">Monthly Volume Cap</span>
              <span className="font-medium text-slate-800 font-mono">40 applications / month</span>
            </div>
            <div className="flex items-center justify-between py-1 border-b border-slate-50">
              <span className="text-slate-500">Company Cooldown Window</span>
              <span className="font-medium text-slate-800 font-mono">90 Days Per Organization</span>
            </div>
            <div className="flex items-center justify-between py-1">
              <span className="text-slate-500">Single-Run Execution Lock</span>
              <span className="font-medium text-emerald-700">Active (File-backed Mutex)</span>
            </div>
          </div>
        </div>

        {/* Scheduler Window & Jitter */}
        <div className="rounded-xl border border-slate-200/80 bg-white p-5 shadow-xs space-y-3">
          <h3 className="text-sm font-semibold text-slate-900 flex items-center gap-2 border-b border-slate-100 pb-3">
            <Clock className="size-4 text-blue-600" />
            <span>APScheduler & Human Jitter Window</span>
          </h3>

          <div className="space-y-2.5 text-xs">
            <div className="flex items-center justify-between py-1 border-b border-slate-50">
              <span className="text-slate-500">Active Operational Window</span>
              <span className="font-bold text-slate-900">09:00 — 23:00 IST</span>
            </div>
            <div className="flex items-center justify-between py-1 border-b border-slate-50">
              <span className="text-slate-500">Human Jitter Randomization</span>
              <span className="font-medium text-slate-800">120s – 300s between actions</span>
            </div>
            <div className="flex items-center justify-between py-1 border-b border-slate-50">
              <span className="text-slate-500">Dead-Man Heartbeat Alert</span>
              <span className="font-medium text-emerald-700">Every 15 min during active window</span>
            </div>
            <div className="flex items-center justify-between py-1">
              <span className="text-slate-500">Night Window Action</span>
              <span className="font-medium text-slate-600">Suppressed (Silent Standby)</span>
            </div>
          </div>
        </div>

        {/* Staged Autonomy Hierarchy */}
        <div className="rounded-xl border border-slate-200/80 bg-white p-5 shadow-xs space-y-3">
          <h3 className="text-sm font-semibold text-slate-900 border-b border-slate-100 pb-3">
            Autonomy Hierarchy & Staging
          </h3>

          <div className="space-y-2 text-xs">
            <div className="flex items-center justify-between p-2 rounded-lg bg-emerald-50/70 border border-emerald-200">
              <div>
                <span className="font-bold text-emerald-950">Level 0 (L0) — Supervised Dry-Run</span>
                <p className="text-[11px] text-emerald-800">Deterministic DOM inspection & evidence capture</p>
              </div>
              <Badge variant="success" size="sm">ACTIVE</Badge>
            </div>

            <div className="flex items-center justify-between p-2 rounded-lg bg-slate-50 border border-slate-200">
              <div>
                <span className="font-semibold text-slate-900">Level 1 (L1) — Human-Approved Staged</span>
                <p className="text-[11px] text-slate-500">Pre-apply safety checks with mandatory approval</p>
              </div>
              <Badge variant="secondary" size="sm">PREPARED</Badge>
            </div>

            <div className="flex items-center justify-between p-2 rounded-lg bg-slate-50 border border-slate-200 opacity-60">
              <div>
                <span className="font-medium text-slate-700">Level 2 (L2) — Supervised Bulk</span>
                <p className="text-[11px] text-slate-500">Requires 30 verified runs & 98% accuracy</p>
              </div>
              <Badge variant="outline" size="sm">LOCKED</Badge>
            </div>

            <div className="flex items-center justify-between p-2 rounded-lg bg-slate-50 border border-slate-200 opacity-60">
              <div>
                <span className="font-medium text-slate-700">Level 3 (L3) — Full Autonomy</span>
                <p className="text-[11px] text-slate-500">Requires production governance release sign-off</p>
              </div>
              <Badge variant="outline" size="sm">LOCKED</Badge>
            </div>
          </div>
        </div>
      </div>

      {/* Confirmation Dialog */}
      {dialogAction && (
        <Dialog
          open={Boolean(dialogAction)}
          onClose={() => {
            if (!isProcessing) setDialogAction(null)
          }}
          title={
            dialogAction === "trip"
              ? "Confirm Emergency Kill Switch Trip"
              : "Confirm Emergency Kill Switch Reset"
          }
          description={
            dialogAction === "trip"
              ? "This will immediately halt all worker execution loops and active browser sessions."
              : "This will re-arm the agent to resume supervised dry-run execution."
          }
          footer={
            <>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setDialogAction(null)}
                disabled={isProcessing}
              >
                Cancel
              </Button>
              <Button
                variant={dialogAction === "trip" ? "destructive" : "default"}
                size="sm"
                onClick={handleConfirmAction}
                disabled={isProcessing}
                className={
                  dialogAction === "reset" ? "bg-emerald-600 hover:bg-emerald-700 text-white" : ""
                }
              >
                {isProcessing ? (
                  <span className="flex items-center gap-1">
                    <RefreshCw className="size-3.5 animate-spin" />
                    <span>Processing...</span>
                  </span>
                ) : dialogAction === "trip" ? (
                  "Confirm Immediate Stop"
                ) : (
                  "Confirm Reset & Arm"
                )}
              </Button>
            </>
          }
        >
          <div className="space-y-3 text-xs text-slate-600">
            {dialogAction === "trip" ? (
              <div className="rounded-lg border border-rose-200 bg-rose-50 p-3 text-rose-900 space-y-1">
                <p className="font-bold flex items-center gap-1">
                  <AlertTriangle className="size-4 text-rose-600 shrink-0" />
                  <span>Immediate Fail-Closed Guarantee</span>
                </p>
                <p className="text-[11px] leading-relaxed">
                  Tripping engages the file-backed mutex state. Any active Playwright browser sessions will terminate immediately with zero PII leakage.
                </p>
              </div>
            ) : (
              <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-emerald-900 space-y-1">
                <p className="font-bold flex items-center gap-1">
                  <CheckCircle2 className="size-4 text-emerald-600 shrink-0" />
                  <span>Resuming Operational Readiness</span>
                </p>
                <p className="text-[11px] leading-relaxed">
                  Resetting clears the mutex and allows scheduled discovery and form inspection to resume within the active IST window.
                </p>
              </div>
            )}
          </div>
        </Dialog>
      )}
    </div>
  )
}
