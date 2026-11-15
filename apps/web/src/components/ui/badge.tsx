import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "@/lib/utils"

const badgeVariants = cva(
  "inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2",
  {
    variants: {
      variant: {
        default:
          "border border-slate-200 bg-slate-100 text-slate-800 hover:bg-slate-200/80",
        secondary:
          "border border-slate-100 bg-slate-50 text-slate-600 hover:bg-slate-100",
        destructive:
          "border border-red-200 bg-red-50 text-red-700 hover:bg-red-100",
        success:
          "border border-emerald-200 bg-emerald-50 text-emerald-700 hover:bg-emerald-100",
        warning:
          "border border-amber-200 bg-amber-50 text-amber-800 hover:bg-amber-100",
        info:
          "border border-blue-200 bg-blue-50 text-blue-700 hover:bg-blue-100",
        indigo:
          "border border-indigo-200 bg-indigo-50 text-indigo-700 hover:bg-indigo-100",
        outline:
          "border border-slate-300 text-slate-700 hover:bg-slate-50",
      },
      size: {
        default: "text-xs px-2.5 py-0.5",
        sm: "text-[11px] px-2 py-0.2",
        lg: "text-sm px-3 py-1",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
)

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, size, ...props }: BadgeProps) {
  return (
    <div className={cn(badgeVariants({ variant, size }), className)} {...props} />
  )
}

export { Badge, badgeVariants }
