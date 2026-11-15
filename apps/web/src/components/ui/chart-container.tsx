import * as React from "react"
import { cn } from "@/lib/utils"

export interface ChartContainerProps {
  title: string
  description?: string
  action?: React.ReactNode
  children: React.ReactNode
  className?: string
  height?: number | string
}

export function ChartContainer({
  title,
  description,
  action,
  children,
  className,
  height = 300,
}: ChartContainerProps) {
  return (
    <div
      className={cn(
        "rounded-xl border border-slate-200/80 bg-white p-5 shadow-xs transition-shadow hover:shadow-sm",
        className
      )}
    >
      <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between mb-4">
        <div>
          <h3 className="text-sm font-semibold text-slate-900">{title}</h3>
          {description && (
            <p className="text-xs text-slate-500 mt-0.5">{description}</p>
          )}
        </div>
        {action && <div>{action}</div>}
      </div>
      <div style={{ height }} className="w-full">
        {children}
      </div>
    </div>
  )
}
