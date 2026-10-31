// URL state for list screens (IA §9): parse and validate search params, drop unknown values, and
// write them back without defaults. One definition per screen describes its fields.

import { isDateKey } from "@/lib/date-range";

export type FieldSpec =
  | { kind: "text"; max: number }
  | { kind: "one"; values: readonly string[]; fallback?: string }
  | { kind: "many"; values: readonly string[] }
  | { kind: "flag" }
  | { kind: "id" }
  /** A store-local calendar day, `YYYY-MM-DD` (custom date ranges). */
  | { kind: "date" };

type FieldValue<S extends FieldSpec> = S extends { kind: "text" }
  ? string
  : S extends { kind: "many" }
    ? string[]
    : S extends { kind: "flag" }
      ? boolean
      : string | null;

export type ListParams<F extends Record<string, FieldSpec>> = { [K in keyof F]: FieldValue<F[K]> } & {
  sort: string;
  page: number;
  page_size: number;
};

type Options = {
  sorts: readonly string[];
  defaultSort: string;
  pageSizes: readonly number[];
  defaultPageSize: number;
  /**
   * Cross-field checks after each field is parsed on its own, e.g. a reversed date range.
   * Returns the keys to drop; they are reset to their defaults and reported as invalid.
   */
  refine?: (params: Record<string, unknown>) => string[];
};

export type ListDefinition<F extends Record<string, FieldSpec>> = {
  parse(search: URLSearchParams): { params: ListParams<F>; invalid: string[] };
  serialize(params: ListParams<F>): URLSearchParams;
  isFiltered(params: ListParams<F>): boolean;
  update(params: ListParams<F>, patch: Partial<ListParams<F>>): ListParams<F>;
  cleared(params: ListParams<F>): ListParams<F>;
  options: Options;
};

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export function defineListParams<F extends Record<string, FieldSpec>>(fields: F, options: Options): ListDefinition<F> {
  type P = ListParams<F>;

  function parse(search: URLSearchParams): { params: P; invalid: string[] } {
    const invalid: string[] = [];
    const out: Record<string, unknown> = {};
    for (const [key, spec] of Object.entries(fields)) {
      const raw = search.get(key);
      switch (spec.kind) {
        case "text":
          out[key] = (raw ?? "").slice(0, spec.max);
          break;
        case "flag":
          if (raw !== null && raw !== "true") invalid.push(key);
          out[key] = raw === "true";
          break;
        case "id":
          if (raw && !UUID.test(raw)) invalid.push(key);
          out[key] = raw && UUID.test(raw) ? raw : null;
          break;
        case "date":
          if (raw && !isDateKey(raw)) invalid.push(key);
          out[key] = raw && isDateKey(raw) ? raw : null;
          break;
        case "one":
          if (raw && !spec.values.includes(raw)) invalid.push(key);
          out[key] = raw && spec.values.includes(raw) ? raw : (spec.fallback ?? null);
          break;
        case "many": {
          const picked: string[] = [];
          for (const value of search.getAll(key)) {
            if (!spec.values.includes(value)) invalid.push(key);
            else if (!picked.includes(value)) picked.push(value);
          }
          out[key] = picked;
          break;
        }
      }
    }
    for (const key of options.refine?.(out) ?? []) {
      invalid.push(key);
      const spec = fields[key];
      out[key] = spec.kind === "many" ? [] : spec.kind === "text" ? "" : spec.kind === "flag" ? false : spec.kind === "one" ? (spec.fallback ?? null) : null;
    }
    const sort = search.get("sort");
    if (sort && !options.sorts.includes(sort)) invalid.push("sort");
    const page = Number(search.get("page") ?? "1");
    if (search.has("page") && !(Number.isInteger(page) && page >= 1)) invalid.push("page");
    const size = Number(search.get("page_size") ?? String(options.defaultPageSize));
    if (search.has("page_size") && !options.pageSizes.includes(size)) invalid.push("page_size");
    out.sort = sort && options.sorts.includes(sort) ? sort : options.defaultSort;
    out.page = Number.isInteger(page) && page >= 1 ? page : 1;
    out.page_size = options.pageSizes.includes(size) ? size : options.defaultPageSize;
    return { params: out as P, invalid };
  }

  function serialize(params: P): URLSearchParams {
    const search = new URLSearchParams();
    for (const [key, spec] of Object.entries(fields)) {
      const value = (params as Record<string, unknown>)[key];
      if (spec.kind === "many") for (const item of value as string[]) search.append(key, item);
      else if (spec.kind === "flag") {
        if (value) search.set(key, "true");
      } else if (spec.kind === "one" && value === (spec.fallback ?? null)) continue;
      else if (value) search.set(key, String(value));
    }
    if (params.sort !== options.defaultSort) search.set("sort", params.sort);
    if (params.page !== 1) search.set("page", String(params.page));
    if (params.page_size !== options.defaultPageSize) search.set("page_size", String(params.page_size));
    return search;
  }

  /** Anything beyond defaults narrows the list (decides "No results" versus "Empty"). */
  function isFiltered(params: P): boolean {
    return Object.entries(fields).some(([key, spec]) => {
      const value = (params as Record<string, unknown>)[key];
      if (spec.kind === "many") return (value as string[]).length > 0;
      if (spec.kind === "text") return (value as string).trim() !== "";
      if (spec.kind === "one") return value !== (spec.fallback ?? null);
      return Boolean(value);
    });
  }

  /** Applies a change and resets to page 1 unless the page itself changes (C-30). */
  function update(params: P, patch: Partial<P>): P {
    const next: P = { ...params, ...patch };
    return "page" in patch ? next : { ...next, page: 1 };
  }

  /** Every filter back to its default, keeping sort and page size. */
  function cleared(params: P): P {
    const reset: Record<string, unknown> = {};
    for (const [key, spec] of Object.entries(fields)) {
      reset[key] = spec.kind === "many" ? [] : spec.kind === "text" ? "" : spec.kind === "flag" ? false : spec.kind === "one" ? (spec.fallback ?? null) : null;
    }
    return { ...params, ...reset, page: 1 } as P;
  }

  return { parse, serialize, isFiltered, update, cleared, options };
}
