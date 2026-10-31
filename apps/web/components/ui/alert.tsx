import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/lib/utils"

// COMPONENT_INVENTORY §4: tones info / success / warning / danger / neutral, 20 px icon.
// `role="alert"` only for danger alerts shown in response to a user action; status otherwise.
const alertVariants = cva(
  "relative grid w-full grid-cols-[0_1fr] items-start gap-y-0.5 rounded-lg border px-4 py-3 text-body has-[>svg]:grid-cols-[20px_1fr] has-[>svg]:gap-x-3 [&>svg]:size-5 [&>svg]:text-current",
  {
    variants: {
      tone: {
        neutral: "border-tone-neutral-border bg-tone-neutral-bg text-tone-neutral-fg",
        info: "border-tone-info-border bg-tone-info-bg text-tone-info-fg",
        success: "border-tone-success-border bg-tone-success-bg text-tone-success-fg",
        warning: "border-tone-warning-border bg-tone-warning-bg text-tone-warning-fg",
        danger: "border-tone-danger-border bg-tone-danger-bg text-tone-danger-fg",
      },
    },
    defaultVariants: {
      tone: "neutral",
    },
  }
)

function Alert({
  className,
  tone,
  role,
  ...props
}: React.ComponentProps<"div"> & VariantProps<typeof alertVariants>) {
  return (
    <div
      data-slot="alert"
      role={role ?? "status"}
      className={cn(alertVariants({ tone }), className)}
      {...props}
    />
  )
}

function AlertTitle({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="alert-title"
      className={cn("col-start-2 text-body-strong", className)}
      {...props}
    />
  )
}

function AlertDescription({
  className,
  ...props
}: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="alert-description"
      className={cn("col-start-2 grid justify-items-start gap-1 text-body", className)}
      {...props}
    />
  )
}

export { Alert, AlertTitle, AlertDescription }
