import * as React from "react"
import { type LucideIcon } from "lucide-react"
import { cn } from "@/lib/utils"

export interface EmptyStateProps {
  icon?: LucideIcon
  title: string
  description?: string
  action?: React.ReactNode
  className?: string
}

export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
  className,
}: EmptyStateProps) {
  return (
    <div
      className={cn(
        "flex min-h-[260px] flex-col items-center justify-center rounded-xl border border-dashed border-slate-300 bg-white p-8 text-center",
        className
      )}
    >
      {Icon && (
        <div className="mx-auto flex size-12 items-center justify-center rounded-xl bg-slate-100 text-slate-500 border border-slate-200">
          <Icon className="size-6" />
        </div>
      )}
      <h3 className="mt-4 text-base font-semibold text-slate-900">{title}</h3>
      {description && (
        <p className="mt-1.5 max-w-sm text-sm text-slate-500">{description}</p>
      )}
      {action && <div className="mt-5">{action}</div>}
    </div>
  )
}
