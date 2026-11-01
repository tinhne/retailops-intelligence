import { formatDayKey, zonedTimeToUtc } from "@/lib/format/datetime";

// Custom date ranges in store-local calendar days (C-31 "date-range", BR-501). The URL keeps the
// days as `YYYY-MM-DD`; the API receives instants: the start day's midnight (inclusive) and the
// midnight after the end day (exclusive), both in the store zone.

const DATE_KEY = /^(\d{4})-(\d{2})-(\d{2})$/;

/** A real calendar day written as `YYYY-MM-DD`. */
export function isDateKey(value: string): boolean {
  const match = DATE_KEY.exec(value);
  if (!match) return false;
  const [year, month, day] = [Number(match[1]), Number(match[2]), Number(match[3])];
  const date = new Date(Date.UTC(year, month - 1, day));
  return date.getUTCFullYear() === year && date.getUTCMonth() === month - 1 && date.getUTCDate() === day;
}

function nextDay(key: string): string {
  const [year, month, day] = key.split("-").map(Number);
  return new Date(Date.UTC(year, month - 1, day + 1)).toISOString().slice(0, 10);
}

export const RANGE_ORDER_ERROR = "End date must be on or after start date.";

/** The validation message for a range (S-05 "Validation error"), or `null` when it is usable. */
export function rangeError(from: string | null, to: string | null): string | null {
  if (from && to && to < from) return RANGE_ORDER_ERROR;
  return null;
}

/** `{ from, to }` instants for the API: start of `from`, start of the day after `to`. */
export function rangeToApi(from: string | null, to: string | null, timeZone: string): { from?: string; to?: string } {
  return {
    from: from ? zonedTimeToUtc(from, "00:00", timeZone).toISOString() : undefined,
    to: to ? zonedTimeToUtc(nextDay(to), "00:00", timeZone).toISOString() : undefined,
  };
}

/** "Oct 1 – Oct 31", "From Oct 1" or "Until Oct 31", for filter chips. */
export function formatRange(from: string | null, to: string | null): string {
  if (from && to) return from === to ? formatDayKey(from) : `${formatDayKey(from)} – ${formatDayKey(to)}`;
  if (from) return `From ${formatDayKey(from)}`;
  if (to) return `Until ${formatDayKey(to)}`;
  return "Custom range";
}

/**
 * Reads a custom range from the URL. Malformed days and a reversed range are invalid: the
 * caller drops them and normalises the link like any other unknown filter (§0.3).
 */
export function parseRange(search: URLSearchParams, fromKey: string, toKey: string, invalid: string[]) {
  let from = search.get(fromKey);
  let to = search.get(toKey);
  if (from !== null && !isDateKey(from)) {
    invalid.push(fromKey);
    from = null;
  }
  if (to !== null && !isDateKey(to)) {
    invalid.push(toKey);
    to = null;
  }
  if (rangeError(from, to)) {
    invalid.push(toKey);
    to = null;
  }
  return { from: from || null, to: to || null };
}
