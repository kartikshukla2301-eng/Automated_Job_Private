import * as React from "react"
import { type LucideIcon } from "lucide-react"
import { cn } from "@/lib/utils"

export interface StatCardProps {
  title: string
  value: string | number
  subtitle?: string
  icon?: LucideIcon
  trend?: {
    value: string
    isPositive?: boolean
    neutral?: boolean
  }
  badge?: string
  className?: string
  onClick?: () => void
}

export function StatCard({
  title,
  value,
  subtitle,
  icon: Icon,
  trend,
  badge,
  className,
  onClick,
}: StatCardProps) {
  return (
    <div
      onClick={onClick}
      className={cn(
        "relative rounded-xl border border-slate-200/80 bg-white p-5 shadow-xs transition-all hover:shadow-sm",
        onClick && "cursor-pointer hover:border-slate-300",
        className
      )}
    >
      <div className="flex items-center justify-between gap-2">
        <p className="text-xs font-medium tracking-wider uppercase text-slate-500">
          {title}
        </p>
        {Icon && (
          <div className="flex size-9 items-center justify-center rounded-lg bg-slate-50 text-slate-600 border border-slate-100">
            <Icon className="size-4" />
          </div>
        )}
      </div>

      <div className="mt-2 flex items-baseline gap-2">
        <span className="text-2xl font-bold tracking-tight text-slate-900">
          {value}
        </span>
        {badge && (
          <span className="rounded-full bg-blue-50 px-2 py-0.5 text-xs font-medium text-blue-700 border border-blue-200">
            {badge}
          </span>
        )}
      </div>

      {(subtitle || trend) && (
        <div className="mt-2 flex items-center gap-2 text-xs text-slate-500">
          {trend && (
            <span
              className={cn(
                "font-semibold",
                trend.neutral
                  ? "text-slate-600"
                  : trend.isPositive
                  ? "text-emerald-600"
                  : "text-red-600"
              )}
            >
              {trend.value}
            </span>
          )}
          {subtitle && <span>{subtitle}</span>}
        </div>
      )}
    </div>
  )
}
