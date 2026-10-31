"use client";

import { useEffect } from "react";

import { useStore } from "@/lib/store/store-context";

/** `{Page} · {Store name} · RetailOps` (IA §7). */
export function useDocumentTitle(page: string): void {
  const { name } = useStore();
  useEffect(() => {
    document.title = `${page} · ${name} · RetailOps`;
  }, [page, name]);
}
