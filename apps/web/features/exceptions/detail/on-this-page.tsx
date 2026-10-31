"use client";

import { ChevronDown, ListTree } from "lucide-react";
import { useRef } from "react";

import { SelectField } from "@/components/data/list-controls";
import { Button } from "@/components/ui/button";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { useMediaQuery } from "@/lib/hooks/browser";

export type PageSection = { id: string; label: string };

/** Scrolls to a section (its `scroll-margin` clears the top bar) and moves focus to its heading. */
export function jumpTo(id: string) {
  const section = document.getElementById(id);
  if (!section) return;
  section.scrollIntoView({ block: "start" });
  const heading = section.querySelector<HTMLElement>("h2");
  if (heading) {
    if (!heading.hasAttribute("tabindex")) heading.setAttribute("tabindex", "-1");
    heading.focus({ preventScroll: true });
  }
}

/**
 * "On this page" (S-04, below 1280 px where the page is one long column): a select from 768 px,
 * a menu below. Lists only the sections the page actually rendered.
 */
export function OnThisPage({ sections }: { sections: PageSection[] }) {
  const wide = useMediaQuery("(min-width: 768px)");
  const picked = useRef<string | null>(null);
  if (sections.length === 0) return null;
  return (
    <div className="xl:hidden">
      {wide ? (
        <SelectField
          label="On this page"
          value=""
          options={[{ value: "", label: "Jump to a section" }, ...sections.map((section) => ({ value: section.id, label: section.label }))]}
          onChange={(id) => id && jumpTo(id)}
        />
      ) : (
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button type="button" variant="secondary" size="sm">
              <ListTree aria-hidden />
              On this page
              <ChevronDown aria-hidden />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent
            align="start"
            className="w-56"
            // The menu returns focus to its trigger on close; after a pick, focus goes to the section instead.
            onCloseAutoFocus={(event) => {
              if (!picked.current) return;
              event.preventDefault();
              jumpTo(picked.current);
              picked.current = null;
            }}
          >
            {sections.map((section) => (
              <DropdownMenuItem
                key={section.id}
                onSelect={() => {
                  picked.current = section.id;
                }}
              >
                {section.label}
              </DropdownMenuItem>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>
      )}
    </div>
  );
}
