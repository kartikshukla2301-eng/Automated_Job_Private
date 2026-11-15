"use client"

import * as React from "react"
import {
  Menu,
  Bell,
  Search,
  ShieldCheck,
  ShieldAlert,
  Lock,
  User,
} from "lucide-react"
import { Badge } from "@/components/ui/badge"

export interface HeaderProps {
  onOpenMobile?: () => void
  userEmail?: string
  killSwitchActive?: boolean
}

export function Header({
  onOpenMobile,
  userEmail = "candidate@devleveler.local",
  killSwitchActive = false,
}: HeaderProps) {
  const [searchQuery, setSearchQuery] = React.useState("")

  return (
    <header className="sticky top-0 z-20 flex h-16 w-full items-center justify-between border-b border-slate-200 bg-white/95 px-4 backdrop-blur-xs sm:px-6">
      {/* Left Area: Mobile Menu & Search */}
      <div className="flex items-center gap-3 flex-1 max-w-md">
        <button
          onClick={onOpenMobile}
          className="lg:hidden flex size-9 items-center justify-center rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-100"
          aria-label="Open navigation menu"
        >
          <Menu className="size-5" />
        </button>

        <div className="relative w-full hidden sm:block">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 size-4 text-slate-400 pointer-events-none" />
          <input
            type="text"
            placeholder="Search jobs, companies, applications..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="h-9 w-full rounded-lg border border-slate-200 bg-slate-50/80 pl-8 pr-3 text-xs text-slate-800 placeholder:text-slate-400 focus:bg-white focus:outline-none focus:ring-2 focus:ring-blue-600/20 focus:border-blue-600 transition-colors"
          />
        </div>
      </div>

      {/* Right Area: Status Badges, Notifications & Profile */}
      <div className="flex items-center gap-2.5 sm:gap-3">
        {/* Safety Gate Status */}
        <div className="hidden md:flex items-center gap-2">
          <Badge variant="warning" size="sm" className="gap-1 font-semibold">
            <Lock className="size-3 text-amber-700" />
            <span>REAL SUBMISSION LOCKED</span>
          </Badge>

          {killSwitchActive ? (
            <Badge variant="destructive" size="sm" className="gap-1 font-semibold animate-pulse">
              <ShieldAlert className="size-3" />
              <span>KILL SWITCH ACTIVE</span>
            </Badge>
          ) : (
            <Badge variant="success" size="sm" className="gap-1">
              <ShieldCheck className="size-3 text-emerald-600" />
              <span>Kill Switch Normal</span>
            </Badge>
          )}

          <Badge variant="default" size="sm" className="text-slate-600">
            Cap: 2/day
          </Badge>
        </div>

        {/* Notifications Icon */}
        <button
          className="relative flex size-9 items-center justify-center rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-50 transition-colors"
          aria-label="Notifications"
          title="Operational notifications"
        >
          <Bell className="size-4" />
          <span className="absolute top-1.5 right-1.5 size-2 rounded-full bg-blue-600 ring-2 ring-white" />
        </button>

        {/* User Profile Capsule */}
        <div className="flex items-center gap-2 rounded-lg border border-slate-200 bg-slate-50/80 p-1 pl-2.5">
          <div className="flex flex-col text-right hidden xl:block">
            <span className="text-xs font-semibold text-slate-900 leading-tight">
              Candidate Owner
            </span>
            <span className="text-[10px] text-slate-500 max-w-[140px] truncate">
              {userEmail}
            </span>
          </div>
          <div className="flex size-7 items-center justify-center rounded-md bg-blue-600 text-white font-medium text-xs">
            <User className="size-4" />
          </div>
        </div>
      </div>
    </header>
  )
}
