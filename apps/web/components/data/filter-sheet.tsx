"use client";

import { SlidersHorizontal } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Sheet, SheetContent, SheetDescription, SheetFooter, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet";

import type { Option } from "./list-controls";

/**
 * The collapsed FilterBar below 768 px (C-31): "Filters (n)" opens a bottom sheet whose controls
 * edit a draft. **Apply** writes the draft to the URL, **Reset** clears the draft.
 */
export function FilterSheet({
  count,
  onOpen,
  onApply,
  onReset,
  children,
}: {
  /** Active filters, shown in the trigger. */
  count: number;
  /** Copies the applied filters into the draft. */
  onOpen: () => void;
  onApply: () => void;
  onReset: () => void;
  children: React.ReactNode;
}) {
  const [open, setOpen] = useState(false);
  return (
    <Sheet
      open={open}
      onOpenChange={(next) => {
        if (next) onOpen();
        setOpen(next);
      }}
    >
      <SheetTrigger asChild>
        <Button type="button" variant="secondary" size="sm" aria-label={count ? `Filters, ${count} active` : "Filters"}>
          <SlidersHorizontal aria-hidden />
          Filters{count ? ` (${count})` : ""}
        </Button>
      </SheetTrigger>
      <SheetContent side="bottom" className="max-h-[85dvh] gap-0 rounded-t-lg">
        <SheetHeader className="border-b">
          <SheetTitle>Filters</SheetTitle>
          <SheetDescription className="sr-only">Choose filters, then apply them to the list.</SheetDescription>
        </SheetHeader>
        <div className="flex min-h-0 flex-1 flex-col gap-5 overflow-y-auto p-4">{children}</div>
        <SheetFooter className="flex-row border-t">
          <Button type="button" variant="secondary" size="lg" className="flex-1" onClick={onReset}>
            Reset
          </Button>
          <Button
            type="button"
            size="lg"
            className="flex-1"
            onClick={() => {
              onApply();
              setOpen(false);
            }}
          >
            Apply
          </Button>
        </SheetFooter>
      </SheetContent>
    </Sheet>
  );
}

/** A labelled group of checkboxes for a multi-value filter inside the sheet. */
export function CheckboxGroup({
  legend,
  options,
  selected,
  onChange,
}: {
  legend: string;
  options: Option[];
  selected: string[];
  onChange: (values: string[]) => void;
}) {
  return (
    <fieldset className="flex flex-col gap-1">
      <legend className="mb-1 text-body-strong">{legend}</legend>
      <div className="grid grid-cols-1 gap-x-4 min-[400px]:grid-cols-2">
        {options.map((option) => (
          <label key={option.value} className="flex min-h-10 cursor-pointer items-center gap-2 text-body">
            <Checkbox
              checked={selected.includes(option.value)}
              onCheckedChange={(checked) =>
                onChange(checked === true ? [...selected, option.value] : selected.filter((value) => value !== option.value))
              }
            />
            {option.label}
          </label>
        ))}
      </div>
    </fieldset>
  );
}
