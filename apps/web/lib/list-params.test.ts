import { describe, expect, it } from "vitest";

import { defineListParams } from "./list-params";

const list = defineListParams(
  {
    q: { kind: "text", max: 10 },
    status: { kind: "one", values: ["ACTIVE", "DRAFT", "ALL"], fallback: "ACTIVE" },
    health: { kind: "many", values: ["OVERSOLD", "HEALTHY"] },
    include_inactive: { kind: "flag" },
    product_id: { kind: "id" },
  },
  { sorts: ["sku", "-available"], defaultSort: "sku", pageSizes: [25, 50], defaultPageSize: 25 },
);
const parse = (query: string) => list.parse(new URLSearchParams(query));
const ID = "0a33dc48-ca87-4fba-9bef-fd654e1941e5";

describe("defineListParams (IA §9)", () => {
  it("applies defaults", () => {
    expect(parse("").params).toEqual({ q: "", status: "ACTIVE", health: [], include_inactive: false, product_id: null, sort: "sku", page: 1, page_size: 25 });
  });

  it("drops and reports unknown values", () => {
    const { params, invalid } = parse(`q=abcdefghijklmn&status=GONE&health=HEALTHY&health=BAD&include_inactive=yes&product_id=x&sort=name&page=0&page_size=7`);
    expect(params).toMatchObject({ q: "abcdefghij", status: "ACTIVE", health: ["HEALTHY"], include_inactive: false, product_id: null, sort: "sku", page: 1, page_size: 25 });
    expect(invalid.sort()).toEqual(["health", "include_inactive", "page", "page_size", "product_id", "sort", "status"]);
  });

  it("round-trips without defaults", () => {
    const query = `status=ALL&health=OVERSOLD&include_inactive=true&product_id=${ID}&sort=-available&page=2&page_size=50`;
    expect(list.serialize(parse(query).params).toString()).toBe(query);
    expect(list.serialize(parse("status=ACTIVE").params).toString()).toBe("");
  });

  it("knows when the list is narrowed, and clears filters but not sort", () => {
    expect(list.isFiltered(parse("sort=-available").params)).toBe(false);
    expect(list.isFiltered(parse("status=DRAFT").params)).toBe(true);
    const cleared = list.cleared(parse("q=pan&health=OVERSOLD&sort=-available&page=3").params);
    expect(cleared).toMatchObject({ q: "", health: [], sort: "-available", page: 1 });
  });

  it("resets the page on changes other than paging", () => {
    const { params } = parse("page=4");
    expect(list.update(params, { q: "x" }).page).toBe(1);
    expect(list.update(params, { page: 5 }).page).toBe(5);
  });
});

describe("date fields and cross-field checks", () => {
  const ranged = defineListParams(
    { from: { kind: "date" }, to: { kind: "date" } },
    {
      sorts: ["-at"],
      defaultSort: "-at",
      pageSizes: [50],
      defaultPageSize: 50,
      refine: (params) => (params.from && params.to && String(params.to) < String(params.from) ? ["to"] : []),
    },
  );

  it("keeps real days and drops malformed ones", () => {
    const { params, invalid } = ranged.parse(new URLSearchParams("from=2026-10-01&to=2026-10-32"));
    expect(params).toMatchObject({ from: "2026-10-01", to: null });
    expect(invalid).toEqual(["to"]);
    expect(ranged.serialize(params).toString()).toBe("from=2026-10-01");
  });

  it("drops what the refinement rejects", () => {
    const { params, invalid } = ranged.parse(new URLSearchParams("from=2026-10-31&to=2026-10-01"));
    expect(params).toMatchObject({ from: "2026-10-31", to: null });
    expect(invalid).toEqual(["to"]);
  });
});
