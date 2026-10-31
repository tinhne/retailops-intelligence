"use client";

import { CircleAlert } from "lucide-react";
import { useId, useState } from "react";

import { Input } from "@/components/ui/input";
import { rangeError } from "@/lib/date-range";

/**
 * A custom range of store-local days next to a preset select (C-31 "date-range"). Edits are
 * written to the URL only when the range is usable, so a reversed range shows its validation
 * message (S-05) and never reaches the API.
 */
export function DateRangeFilter({
  label,
  from,
  to,
  zone,
  onChange,
}: {
  /** The filter's name, e.g. "Placed": the inputs read "Placed from" and "Placed to". */
  label: string;
  from: string | null;
  to: string | null;
  /** Generic zone name ("ET"): the days are store-local, not the browser's. */
  zone: string;
  onChange: (from: string | null, to: string | null) => void;
}) {
  const id = useId();
  const [draft, setDraft] = useState({ from: from ?? "", to: to ?? "" });
  const [synced, setSynced] = useState({ from, to });

  // A new range from the URL (back button, Clear all, chip removal) replaces the draft.
  if (synced.from !== from || synced.to !== to) {
    setSynced({ from, to });
    setDraft({ from: from ?? "", to: to ?? "" });
  }

  const error = rangeError(draft.from || null, draft.to || null);
  const change = (next: { from: string; to: string }) => {
    setDraft(next);
    if (!rangeError(next.from || null, next.to || null)) onChange(next.from || null, next.to || null);
  };

  return (
    <fieldset className="flex min-w-0 flex-col gap-1">
      <legend className="sr-only">
        {label}, custom range in store days ({zone})
      </legend>
      <div className="flex flex-wrap items-center gap-2">
        <label htmlFor={`${id}-from`} className="text-sm text-muted-foreground">
          From
        </label>
        <Input
          id={`${id}-from`}
          type="date"
          aria-label={`${label} from`}
          value={draft.from}
          max={draft.to || undefined}
          onChange={(event) => change({ ...draft, from: event.target.value })}
          className="w-auto"
        />
        <label htmlFor={`${id}-to`} className="text-sm text-muted-foreground">
          to
        </label>
        <Input
          id={`${id}-to`}
          type="date"
          aria-label={`${label} to`}
          value={draft.to}
          min={draft.from || undefined}
          aria-invalid={error ? true : undefined}
          aria-describedby={error ? `${id}-error` : undefined}
          onChange={(event) => change({ ...draft, to: event.target.value })}
          className="w-auto"
        />
        <span className="text-xs text-muted-foreground">({zone})</span>
      </div>
      {error ? (
        <p id={`${id}-error`} role="alert" className="flex items-center gap-1 text-sm text-tone-danger-fg">
          <CircleAlert aria-hidden className="size-4 shrink-0" />
          {error}
        </p>
      ) : null}
    </fieldset>
  );
}
