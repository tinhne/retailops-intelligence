/** A titled card section on detail pages (S-04, S-06, S-08, S-12). */
export function Section({ id, title, children, aside }: { id: string; title: string; children: React.ReactNode; aside?: React.ReactNode }) {
  return (
    <section aria-labelledby={`${id}-title`} className="rounded-lg border bg-card p-4 md:p-5">
      <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
        <h2 id={`${id}-title`} className="text-title-sm">
          {title}
        </h2>
        {aside}
      </div>
      {children}
    </section>
  );
}

/** One labelled figure in a row of tiles (COMPONENT_INVENTORY StatTile). */
export function StatTile({ label, children, hint }: { label: string; children: React.ReactNode; hint?: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-1 rounded-md border p-3">
      <span className="text-xs text-muted-foreground">{label}</span>
      <span className="text-title tabular-nums">{children}</span>
      {hint ? <span className="text-xs font-normal text-muted-foreground">{hint}</span> : null}
    </div>
  );
}
