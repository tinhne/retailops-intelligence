import { describe, expect, it } from "vitest";

import { formatRange, isDateKey, parseRange, rangeError, rangeToApi } from "./date-range";

describe("custom date ranges in store days", () => {
  it("accepts real calendar days only", () => {
    expect(isDateKey("2026-10-31")).toBe(true);
    expect(isDateKey("2028-02-29")).toBe(true);
    expect(isDateKey("2026-02-29")).toBe(false);
    expect(isDateKey("2026-1-01")).toBe(false);
    expect(isDateKey("10/31/2026")).toBe(false);
  });

  it("refuses an end day before the start day", () => {
    expect(rangeError("2026-10-31", "2026-10-01")).toBe("End date must be on or after start date.");
    expect(rangeError("2026-10-31", "2026-10-31")).toBeNull();
    expect(rangeError(null, "2026-10-01")).toBeNull();
  });

  it("turns days into the store's midnights, the end exclusive", () => {
    expect(rangeToApi("2026-10-31", "2026-10-31", "America/New_York")).toEqual({
      from: "2026-10-31T04:00:00.000Z",
      to: "2026-11-01T04:00:00.000Z",
    });
    expect(rangeToApi(null, "2026-12-31", "America/New_York")).toEqual({ from: undefined, to: "2027-01-01T05:00:00.000Z" });
  });

  it("labels chips", () => {
    expect(formatRange("2026-10-01", "2026-10-31")).toBe("Oct 1 – Oct 31");
    expect(formatRange("2026-10-01", "2026-10-01")).toBe("Oct 1");
    expect(formatRange("2026-10-01", null)).toBe("From Oct 1");
    expect(formatRange(null, "2026-10-31")).toBe("Until Oct 31");
  });

  it("reports malformed parts of a link", () => {
    const invalid: string[] = [];
    expect(parseRange(new URLSearchParams("from=2026-13-01&to=2026-10-02"), "from", "to", invalid)).toEqual({
      from: null,
      to: "2026-10-02",
    });
    expect(invalid).toEqual(["from"]);
  });
});
