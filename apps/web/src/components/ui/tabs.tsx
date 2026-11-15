import * as React from "react"
import { cn } from "@/lib/utils"

export interface TabItem {
  id: string
  label: string
  count?: number
  icon?: React.ComponentType<{ className?: string }>
}

export interface TabsProps {
  tabs: TabItem[]
  activeTab: string
  onChange: (tabId: string) => void
  className?: string
}

export function Tabs({ tabs, activeTab, onChange, className }: TabsProps) {
  return (
    <div
      role="tablist"
      aria-orientation="horizontal"
      className={cn(
        "flex items-center gap-1 border-b border-slate-200 overflow-x-auto no-scrollbar",
        className
      )}
    >
      {tabs.map((tab) => {
        const isActive = tab.id === activeTab
        const Icon = tab.icon
        return (
          <button
            key={tab.id}
            role="tab"
            aria-selected={isActive}
            aria-controls={`panel-${tab.id}`}
            id={`tab-${tab.id}`}
            onClick={() => onChange(tab.id)}
            className={cn(
              "group inline-flex items-center gap-2 border-b-2 px-3.5 py-2.5 text-sm font-medium transition-all shrink-0 select-none",
              isActive
                ? "border-blue-600 text-blue-600"
                : "border-transparent text-slate-500 hover:border-slate-300 hover:text-slate-800"
            )}
          >
            {Icon && (
              <Icon
                className={cn(
                  "size-4 transition-colors",
                  isActive ? "text-blue-600" : "text-slate-400 group-hover:text-slate-600"
                )}
              />
            )}
            <span>{tab.label}</span>
            {tab.count !== undefined && (
              <span
                className={cn(
                  "rounded-full px-2 py-0.5 text-[11px] font-semibold",
                  isActive
                    ? "bg-blue-100 text-blue-700"
                    : "bg-slate-100 text-slate-600 group-hover:bg-slate-200"
                )}
              >
                {tab.count}
              </span>
            )}
          </button>
        )
      })}
    </div>
  )
}
