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
