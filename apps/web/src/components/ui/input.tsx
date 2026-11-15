import * as React from "react"
import { Search, X } from "lucide-react"
import { cn } from "@/lib/utils"

export interface InputProps
  extends React.InputHTMLAttributes<HTMLInputElement> {
  error?: boolean
}

const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ className, type, error, ...props }, ref) => {
    return (
      <input
        type={type}
        className={cn(
          "flex h-9 w-full rounded-md border border-slate-200 bg-white px-3 py-1 text-sm text-slate-900 shadow-xs transition-colors file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-slate-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-600/20 focus-visible:border-blue-600 disabled:cursor-not-allowed disabled:opacity-50",
          error && "border-red-500 focus-visible:ring-red-500/20 focus-visible:border-red-500",
          className
        )}
        ref={ref}
        {...props}
      />
    )
  }
)
Input.displayName = "Input"

export interface SearchInputProps extends Omit<InputProps, "type"> {
  onClear?: () => void
}

const SearchInput = React.forwardRef<HTMLInputElement, SearchInputProps>(
  ({ className, value, onClear, onChange, ...props }, ref) => {
    return (
      <div className="relative flex items-center w-full">
        <Search className="absolute left-2.5 size-4 text-slate-400 pointer-events-none" />
        <Input
          type="text"
          className={cn("pl-8 pr-8", className)}
          value={value}
          onChange={onChange}
          ref={ref}
          {...props}
        />
        {value && onClear && (
          <button
            type="button"
            onClick={onClear}
            className="absolute right-2.5 text-slate-400 hover:text-slate-600 p-0.5 rounded-full"
            aria-label="Clear search"
          >
            <X className="size-3.5" />
          </button>
        )}
      </div>
    )
  }
)
SearchInput.displayName = "SearchInput"

export { Input, SearchInput }
