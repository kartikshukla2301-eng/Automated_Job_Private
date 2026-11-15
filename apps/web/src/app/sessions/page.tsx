"use client"

import * as React from "react"
import { KeyRound, RefreshCw, Lock } from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { PageHeader } from "@/components/ui/page-header"

export default function SessionsPage() {
  return (
    <div className="space-y-6">
      <PageHeader
        title="Browser Sessions & Authentication"
        description="Isolated browser session states for platforms requiring manual authentication. Password storage is strictly prohibited."
        breadcrumbs={[
          { label: "Overview", href: "/" },
          { label: "Sessions" },
        ]}
      />

      <div className="rounded-xl border border-amber-200/80 bg-amber-50/80 p-4 text-xs text-amber-900 space-y-1">
        <div className="flex items-center gap-1.5 font-bold">
          <Lock className="size-4 text-amber-700" />
          <span>Strict Security Protocol</span>
        </div>
        <p className="leading-relaxed">
          The agent exclusively consumes temporary browser session cookies stored in isolated JSON files.
          Plaintext credentials, passwords, and 2FA secrets are strictly rejected and never saved.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-5 md:grid-cols-3">
        {[
          {
            platform: "Naukri",
            stateFile: "worker/sessions/naukri_storage_state.json",
            status: "AUTHENTICATED",
            statusVariant: "success" as const,
            expiresIn: "12 days remaining",
            lastUsed: "3 hours ago",
          },
          {
            platform: "Wellfound",
            stateFile: "worker/sessions/wellfound_storage_state.json",
            status: "AUTHENTICATED",
            statusVariant: "success" as const,
            expiresIn: "8 days remaining",
            lastUsed: "5 hours ago",
          },
          {
            platform: "LinkedIn",
            stateFile: "worker/sessions/linkedin_storage_state.json",
            status: "AUTHENTICATED",
            statusVariant: "success" as const,
            expiresIn: "6 days remaining",
            lastUsed: "Yesterday",
          },
        ].map((s) => (
          <div
            key={s.platform}
            className="rounded-xl border border-slate-200/80 bg-white p-5 shadow-xs space-y-4"
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <div className="flex size-8 items-center justify-center rounded-lg bg-slate-100 text-slate-700">
                  <KeyRound className="size-4" />
                </div>
                <div>
                  <h3 className="text-sm font-semibold text-slate-900">
                    {s.platform}
                  </h3>
                  <span className="text-[10px] text-slate-400">Playwright Session</span>
                </div>
              </div>
              <Badge variant={s.statusVariant} size="sm">
                {s.status}
              </Badge>
            </div>

            <div className="space-y-1.5 text-xs text-slate-600 border-t border-slate-100 pt-3">
              <div>
                <span className="text-slate-400 text-[11px]">Storage State File:</span>
                <p className="font-mono text-[10px] text-slate-700 truncate mt-0.5">
                  {s.stateFile}
                </p>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">TTL Freshness:</span>
                <span className="font-medium text-slate-800">{s.expiresIn}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Last Verified:</span>
                <span className="text-slate-700">{s.lastUsed}</span>
              </div>
            </div>

            <div className="pt-2 border-t border-slate-100">
              <Button variant="outline" size="xs" className="w-full gap-1">
                <RefreshCw className="size-3" />
                <span>Re-Authenticate Session</span>
              </Button>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
