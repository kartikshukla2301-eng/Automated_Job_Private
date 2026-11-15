"use client"

import * as React from "react"
import { Sidebar } from "./sidebar"
import { Header } from "./header"

export interface AppLayoutProps {
  children: React.ReactNode
}

export function AppLayout({ children }: AppLayoutProps) {
  const [collapsed, setCollapsed] = React.useState(false)
  const [mobileOpen, setMobileOpen] = React.useState(false)

  return (
    <div className="flex h-screen w-full overflow-hidden bg-slate-50 font-sans text-slate-900 antialiased">
      {/* Sidebar Navigation */}
      <React.Suspense fallback={<div className="w-64 shrink-0 bg-white border-r border-slate-200" />}>
        <Sidebar
          collapsed={collapsed}
          onToggleCollapse={() => setCollapsed(!collapsed)}
          mobileOpen={mobileOpen}
          onMobileClose={() => setMobileOpen(false)}
        />
      </React.Suspense>

      {/* Main Content Area */}
      <div className="flex flex-1 flex-col overflow-hidden">
        <Header onOpenMobile={() => setMobileOpen(true)} />

        <main className="flex-1 overflow-y-auto px-4 py-6 sm:px-8">
          <div className="mx-auto max-w-7xl">
            {children}
          </div>
        </main>
      </div>
    </div>
  )
}
