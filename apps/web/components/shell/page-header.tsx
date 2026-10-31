import { cn } from "@/lib/utils";

type PageHeaderProps = {
  title: string;
  subtitle?: React.ReactNode;
  meta?: React.ReactNode;
  actions?: React.ReactNode;
  className?: string;
};

/**
 * The page `h1` plus optional subtitle, meta line and actions (COMPONENT_INVENTORY C-29).
 * The title renders immediately, even while data loads. The shell moves focus to it after
 * client-side navigation, hence `tabIndex={-1}`.
 */
export function PageHeader({ title, subtitle, meta, actions, className }: PageHeaderProps) {
  return (
    <div className={cn("flex flex-col gap-3 md:flex-row md:items-start md:justify-between", className)}>
      <div className="flex min-w-0 flex-col gap-1">
        <h1 tabIndex={-1} className="text-title-lg outline-none">
          {title}
        </h1>
        {subtitle ? <p className="text-body text-muted-foreground">{subtitle}</p> : null}
        {meta ? <div className="text-sm text-muted-foreground">{meta}</div> : null}
      </div>
      {actions ? <div className="flex flex-wrap items-center gap-2">{actions}</div> : null}
    </div>
  );
}
