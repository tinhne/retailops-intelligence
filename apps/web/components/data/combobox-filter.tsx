"use client";

import { useQuery, type QueryKey } from "@tanstack/react-query";
import { Check, ChevronDown, Search } from "lucide-react";
import { useEffect, useId, useState } from "react";

import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { userMessage } from "@/lib/api/errors";
import { cn } from "@/lib/utils";

export type ComboboxOption = { value: string; label: string; detail?: string };

function useDebounced<T>(value: T, delay: number): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = window.setTimeout(() => setDebounced(value), delay);
    return () => window.clearTimeout(timer);
  }, [value, delay]);
  return debounced;
}

/**
 * A filter that searches the server for its options (C-31 "combobox"), for lists too long for a
 * checkbox menu, such as products. The input follows the ARIA combobox pattern: arrow keys move
 * through the options, Enter picks one, Escape closes.
 */
export function ComboboxFilter({
  label,
  value,
  valueLabel,
  placeholder,
  queryKey,
  loadOptions,
  noMatches,
  onChange,
}: {
  label: string;
  value: string | null;
  /** Shown on the trigger once a value is picked. */
  valueLabel?: string;
  placeholder: string;
  queryKey: (search: string) => QueryKey;
  loadOptions: (search: string, signal: AbortSignal) => Promise<ComboboxOption[]>;
  noMatches: string;
  onChange: (value: string | null) => void;
}) {
  const id = useId();
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");
  const [active, setActive] = useState(0);
  const term = useDebounced(search.trim(), 300);
  const options = useQuery({
    queryKey: queryKey(term),
    queryFn: ({ signal }) => loadOptions(term, signal),
    enabled: open,
    staleTime: 60_000,
  });
  const items = options.data ?? [];

  const pick = (option: ComboboxOption) => {
    onChange(option.value);
    setOpen(false);
    setSearch("");
  };
  const onKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setActive((index) => Math.min(index + 1, items.length - 1));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setActive((index) => Math.max(index - 1, 0));
    } else if (event.key === "Enter" && items[active]) {
      event.preventDefault();
      pick(items[active]);
    }
  };

  return (
    <Popover
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        if (!next) setSearch("");
      }}
    >
      <PopoverTrigger asChild>
        <Button
          type="button"
          variant="secondary"
          size="sm"
          aria-label={value ? `${label}: ${valueLabel ?? "selected"}, change` : label}
          className={cn("max-w-full", value && "border-primary bg-surface-selected")}
        >
          <span className="truncate">
            {label}
            {value && valueLabel ? ` · ${valueLabel}` : ""}
          </span>
          <ChevronDown aria-hidden className="size-3.5" />
        </Button>
      </PopoverTrigger>
      <PopoverContent align="start" className="w-80 max-w-[calc(100vw-2rem)] p-2">
        <div className="relative">
          <Search aria-hidden className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" />
          <input
            type="text"
            role="combobox"
            aria-label={`Search ${label.toLowerCase()}`}
            aria-expanded="true"
            aria-controls={`${id}-list`}
            aria-autocomplete="list"
            aria-activedescendant={items[active] ? `${id}-option-${active}` : undefined}
            value={search}
            placeholder={placeholder}
            maxLength={100}
            onChange={(event) => {
              setSearch(event.target.value);
              setActive(0);
            }}
            onKeyDown={onKeyDown}
            className="h-10 w-full rounded-md border border-input bg-card pr-2 pl-8 text-base text-foreground placeholder:text-text-placeholder focus-visible:border-ring focus-visible:shadow-[0_0_0_1px_var(--ring)] focus-visible:outline-none sm:h-8 sm:text-body"
          />
        </div>
        <ul id={`${id}-list`} role="listbox" aria-label={label} className="mt-2 flex max-h-72 flex-col overflow-y-auto">
          {items.map((option, index) => (
            <li
              key={option.value}
              id={`${id}-option-${index}`}
              role="option"
              aria-selected={option.value === value}
              onMouseEnter={() => setActive(index)}
              onClick={() => pick(option)}
              className={cn(
                "flex min-h-8 cursor-pointer items-center gap-2 rounded-md px-2 py-1 text-body",
                index === active && "bg-accent",
              )}
            >
              <Check aria-hidden className={cn("size-3.5 shrink-0", option.value === value ? "opacity-100" : "opacity-0")} />
              <span className="flex min-w-0 flex-col">
                <span className="truncate font-medium">{option.label}</span>
                {option.detail ? <span className="truncate text-xs text-muted-foreground">{option.detail}</span> : null}
              </span>
            </li>
          ))}
        </ul>
        <div aria-live="polite" className="text-sm text-muted-foreground">
          {options.isPending ? (
            <p className="px-2 py-1.5">Searching…</p>
          ) : options.isError ? (
            <p className="px-2 py-1.5 text-tone-danger-fg">
              {userMessage(options.error)}{" "}
              <button type="button" className="text-link underline" onClick={() => void options.refetch()}>
                Try again
              </button>
            </p>
          ) : items.length === 0 ? (
            <p className="px-2 py-1.5">{noMatches}</p>
          ) : null}
        </div>
        {value ? (
          <div className="mt-1 border-t pt-1">
            <button
              type="button"
              onClick={() => {
                onChange(null);
                setOpen(false);
              }}
              className="flex min-h-8 w-full items-center rounded-md px-2 text-left text-body hover:bg-accent"
            >
              Any {label.toLowerCase()}
            </button>
          </div>
        ) : null}
      </PopoverContent>
    </Popover>
  );
}
