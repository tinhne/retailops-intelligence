import * as React from "react"

import { cn } from "@/lib/utils"

// DESIGN_SYSTEM §9–§10: 3:1 border, 2 px focus border without offset, danger border when invalid.
// 40 px / 16 px text below 640 px so iOS Safari does not zoom on focus.
function Input({ className, type, ...props }: React.ComponentProps<"input">) {
  return (
    <input
      type={type}
      data-slot="input"
      className={cn(
        "h-10 w-full min-w-0 rounded-md border border-input bg-card px-3 text-base text-foreground transition-colors duration-100 outline-none placeholder:text-text-placeholder hover:border-input-hover sm:h-8 sm:text-body",
        "focus-visible:border-ring focus-visible:shadow-[0_0_0_1px_var(--ring)] focus-visible:outline-none",
        "aria-invalid:border-tone-danger-fg aria-invalid:focus-visible:shadow-[0_0_0_1px_var(--tone-danger-fg)]",
        "disabled:cursor-not-allowed disabled:border-border disabled:bg-surface-disabled disabled:text-text-disabled",
        className
      )}
      {...props}
    />
  )
}

export { Input }
