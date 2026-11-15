"use client"

import * as React from "react"
import { Save, ShieldCheck, Database, Bell } from "lucide-react"
import { Button } from "@/components/ui/button"
import { PageHeader } from "@/components/ui/page-header"
import { Input } from "@/components/ui/input"

export default function SettingsPage() {
  return (
    <div className="space-y-6">
      <PageHeader
        title="Settings & Platform Configuration"
        description="Local runtime parameters, API connectivity, and operational boundaries."
        breadcrumbs={[
          { label: "Overview", href: "/" },
          { label: "Settings" },
        ]}
      />

      <div className="grid grid-cols-1 gap-6 max-w-4xl">
        {/* Backend Connectivity */}
        <div className="rounded-xl border border-slate-200/80 bg-white p-5 shadow-xs space-y-4">
          <h3 className="text-sm font-semibold text-slate-900 flex items-center gap-2">
            <Database className="size-4 text-slate-400" />
            <span>Backend API Connection</span>
          </h3>

          <div className="space-y-3 text-xs">
            <div>
              <label className="text-slate-600 font-medium block mb-1">
                FastAPI Base URL:
              </label>
              <Input defaultValue="http://127.0.0.1:8000" className="max-w-md font-mono" />
            </div>

            <div className="flex items-center gap-2 pt-1 text-emerald-700">
              <ShieldCheck className="size-4 text-emerald-600" />
              <span>Connected to local backend (Status: Healthy)</span>
            </div>
          </div>
        </div>

        {/* Telegram Notifications */}
        <div className="rounded-xl border border-slate-200/80 bg-white p-5 shadow-xs space-y-4">
          <h3 className="text-sm font-semibold text-slate-900 flex items-center gap-2">
            <Bell className="size-4 text-slate-400" />
            <span>Telegram Bot Notifications</span>
          </h3>

          <div className="space-y-3 text-xs">
            <p className="text-slate-500">
              Alert owner of queued approvals, needs-user-input questions, and emergency kill-switch events.
            </p>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <div>
                <label className="text-slate-600 font-medium block mb-1">
                  Telegram Bot Token:
                </label>
                <Input type="password" placeholder="Configured via .env" disabled className="bg-slate-50 font-mono" />
              </div>
              <div>
                <label className="text-slate-600 font-medium block mb-1">
                  Allowed Chat IDs:
                </label>
                <Input placeholder="Configured via .env" disabled className="bg-slate-50 font-mono" />
              </div>
            </div>
          </div>
        </div>

        {/* Save button */}
        <div>
          <Button variant="default" size="sm" className="gap-1.5 bg-blue-600 hover:bg-blue-700">
            <Save className="size-4" />
            <span>Save Settings</span>
          </Button>
        </div>
      </div>
    </div>
  )
}
