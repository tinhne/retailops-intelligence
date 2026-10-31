import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { Loader2Icon } from "lucide-react"
import { Slot } from "radix-ui"

import { cn } from "@/lib/utils"

// DESIGN_SYSTEM §10 and COMPONENT_INVENTORY §4. `aria-disabled` keeps permission-disabled
// buttons focusable (so their reason is reachable); `disabled` is reserved for in-flight submits.
const buttonVariants = cva(
  "relative inline-flex shrink-0 items-center justify-center gap-2 rounded-md text-body-strong whitespace-nowrap transition-colors duration-100 outline-none focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring disabled:pointer-events-none aria-disabled:cursor-not-allowed [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-4",
  {
    variants: {
      variant: {
        primary:
          "bg-primary text-primary-foreground hover:bg-primary-hover active:bg-primary-active disabled:border disabled:border-border disabled:bg-surface-disabled disabled:text-text-disabled aria-disabled:border aria-disabled:border-border aria-disabled:bg-surface-disabled aria-disabled:text-text-disabled",
        secondary:
          "border border-input bg-card text-foreground hover:bg-accent active:border-input-hover active:bg-muted disabled:border-border disabled:bg-surface-disabled disabled:text-text-disabled aria-disabled:border-border aria-disabled:bg-surface-disabled aria-disabled:text-text-disabled",
        ghost:
          "text-text-secondary hover:bg-accent hover:text-foreground active:bg-muted disabled:text-text-disabled aria-disabled:bg-transparent aria-disabled:text-text-disabled",
        destructive:
          "bg-destructive text-destructive-foreground hover:bg-destructive-hover active:bg-destructive-hover disabled:border disabled:border-border disabled:bg-surface-disabled disabled:text-text-disabled aria-disabled:border aria-disabled:border-border aria-disabled:bg-surface-disabled aria-disabled:text-text-disabled",
        link: "h-auto px-0 text-link hover:underline active:text-primary-active",
      },
      size: {
        sm: "h-7 gap-1.5 px-2.5",
        md: "h-8 px-3",
        lg: "h-10 px-4",
        icon: "size-8",
        "icon-sm": "size-7",
      },
    },
    defaultVariants: {
      variant: "primary",
      size: "md",
    },
  }
)

type ButtonProps = React.ComponentProps<"button"> &
  VariantProps<typeof buttonVariants> & {
    asChild?: boolean
    /** Shows a spinner and `pendingLabel`, locks the width and ignores clicks. */
    pending?: boolean
    pendingLabel?: string
  }

function Button({
  className,
  variant = "primary",
  size = "md",
  asChild = false,
  pending = false,
  pendingLabel,
  children,
  onClick,
  ...props
}: ButtonProps) {
  const Comp = asChild ? Slot.Root : "button"
  const ariaDisabled = props["aria-disabled"] === true || props["aria-disabled"] === "true"
  // Only swap the handler when a click must be ignored, so server components can render
  // `<Button asChild><Link/></Button>` without passing a function across the boundary.
  const handleClick =
    pending || ariaDisabled
      ? (event: React.MouseEvent<HTMLButtonElement>) => event.preventDefault()
      : onClick

  return (
    <Comp
      data-slot="button"
      data-variant={variant}
      data-size={size}
      aria-busy={pending || undefined}
      className={cn(buttonVariants({ variant, size, className }))}
      onClick={handleClick}
      {...props}
    >
      {pending && !asChild ? (
        <>
          <Loader2Icon aria-hidden className="motion-essential animate-spin" />
          {pendingLabel ?? children}
        </>
      ) : (
        children
      )}
    </Comp>
  )
}

export { Button, buttonVariants }
export type { ButtonProps }
