import * as React from "react"
import { AlertTriangle, RefreshCw } from "lucide-react"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"

export interface ErrorStateProps {
  title?: string
  message: string
  onRetry?: () => void
  retryText?: string
  className?: string
}

export function ErrorState({
  title = "Connection or Data Error",
  message,
  onRetry,
  retryText = "Try Again",
  className,
}: ErrorStateProps) {
  return (
    <div
      className={cn(
        "flex min-h-[220px] flex-col items-center justify-center rounded-xl border border-red-200 bg-red-50/50 p-6 text-center",
        className
      )}
    >
      <div className="flex size-10 items-center justify-center rounded-full bg-red-100 text-red-600 border border-red-200">
        <AlertTriangle className="size-5" />
      </div>
      <h3 className="mt-3 text-sm font-semibold text-red-900">{title}</h3>
      <p className="mt-1 max-w-md text-xs text-red-700 leading-relaxed">
        {message}
      </p>
      {onRetry && (
        <Button
          onClick={onRetry}
          variant="outline"
          size="sm"
          className="mt-4 border-red-300 bg-white text-red-800 hover:bg-red-50 hover:text-red-900 gap-1.5"
        >
          <RefreshCw className="size-3.5" />
          {retryText}
        </Button>
      )}
    </div>
  )
}
