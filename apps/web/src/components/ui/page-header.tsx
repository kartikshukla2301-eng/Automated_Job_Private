import * as React from "react"
import Link from "next/link"
import { ChevronRight } from "lucide-react"
import { cn } from "@/lib/utils"

export interface BreadcrumbItem {
  label: string
  href?: string
}

export interface PageHeaderProps {
  title: string
  description?: string
  breadcrumbs?: BreadcrumbItem[]
  badge?: React.ReactNode
  actions?: React.ReactNode
  className?: string
}

export function PageHeader({
  title,
  description,
  breadcrumbs,
  badge,
  actions,
  className,
}: PageHeaderProps) {
  return (
    <div className={cn("mb-6 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between", className)}>
      <div className="space-y-1">
        {breadcrumbs && breadcrumbs.length > 0 && (
          <nav aria-label="Breadcrumb" className="flex items-center gap-1.5 text-xs text-slate-500 mb-1">
            {breadcrumbs.map((item, index) => {
              const isLast = index === breadcrumbs.length - 1
              return (
                <React.Fragment key={index}>
                  {item.href && !isLast ? (
                    <Link
                      href={item.href}
                      className="hover:text-slate-900 transition-colors"
                    >
                      {item.label}
                    </Link>
                  ) : (
                    <span className={cn(isLast && "font-medium text-slate-700")}>
                      {item.label}
                    </span>
                  )}
                  {!isLast && <ChevronRight className="size-3 text-slate-400" />}
                </React.Fragment>
              )
            })}
          </nav>
        )}
        <div className="flex items-center gap-2.5 flex-wrap">
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">
            {title}
          </h1>
          {badge}
        </div>
        {description && (
          <p className="text-sm text-slate-500 max-w-3xl leading-relaxed">
            {description}
          </p>
        )}
      </div>

      {actions && (
        <div className="flex items-center gap-2.5 shrink-0 pt-1 sm:pt-0">
          {actions}
        </div>
      )}
    </div>
  )
}
