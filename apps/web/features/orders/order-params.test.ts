import { describe, expect, it } from "vitest";

import { parseOrderParams, serializeOrderParams, storeMidnight, toOrderQuery, updateOrderParams } from "./order-params";

const ET = "America/New_York";
const parse = (query: string) => parseOrderParams(new URLSearchParams(query));

describe("orders URL state (S-05)", () => {
  it("defaults to newest first, and drops unknown values", () => {
    expect(parse("").params).toMatchObject({ sort: "-placed_at", page: 1, page_size: 25, overdue: false });
    const { params, invalid } = parse("status=PAID&status=LOST&channel=FAX&overdue=yes&sort=ship_by");
    expect(params.status).toEqual(["PAID"]);
    expect(params.channel).toBeNull();
    expect(params.overdue).toBe(false);
    expect(params.sort).toBe("ship_by");
    expect(invalid.sort()).toEqual(["channel", "overdue", "status"]);
  });

  it("round-trips without default noise", () => {
    const { params } = parse("status=PAID&status=PROCESSING&overdue=true&placed=7d&page=2");
    expect(serializeOrderParams(params).toString()).toBe("status=PAID&status=PROCESSING&placed=7d&overdue=true&page=2");
  });

  it("resets the page on filter changes", () => {
    const { params } = parse("page=4");
    expect(updateOrderParams(params, { overdue: true }).page).toBe(1);
    expect(updateOrderParams(params, { page: 5 }).page).toBe(5);
  });
});

describe("placed presets use store-local days (BR-501)", () => {
  // 03:00 UTC on Nov 1 is still Oct 31, 11 PM in New York.
  const now = new Date("2026-11-01T03:00:00Z");

  it("starts today at store midnight, not UTC midnight", () => {
    expect(storeMidnight(now, ET, 0).toISOString()).toBe("2026-10-31T04:00:00.000Z");
  });

  it("counts back calendar days across the DST change", () => {
    // Nov 2 (EST) minus 6 days is Oct 27 (EDT).
    expect(storeMidnight(new Date("2026-11-02T15:00:00Z"), ET, 6).toISOString()).toBe("2026-10-27T04:00:00.000Z");
  });

  it("builds the API query", () => {
    const { params } = parse("placed=today&overdue=true&q=%20KHK-1%20");
    expect(toOrderQuery(params, now, ET)).toMatchObject({
      placed_from: "2026-10-31T04:00:00.000Z",
      overdue: true,
      q: "KHK-1",
      sort: "-placed_at",
    });
  });
});
