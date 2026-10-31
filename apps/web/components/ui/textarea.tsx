import * as React from "react"
import { cn } from "@/lib/utils"

function Textarea({ className, ...props }: React.ComponentProps<"textarea">) {
  return (
    <textarea
      data-slot="textarea"
      className={cn(
        "flex field-sizing-content min-h-20 w-full rounded-md border border-input bg-card px-3 py-2 text-base text-foreground transition-colors duration-100 outline-none placeholder:text-text-placeholder hover:border-input-hover focus-visible:border-ring focus-visible:shadow-[0_0_0_1px_var(--ring)] focus-visible:outline-none aria-invalid:border-tone-danger-fg disabled:cursor-not-allowed disabled:border-border disabled:bg-surface-disabled disabled:text-text-disabled sm:text-body",
        className
      )}
      {...props}
    />
  )
}

export { Textarea }
