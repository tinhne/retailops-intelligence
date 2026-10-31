import { cn } from "@/lib/utils"

// `--muted` fill with a 2 s opacity pulse (DESIGN_SYSTEM §7); static under reduced motion.
function Skeleton({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="skeleton"
      aria-hidden
      className={cn("animate-skeleton rounded-md bg-muted", className)}
      {...props}
    />
  )
}

export { Skeleton }
