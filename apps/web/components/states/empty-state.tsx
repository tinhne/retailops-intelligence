import type { LucideIcon } from "lucide-react";

import { cn } from "@/lib/utils";

type EmptyStateProps = {
  icon: LucideIcon;
  title: string;
  description?: React.ReactNode;
  /** Only pass an action the person is allowed to take (SCREEN_SPECIFICATIONS §0.3). */
  action?: React.ReactNode;
  variant?: "empty" | "success";
  size?: "page" | "section";
  className?: string;
};

/** "Nothing here yet" and "all clear" states (COMPONENT_INVENTORY C-34). */
export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
  variant = "empty",
  size = "section",
  className,
}: EmptyStateProps) {
  const Heading = size === "page" ? "h2" : "h3";
  return (
    <div className={cn("flex flex-col items-center gap-2 text-center", size === "page" ? "py-16" : "py-8", className)}>
      <span
        className={cn(
          "flex size-10 items-center justify-center rounded-full",
          variant === "success" ? "bg-tone-success-bg text-tone-success-fg" : "bg-muted text-muted-foreground",
        )}
      >
        <Icon aria-hidden className="size-6" />
      </span>
      <Heading className="text-title-sm">{title}</Heading>
      {description ? <p className="max-w-md text-body text-muted-foreground">{description}</p> : null}
      {action ? <div className="mt-2 flex flex-wrap justify-center gap-2">{action}</div> : null}
    </div>
  );
}
