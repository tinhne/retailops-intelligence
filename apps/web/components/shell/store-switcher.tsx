"use client";

import { Check, ChevronsUpDown } from "lucide-react";
import { useRouter } from "next/navigation";
import { Fragment } from "react";

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { zoneGenericName } from "@/lib/format/datetime";
import { allStores, useMe } from "@/lib/session/session";
import { useStore } from "@/lib/store/store-context";
import { cn } from "@/lib/utils";

/** Store name plus "USD · Times in ET" (IA §7). */
function StoreText({ name, currency, timezone }: { name: string; currency: string; timezone: string }) {
  return (
    <span className="flex min-w-0 flex-col text-left">
      <span className="truncate text-body-strong text-foreground">{name}</span>
      <span className="truncate text-xs font-normal text-muted-foreground">
        {currency} · Times in {zoneGenericName(timezone)}
      </span>
    </span>
  );
}

/**
 * A static label with one store, a menu grouped by organization with more (C-24). Switching
 * keeps the current section and drops record IDs (`/s/A/orders/1` → `/s/B/orders`).
 */
export function StoreSwitcher({ section, className }: { section: string; className?: string }) {
  const store = useStore();
  const { data: me } = useMe();
  const router = useRouter();
  const stores = me ? allStores(me) : [];

  if (stores.length <= 1) {
    return (
      <div className={cn("px-2 py-1", className)}>
        <StoreText name={store.name} currency={store.currency} timezone={store.timezone} />
      </div>
    );
  }

  const organizations = [...new Set(stores.map((item) => item.organizationName))];

  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        className={cn(
          "flex w-full items-center gap-2 rounded-md px-2 py-1 text-left transition-colors duration-100 hover:bg-accent",
          className,
        )}
        aria-label={`Store: ${store.name}. Switch store`}
      >
        <StoreText name={store.name} currency={store.currency} timezone={store.timezone} />
        <ChevronsUpDown aria-hidden className="ml-auto size-4 shrink-0 text-muted-foreground" />
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="w-64">
        {organizations.map((organization, index) => (
          <Fragment key={organization}>
            {index > 0 ? <DropdownMenuSeparator /> : null}
            <DropdownMenuLabel className="text-xs text-muted-foreground">{organization}</DropdownMenuLabel>
            {stores
              .filter((item) => item.organizationName === organization)
              .map((item) => (
                <DropdownMenuItem
                  key={item.id}
                  onSelect={() => router.push(`/s/${item.id}/${section}`)}
                  aria-current={item.id === store.id ? "true" : undefined}
                >
                  <span className="min-w-0 flex-1 truncate">{item.name}</span>
                  {item.id === store.id ? <Check aria-label="Current store" className="text-primary" /> : null}
                </DropdownMenuItem>
              ))}
          </Fragment>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
