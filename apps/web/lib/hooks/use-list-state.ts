"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef } from "react";
import { toast } from "sonner";

import type { FieldSpec, ListDefinition, ListParams } from "@/lib/list-params";

/**
 * Binds a list definition to the URL: parsed params, an `update` that writes them back, and the
 * normalisation of shared links with unknown values (SCREEN_SPECIFICATIONS §0.3).
 */
export function useListState<F extends Record<string, FieldSpec>>(definition: ListDefinition<F>) {
  type P = ListParams<F>;
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const { params, invalid } = useMemo(() => definition.parse(searchParams), [definition, searchParams]);

  const navigate = useCallback(
    (next: P, mode: "replace" | "push" = "replace") => {
      const search = definition.serialize(next).toString();
      const url = search ? `${pathname}?${search}` : pathname;
      if (mode === "push") router.push(url, { scroll: false });
      else router.replace(url, { scroll: false });
    },
    [definition, pathname, router],
  );

  const normalised = useRef(false);
  useEffect(() => {
    if (normalised.current || invalid.length === 0) return;
    normalised.current = true;
    toast.info("Some filters in the link weren't recognised and were removed.");
    navigate(params);
  }, [invalid.length, navigate, params]);

  return {
    params,
    update: (patch: Partial<P>, mode: "replace" | "push" = "replace") => navigate(definition.update(params, patch), mode),
    clearAll: () => navigate(definition.cleared(params)),
    isFiltered: definition.isFiltered(params),
  };
}
