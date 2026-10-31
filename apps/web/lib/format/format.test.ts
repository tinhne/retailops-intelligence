import { describe, expect, it } from "vitest";

import {
  formatDate,
  formatDateTime,
  formatDateTimeCompact,
  formatDateTimeShort,
  formatDayKey,
  formatDue,
  formatDuration,
  formatLongDate,
  formatRelative,
  localDateKey,
  utcToZonedInputs,
  zonedTimeToUtc,
} from "./datetime";
import {
  formatBytes,
  formatCount,
  formatMoney,
  formatMoneyCompact,
  formatMoneyForSpeech,
  formatPercentValue,
  formatQuantity,
} from "./number";

const ET = "America/New_York";
// Daylight saving ends in New York at 2:00 AM EDT on Sunday, Nov 1, 2026 (06:00 UTC).
const BEFORE_DST_END = "2026-11-01T05:30:00Z"; // 1:30 AM EDT
const AFTER_DST_END = "2026-11-01T06:30:00Z"; // 1:30 AM EST
const NOW = new Date("2026-11-01T15:00:00Z"); // 10:00 AM EST

describe("money (BR-503)", () => {
  it("formats decimal strings in the store currency", () => {
    expect(formatMoney("1234.5", "USD")).toBe("$1,234.50");
    expect(formatMoney("0", "USD")).toBe("$0.00");
    expect(formatMoney("600.00", "EUR")).toBe("€600.00");
  });

  it("keeps cents exact for large amounts", () => {
    expect(formatMoney("9999999999.99", "USD")).toBe("$9,999,999,999.99");
  });

  it("uses U+2212 for negatives, and an ASCII minus for speech", () => {
    expect(formatMoney("-12.40", "USD")).toBe("−$12.40");
    expect(formatMoneyForSpeech("-12.40", "USD")).toBe("-$12.40");
  });

  it("compacts axis ticks only", () => {
    expect(formatMoneyCompact(12400, "USD")).toBe("$12.4K");
  });
});

describe("numbers", () => {
  it("formats quantities, counts, percentages and bytes", () => {
    expect(formatQuantity(1240)).toBe("1,240");
    expect(formatQuantity(-4)).toBe("−4");
    expect(formatCount(1, "row")).toBe("1 row");
    expect(formatCount(14, "row")).toBe("14 rows");
    expect(formatPercentValue("94.1")).toBe("94.1%");
    expect(formatPercentValue("100.0")).toBe("100%");
    expect(formatPercentValue("0.8")).toBe("0.8%");
    expect(formatBytes(1_800_000)).toBe("1.8 MB");
    expect(formatBytes(512)).toBe("512 B");
  });
});

describe("date and time in the store zone (BR-501)", () => {
  it("derives the zone abbreviation per instant across the DST change", () => {
    expect(formatDateTime(BEFORE_DST_END, ET, NOW)).toBe("Nov 1, 1:30 AM EDT");
    expect(formatDateTime(AFTER_DST_END, ET, NOW)).toBe("Nov 1, 1:30 AM EST");
  });

  it("adds the year only outside the current store-local year", () => {
    expect(formatDateTime("2025-12-30T21:05:00Z", ET, NOW)).toBe("Dec 30, 2025, 4:05 PM EST");
    expect(formatDateTimeShort("2026-10-31T13:42:00Z", ET, NOW)).toBe("Oct 31, 9:42 AM");
  });

  it("uses the store zone, not UTC, for calendar days", () => {
    // 02:00 UTC on Nov 1 is still Oct 31 in New York.
    expect(localDateKey(new Date("2026-11-01T02:00:00Z"), ET)).toBe("2026-10-31");
    expect(formatDate("2026-11-01T02:00:00Z", ET)).toBe("Oct 31, 2026");
    expect(formatLongDate(new Date("2026-11-01T02:00:00Z"), ET)).toBe("Saturday, Oct 31, 2026");
  });

  it("shows only the time for today", () => {
    expect(formatDateTimeCompact("2026-11-01T14:45:00Z", ET, NOW)).toBe("9:45 AM EST");
    expect(formatDateTimeCompact("2026-10-30T22:15:00Z", ET, NOW)).toBe("Oct 30, 6:15 PM EDT");
  });

  it("formats API day keys without shifting them", () => {
    expect(formatDayKey("2026-10-31")).toBe("Oct 31");
  });
});

describe("durations and deadlines", () => {
  it("switches to days at 72 hours", () => {
    expect(formatDuration(30)).toBe("30h");
    expect(formatDuration(102)).toBe("4d 6h");
  });

  it("words future and past deadlines", () => {
    const now = new Date("2026-11-01T12:00:00Z");
    expect(formatDue("2026-11-01T15:55:00Z", now)).toEqual({ overdue: false, text: "Due in 3h 55m" });
    expect(formatDue("2026-11-01T12:20:00Z", now)).toEqual({ overdue: false, text: "Due in 20m" });
    expect(formatDue("2026-11-03T16:00:00Z", now)).toEqual({ overdue: false, text: "Due in 2d 4h" });
    expect(formatDue("2026-10-31T06:00:00Z", now)).toEqual({ overdue: true, text: "Overdue 30h" });
    expect(formatDue("2026-10-28T06:00:00Z", now)).toEqual({ overdue: true, text: "Overdue 4d 6h" });
  });

  it("words elapsed time", () => {
    const now = new Date("2026-11-01T12:00:00Z");
    expect(formatRelative("2026-11-01T11:59:30Z", ET, now)).toBe("just now");
    expect(formatRelative("2026-11-01T11:48:00Z", ET, now)).toBe("12m ago");
    expect(formatRelative("2026-11-01T07:00:00Z", ET, now)).toBe("5h ago");
    expect(formatRelative("2026-10-29T12:00:00Z", ET, now)).toBe("3d ago");
    expect(formatRelative("2026-10-01T12:00:00Z", ET, now)).toBe("Oct 1, 2026");
  });
});

describe("store-local inputs", () => {
  it("converts store wall-clock times to UTC on both sides of the DST change", () => {
    expect(zonedTimeToUtc("2026-10-31", "09:00", ET).toISOString()).toBe("2026-10-31T13:00:00.000Z"); // EDT
    expect(zonedTimeToUtc("2026-11-02", "09:00", ET).toISOString()).toBe("2026-11-02T14:00:00.000Z"); // EST
    expect(zonedTimeToUtc("2026-11-01", "12:00", "UTC").toISOString()).toBe("2026-11-01T12:00:00.000Z");
  });

  it("round-trips an instant through the input fields", () => {
    expect(utcToZonedInputs("2026-11-02T14:00:00Z", ET)).toEqual({ date: "2026-11-02", time: "09:00" });
    const { date, time } = utcToZonedInputs("2026-10-31T13:30:00Z", ET);
    expect(zonedTimeToUtc(date, time, ET).toISOString()).toBe("2026-10-31T13:30:00.000Z");
  });
});
