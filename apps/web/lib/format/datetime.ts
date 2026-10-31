// Date and time formatters (DESIGN_SYSTEM §13). Every function takes the store time zone and
// never reads the browser's zone (BR-501). Zone abbreviations come from Intl for each instant,
// so EDT/EST switch correctly across daylight-saving changes.

const HOUR = 60 * 60 * 1000;
const MINUTE = 60 * 1000;

/**
 * Generic zone name for a store time zone, e.g. "ET" for America/New_York (DESIGN_SYSTEM §13).
 * Used in column headers and the store label; full timestamps carry the specific abbreviation.
 */
export function zoneGenericName(timeZone: string, at: Date = new Date()): string {
  try {
    const part = new Intl.DateTimeFormat("en-US", { timeZone, timeZoneName: "shortGeneric" })
      .formatToParts(at)
      .find((item) => item.type === "timeZoneName");
    return part?.value ?? timeZone;
  } catch {
    return timeZone;
  }
}

/** The store-local calendar date as `YYYY-MM-DD`. */
export function localDateKey(at: Date, timeZone: string): string {
  return new Intl.DateTimeFormat("en-CA", { timeZone, year: "numeric", month: "2-digit", day: "2-digit" }).format(at);
}

function localYear(at: Date, timeZone: string): string {
  return new Intl.DateTimeFormat("en-US", { timeZone, year: "numeric" }).format(at);
}

/** "Oct 31, 9:42 AM EDT", with the year added when it is not the current year in the store zone. */
export function formatDateTime(iso: string, timeZone: string, now: Date = new Date()): string {
  const at = new Date(iso);
  return new Intl.DateTimeFormat("en-US", {
    timeZone,
    month: "short",
    day: "numeric",
    year: localYear(at, timeZone) === localYear(now, timeZone) ? undefined : "numeric",
    hour: "numeric",
    minute: "2-digit",
    timeZoneName: "short",
  }).format(at);
}

/** "Oct 31, 9:42 AM": table cells, where the column header carries the generic zone. */
export function formatDateTimeShort(iso: string, timeZone: string, now: Date = new Date()): string {
  const at = new Date(iso);
  return new Intl.DateTimeFormat("en-US", {
    timeZone,
    month: "short",
    day: "numeric",
    year: localYear(at, timeZone) === localYear(now, timeZone) ? undefined : "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(at);
}

/** "9:42 AM EDT". */
export function formatTime(iso: string, timeZone: string): string {
  return new Intl.DateTimeFormat("en-US", {
    timeZone,
    hour: "numeric",
    minute: "2-digit",
    timeZoneName: "short",
  }).format(new Date(iso));
}

/** Time only when the instant is today in the store zone, otherwise the full date and time. */
export function formatDateTimeCompact(iso: string, timeZone: string, now: Date = new Date()): string {
  return localDateKey(new Date(iso), timeZone) === localDateKey(now, timeZone)
    ? formatTime(iso, timeZone)
    : formatDateTime(iso, timeZone, now);
}

/** "Oct 31, 2026". */
export function formatDate(iso: string, timeZone: string): string {
  return new Intl.DateTimeFormat("en-US", { timeZone, month: "short", day: "numeric", year: "numeric" }).format(
    new Date(iso),
  );
}

/** "Saturday, Oct 31, 2026": today's date in the store zone, for page subtitles. */
export function formatLongDate(at: Date, timeZone: string): string {
  return new Intl.DateTimeFormat("en-US", {
    timeZone,
    weekday: "long",
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(at);
}

/** A store-local calendar day (`YYYY-MM-DD` from the API) as "Oct 31". */
export function formatDayKey(day: string): string {
  const [year, month, date] = day.split("-").map(Number);
  return new Intl.DateTimeFormat("en-US", { timeZone: "UTC", month: "short", day: "numeric" }).format(
    new Date(Date.UTC(year, month - 1, date)),
  );
}

/** "30h" under 72 hours, then "4d 6h". */
export function formatDuration(hours: number): string {
  const whole = Math.max(0, Math.floor(hours));
  if (whole < 72) return `${whole}h`;
  return `${Math.floor(whole / 24)}d ${whole % 24}h`;
}

/** "just now", "12m ago", "5h ago", "3d ago", then the short date. */
export function formatRelative(iso: string, timeZone: string, now: Date = new Date()): string {
  const elapsed = now.getTime() - new Date(iso).getTime();
  if (elapsed < MINUTE) return "just now";
  if (elapsed < HOUR) return `${Math.floor(elapsed / MINUTE)}m ago`;
  if (elapsed < 24 * HOUR) return `${Math.floor(elapsed / HOUR)}h ago`;
  if (elapsed < 7 * 24 * HOUR) return `${Math.floor(elapsed / (24 * HOUR))}d ago`;
  return formatDate(iso, timeZone);
}

export type DueState = { overdue: boolean; text: string };

/**
 * Deadline wording (DESIGN_SYSTEM §13): "Due in 3h 12m" (minutes only under 24 h), "Due in 2d 4h",
 * "Overdue 30h" up to 72 h, then "Overdue 4d 6h".
 */
export function formatDue(iso: string, now: Date = new Date()): DueState {
  const delta = new Date(iso).getTime() - now.getTime();
  if (delta >= 0) {
    const minutes = Math.floor(delta / MINUTE);
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return { overdue: false, text: hours === 0 ? `Due in ${minutes}m` : `Due in ${hours}h ${minutes % 60}m` };
    return { overdue: false, text: `Due in ${Math.floor(hours / 24)}d ${hours % 24}h` };
  }
  return { overdue: true, text: `Overdue ${formatDuration(-delta / HOUR)}` };
}

/** The UTC offset of a zone at an instant, in minutes (e.g. −240 for EDT). */
function zoneOffsetMinutes(at: Date, timeZone: string): number {
  const parts = Object.fromEntries(
    new Intl.DateTimeFormat("en-US", {
      timeZone,
      hourCycle: "h23",
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    })
      .formatToParts(at)
      .map((part) => [part.type, part.value]),
  );
  const asUtc = Date.UTC(+parts.year, +parts.month - 1, +parts.day, +parts.hour, +parts.minute, +parts.second);
  return Math.round((asUtc - at.getTime()) / 60_000);
}

/**
 * The instant at which the wall-clock `date` (`YYYY-MM-DD`) and `time` (`HH:MM`) occur in the
 * store zone. Used by inputs that take store-local times (C-59), never the browser's zone.
 */
export function zonedTimeToUtc(date: string, time: string, timeZone: string): Date {
  const [year, month, day] = date.split("-").map(Number);
  const [hour, minute] = time.split(":").map(Number);
  const wall = Date.UTC(year, month - 1, day, hour, minute);
  let guess = wall - zoneOffsetMinutes(new Date(wall), timeZone) * 60_000;
  // A second pass corrects guesses that land on the other side of a DST change.
  guess = wall - zoneOffsetMinutes(new Date(guess), timeZone) * 60_000;
  return new Date(guess);
}

/** `{ date: "YYYY-MM-DD", time: "HH:MM" }` of an instant in the store zone, for input defaults. */
export function utcToZonedInputs(iso: string, timeZone: string): { date: string; time: string } {
  const at = new Date(iso);
  const time = new Intl.DateTimeFormat("en-GB", { timeZone, hour: "2-digit", minute: "2-digit", hourCycle: "h23" }).format(at);
  return { date: localDateKey(at, timeZone), time };
}

/** Midnight in the store zone, `daysBack` store-local days before today (BR-501). */
export function storeMidnight(now: Date, timeZone: string, daysBack: number): Date {
  const [year, month, day] = localDateKey(now, timeZone).split("-").map(Number);
  const start = new Date(Date.UTC(year, month - 1, day - daysBack));
  return zonedTimeToUtc(start.toISOString().slice(0, 10), "00:00", timeZone);
}
