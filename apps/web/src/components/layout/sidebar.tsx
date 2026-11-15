"use client"

import * as React from "react"
import Link from "next/link"
import { usePathname } from "next/navigation"
import {
  LayoutDashboard,
  Briefcase,
  Send,
  CheckCircle2,
  HelpCircle,
  User,
  FileText,
  Radio,
  KeyRound,
  ShieldAlert,
  BarChart3,
  Settings,
  ChevronLeft,
  ChevronRight,
  ShieldCheck,
  Lock,
} from "lucide-react"
import { cn } from "@/lib/utils"

export interface NavItem {
  title: string
  href: string
  icon: React.ComponentType<{ className?: string }>
  badge?: string | number
  badgeVariant?: "blue" | "amber" | "green"
}

export const navigationItems: NavItem[] = [
  {
    title: "Overview",
    href: "/",
    icon: LayoutDashboard,
  },
  {
    title: "Job Queue",
    href: "/jobs",
    icon: Briefcase,
  },
  {
    title: "Applications",
    href: "/applications",
    icon: Send,
  },
  {
    title: "Approval Queue",
    href: "/approvals",
    icon: CheckCircle2,
  },
  {
    title: "Answer Bank",
    href: "/answer-bank",
    icon: HelpCircle,
  },
  {
    title: "My Profile",
    href: "/profile",
    icon: User,
  },
  {
    title: "Resumes",
    href: "/resumes",
    icon: FileText,
  },
  {
    title: "Providers",
    href: "/providers",
    icon: Radio,
  },
  {
    title: "Sessions",
    href: "/sessions",
    icon: KeyRound,
  },
  {
    title: "Automation",
    href: "/automation",
    icon: ShieldAlert,
  },
  {
    title: "Analytics",
    href: "/analytics",
    icon: BarChart3,
  },
  {
    title: "Settings",
    href: "/settings",
    icon: Settings,
  },
]

export interface SidebarProps {
  collapsed?: boolean
  onToggleCollapse?: () => void
  mobileOpen?: boolean
  onMobileClose?: () => void
}

export function Sidebar({
  collapsed = false,
  onToggleCollapse,
  mobileOpen = false,
  onMobileClose,
}: SidebarProps) {
  const pathname = usePathname()

  const sidebarContent = (
    <div className="flex h-full flex-col justify-between bg-white border-r border-slate-200">
      {/* Brand Header */}
      <div>
        <div className="flex h-16 items-center justify-between px-4 border-b border-slate-100">
          <Link
            href="/"
            className="flex items-center gap-2.5 font-bold tracking-tight text-slate-900 overflow-hidden"
          >
            <div className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-blue-600 text-white shadow-xs">
              <ShieldCheck className="size-5" />
            </div>
            {!collapsed && (
              <div className="flex flex-col">
                <span className="text-sm font-semibold tracking-tight text-slate-900 leading-tight">
                  JobAgent AI
                </span>
                <span className="text-[10px] font-medium text-slate-500 uppercase tracking-wider">
                  L0 Platform
                </span>
              </div>
            )}
          </Link>
          {onToggleCollapse && (
            <button
              onClick={onToggleCollapse}
              className="hidden lg:flex size-7 items-center justify-center rounded-md border border-slate-200 text-slate-500 hover:bg-slate-100 hover:text-slate-800 transition-colors"
              aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            >
              {collapsed ? (
                <ChevronRight className="size-3.5" />
              ) : (
                <ChevronLeft className="size-3.5" />
              )}
            </button>
          )}
        </div>

        {/* Navigation Items */}
        <nav aria-label="Main Navigation" className="space-y-0.5 px-2.5 py-3 overflow-y-auto max-h-[calc(100vh-180px)]">
          {navigationItems.map((item) => {
            const Icon = item.icon
            const isActive =
              item.href === "/"
                ? pathname === "/" || pathname === "/dashboard"
                : pathname.startsWith(item.href)

            return (
              <Link
                key={item.href}
                href={item.href}
                onClick={onMobileClose}
                className={cn(
                  "group flex items-center gap-3 rounded-lg px-3 py-2 text-xs font-medium transition-colors select-none",
                  isActive
                    ? "bg-blue-50 text-blue-700 font-semibold"
                    : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"
                )}
                title={collapsed ? item.title : undefined}
              >
                <Icon
                  className={cn(
                    "size-4 shrink-0 transition-colors",
                    isActive ? "text-blue-600" : "text-slate-400 group-hover:text-slate-600"
                  )}
                />
                {!collapsed && (
                  <span className="flex-1 truncate">{item.title}</span>
                )}
                {!collapsed && item.badge !== undefined && (
                  <span className="rounded-full bg-blue-100 px-1.5 py-0.2 text-[10px] font-semibold text-blue-700">
                    {item.badge}
                  </span>
                )}
              </Link>
            )
          })}
        </nav>
      </div>

      {/* Safety Status Banner at Bottom */}
      <div className="p-3 border-t border-slate-100 bg-slate-50/60">
        {!collapsed ? (
          <div className="rounded-lg border border-amber-200/80 bg-amber-50/80 p-2.5">
            <div className="flex items-center gap-1.5 text-amber-900 font-semibold text-xs">
              <Lock className="size-3.5 text-amber-700" />
              <span>L0 Dry-Run Guard</span>
            </div>
            <p className="mt-1 text-[11px] text-amber-800 leading-tight">
              Real submissions locked. Cap: 2 apps/day.
            </p>
          </div>
        ) : (
          <div
            className="flex justify-center text-amber-700"
            title="L0 Dry-Run Guard Active (Submissions Locked)"
          >
            <Lock className="size-4" />
          </div>
        )}
      </div>
    </div>
  )

  return (
    <>
      {/* Desktop Persistent Sidebar */}
      <aside
        className={cn(
          "hidden lg:flex flex-col shrink-0 transition-all duration-200 z-30",
          collapsed ? "w-16" : "w-60"
        )}
      >
        {sidebarContent}
      </aside>

      {/* Mobile Backdrop & Drawer */}
      {mobileOpen && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <div
            onClick={onMobileClose}
            className="fixed inset-0 bg-slate-900/40 backdrop-blur-xs transition-opacity"
          />
          <div className="fixed inset-y-0 left-0 z-50 w-64 bg-white shadow-xl animate-in slide-in-from-left">
            {sidebarContent}
          </div>
        </div>
      )}
    </>
  )
}
