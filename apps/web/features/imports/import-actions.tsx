"use client";

import { ChevronDown, Download, Plus } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { toast } from "sonner";

import { ActionButton } from "@/components/actions/action-button";
import { sectionHref } from "@/components/shell/nav-config";
import { Button, type ButtonProps } from "@/components/ui/button";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { downloadFile } from "@/lib/api/download";
import { isApiError } from "@/lib/api/errors";
import { importsApi } from "@/lib/api/imports-api";
import { IMPORT_TYPES_IN_ORDER, importTypeLabels, type ImportType } from "@/lib/status-maps";
import { usePermission, useStore, type StoreContextValue } from "@/lib/store/store-context";

/**
 * The new-import URL for a type, or `undefined` when the person can't run imports, so empty
 * states elsewhere only offer the action to people who can take it.
 */
export function newImportHref(store: StoreContextValue, type?: ImportType): string | undefined {
  if (!store.permissions.has("imports.run") || !sectionHref(store.id, "imports", store.permissions)) return undefined;
  return `/s/${store.id}/imports/new${type ? `?type=${type}` : ""}`;
}

/** "New import" (S-11): a link when allowed, otherwise a disabled button with the reason. */
export function NewImportButton({ type, label = "New import", variant = "primary" }: { type?: ImportType; label?: string; variant?: ButtonProps["variant"] }) {
  const store = useStore();
  const gate = usePermission("imports.run");
  const href = newImportHref(store, type);
  if (gate.allowed && href) {
    return (
      <Button asChild variant={variant}>
        <Link href={href}>
          <Plus aria-hidden />
          {label}
        </Link>
      </Button>
    );
  }
  return (
    <ActionButton gate={gate.allowed ? { allowed: false, reason: "Imports aren't available yet." } : gate} variant={variant}>
      <Plus aria-hidden />
      {label}
    </ActionButton>
  );
}

/** Fetches a file and toasts on failure (S-11 "Template download error"). */
export function useDownload() {
  const [pending, setPending] = useState<string | null>(null);
  const run = async (key: string, path: string, fallbackName: string, failure: string) => {
    setPending(key);
    try {
      await downloadFile(path, fallbackName);
    } catch (error) {
      if (!(isApiError(error) && error.status === 401)) {
        toast.error(failure, { action: { label: "Try again", onClick: () => void run(key, path, fallbackName, failure) } });
      }
    } finally {
      setPending(null);
    }
  };
  return { pending, run };
}

/** "Download template ▾", in the recommended import order. */
export function TemplateMenu({ variant = "secondary" }: { variant?: ButtonProps["variant"] }) {
  const store = useStore();
  const { pending, run } = useDownload();
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant={variant} pending={pending !== null}>
          <Download aria-hidden />
          Download template
          <ChevronDown aria-hidden />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        {IMPORT_TYPES_IN_ORDER.map((type) => (
          <DropdownMenuItem
            key={type}
            onSelect={() =>
              void run(type, importsApi.templatePath(store.id, type), `${type}_template.csv`, "Couldn't download the template. Try again.")
            }
          >
            {type}.csv
            <span className="ml-auto pl-4 text-xs text-muted-foreground">{importTypeLabels[type]}</span>
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

/** An empty state's import action (S-02, S-05, S-07, S-09, S-10). Shown only to people who can run imports. */
export function ImportLink({ type, label }: { type?: ImportType; label: string }) {
  const store = useStore();
  const href = newImportHref(store, type);
  if (!href) return null;
  return (
    <Button asChild>
      <Link href={href}>
        <Plus aria-hidden />
        {label}
      </Link>
    </Button>
  );
}
