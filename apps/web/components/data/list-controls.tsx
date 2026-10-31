"use client";

import { ChevronDown, Search, X } from "lucide-react";
import { useEffect, useId, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { formatQuantity } from "@/lib/format/number";
import { cn } from "@/lib/utils";

export type Option = { value: string; label: string; group?: string };

/** A labelled native select, styled like the other controls (works with every input method). */
export function SelectField({
  label,
  value,
  options,
  onChange,
  hideLabel = false,
  className,
}: {
  label: string;
  value: string;
  options: Option[];
  onChange: (value: string) => void;
  hideLabel?: boolean;
  className?: string;
}) {
  const id = useId();
  return (
    <div className={cn("flex items-center gap-2", className)}>
      <label htmlFor={id} className={cn("text-sm whitespace-nowrap text-muted-foreground", hideLabel && "sr-only")}>
        {label}
      </label>
      <div className="relative">
        <select
          id={id}
          value={value}
          onChange={(event) => onChange(event.target.value)}
          className="h-10 appearance-none rounded-md border border-input bg-card pr-8 pl-3 text-base text-foreground hover:border-input-hover focus-visible:border-ring focus-visible:shadow-[0_0_0_1px_var(--ring)] focus-visible:outline-none sm:h-8 sm:text-body"
        >
          {options.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
        <ChevronDown aria-hidden className="pointer-events-none absolute top-1/2 right-2 size-4 -translate-y-1/2 text-muted-foreground" />
      </div>
    </div>
  );
}

/** A filter button opening a checkbox list (C-31 "multi"). Its name includes the count. */
export function MultiSelectFilter({
  label,
  options,
  selected,
  onChange,
}: {
  label: string;
  options: Option[];
  selected: string[];
  onChange: (values: string[]) => void;
}) {
  const groups = [...new Set(options.map((option) => option.group))];
  const toggle = (value: string, checked: boolean) =>
    onChange(checked ? [...selected, value] : selected.filter((item) => item !== value));

  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button
          type="button"
          variant="secondary"
          size="sm"
          aria-label={selected.length ? `${label}, ${selected.length} selected` : label}
          className={cn(selected.length > 0 && "border-primary bg-surface-selected")}
        >
          {label}
          {selected.length > 0 ? <span className="tabular-nums">· {selected.length}</span> : null}
          <ChevronDown aria-hidden className="size-3.5" />
        </Button>
      </PopoverTrigger>
      <PopoverContent align="start" className="w-64 p-2">
        <fieldset className="flex max-h-80 flex-col gap-0.5 overflow-y-auto">
          <legend className="sr-only">{label}</legend>
          {groups.map((group) => (
            <div key={group ?? "all"} className="flex flex-col gap-0.5">
              {group ? <p className="px-2 pt-2 pb-1 text-xs text-muted-foreground">{group}</p> : null}
              {options
                .filter((option) => option.group === group)
                .map((option) => (
                  <label
                    key={option.value}
                    className="flex min-h-8 cursor-pointer items-center gap-2 rounded-md px-2 text-body hover:bg-accent"
                  >
                    <Checkbox
                      checked={selected.includes(option.value)}
                      onCheckedChange={(checked) => toggle(option.value, checked === true)}
                    />
                    {option.label}
                  </label>
                ))}
            </div>
          ))}
        </fieldset>
      </PopoverContent>
    </Popover>
  );
}

export type Chip = { key: string; label: string; onRemove: () => void };

/** Active filters as removable chips plus "Clear all" (C-31). */
export function FilterChips({ chips, onClearAll }: { chips: Chip[]; onClearAll: () => void }) {
  if (chips.length === 0) return null;
  return (
    <div className="flex flex-wrap items-center gap-2">
      {chips.map((chip) => (
        <span
          key={chip.key}
          className="inline-flex h-6 items-center gap-1 rounded-sm border border-tone-primary-border bg-surface-selected pr-0.5 pl-2 text-xs"
        >
          {chip.label}
          <button
            type="button"
            onClick={chip.onRemove}
            aria-label={`Remove filter ${chip.label}`}
            className="inline-flex size-5 items-center justify-center rounded-sm text-muted-foreground hover:bg-accent hover:text-foreground"
          >
            <X aria-hidden className="size-3" />
          </button>
        </span>
      ))}
      <Button type="button" variant="link" size="sm" onClick={onClearAll}>
        Clear all
      </Button>
    </div>
  );
}

/** Search box with a 300 ms debounce, a clear button, and "/" to focus it (C-32). */
export function SearchInput({
  value,
  onChange,
  placeholder,
  label,
}: {
  value: string;
  onChange: (value: string) => void;
  placeholder: string;
  label: string;
}) {
  const [draft, setDraft] = useState(value);
  const [synced, setSynced] = useState(value);
  const input = useRef<HTMLInputElement>(null);

  // A new value from the URL (back button, Clear all) replaces the draft.
  if (value !== synced) {
    setSynced(value);
    setDraft(value);
  }

  useEffect(() => {
    if (draft === value) return;
    const timer = window.setTimeout(() => onChange(draft), 300);
    return () => window.clearTimeout(timer);
  }, [draft, value, onChange]);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      const typing = target?.closest("input, textarea, select, [contenteditable=true]");
      if (event.key === "/" && !typing) {
        event.preventDefault();
        input.current?.focus();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  return (
    <div className="relative w-full sm:w-72">
      <Search aria-hidden className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" />
      <input
        ref={input}
        type="search"
        aria-label={label}
        value={draft}
        maxLength={100}
        placeholder={placeholder}
        onChange={(event) => setDraft(event.target.value)}
        className="h-10 w-full rounded-md border border-input bg-card pr-8 pl-8 text-base text-foreground placeholder:text-text-placeholder hover:border-input-hover focus-visible:border-ring focus-visible:shadow-[0_0_0_1px_var(--ring)] focus-visible:outline-none sm:h-8 sm:text-body [&::-webkit-search-cancel-button]:hidden"
      />
      {draft ? (
        <button
          type="button"
          aria-label="Clear search"
          onClick={() => {
            setDraft("");
            onChange("");
          }}
          className="absolute top-1/2 right-1.5 inline-flex size-6 -translate-y-1/2 items-center justify-center rounded-sm text-muted-foreground hover:bg-accent"
        >
          <X aria-hidden className="size-3.5" />
        </button>
      ) : null}
    </div>
  );
}

/** "1–25 of 312", rows per page, Previous / Next, "Page 2 of 13" (C-33). */
export function Pagination({
  page,
  pageSize,
  total,
  onPageChange,
  onPageSizeChange,
}: {
  page: number;
  pageSize: number;
  total: number;
  onPageChange: (page: number) => void;
  onPageSizeChange: (size: number) => void;
}) {
  const pages = Math.max(1, Math.ceil(total / pageSize));
  const first = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const last = Math.min(total, page * pageSize);
  return (
    <nav aria-label="Pagination" className="flex flex-wrap items-center justify-between gap-3 border-t px-4 py-2 text-sm">
      <p className="text-muted-foreground tabular-nums">
        {formatQuantity(first)}–{formatQuantity(last)} of {formatQuantity(total)}
      </p>
      <div className="flex flex-wrap items-center gap-3">
        <SelectField
          label="Rows per page"
          value={String(pageSize)}
          options={[25, 50, 100].map((size) => ({ value: String(size), label: String(size) }))}
          onChange={(value) => onPageSizeChange(Number(value))}
        />
        <Button type="button" variant="secondary" size="sm" disabled={page <= 1} onClick={() => onPageChange(page - 1)}>
          Previous
        </Button>
        <span className="tabular-nums text-muted-foreground">
          Page {formatQuantity(page)} of {formatQuantity(pages)}
        </span>
        <Button type="button" variant="secondary" size="sm" disabled={page >= pages} onClick={() => onPageChange(page + 1)}>
          Next
        </Button>
      </div>
    </nav>
  );
}
