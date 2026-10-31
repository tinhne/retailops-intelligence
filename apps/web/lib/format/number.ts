// Number formatters (DESIGN_SYSTEM §13). Locale is fixed to en-US in v1. Money arrives from the
// API as a decimal string (BR-503) and is formatted from the string, never converted with
// parseFloat for arithmetic.

const MINUS = "−";

/** Swaps the ASCII hyphen-minus for U+2212, the typographic minus used in the product. */
function typographicMinus(text: string): string {
  return text.replace("-", MINUS);
}

const moneyFormatters = new Map<string, Intl.NumberFormat>();

function moneyFormatter(currency: string): Intl.NumberFormat {
  let formatter = moneyFormatters.get(currency);
  if (!formatter) {
    formatter = new Intl.NumberFormat("en-US", {
      style: "currency",
      currency,
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });
    moneyFormatters.set(currency, formatter);
  }
  return formatter;
}

/** "$1,234.50", "−$12.40". Accepts the API's decimal string as is. */
export function formatMoney(value: string, currency: string): string {
  return typographicMinus(moneyFormatter(currency).format(value as Intl.StringNumericLiteral));
}

/** The same value with an ASCII minus, for `aria-label` (some screen readers skip U+2212). */
export function formatMoneyForSpeech(value: string, currency: string): string {
  return moneyFormatter(currency).format(value as Intl.StringNumericLiteral);
}

/** "$12.4K", "$1.2M". Chart axis ticks only (§13). */
export function formatMoneyCompact(value: number, currency: string): string {
  return typographicMinus(
    new Intl.NumberFormat("en-US", {
      style: "currency",
      currency,
      notation: "compact",
      maximumFractionDigits: 1,
    }).format(value),
  );
}

const quantityFormatter = new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 });

/** "1,240", "−4". */
export function formatQuantity(value: number): string {
  return typographicMinus(quantityFormatter.format(value));
}

/** "1 row", "14 rows". */
export function formatCount(value: number, singular: string, plural = `${singular}s`): string {
  return `${formatQuantity(value)} ${value === 1 ? singular : plural}`;
}

/**
 * A percentage the API already computed, such as `on_time_rate_pct` ("94.1"): one decimal,
 * none at 100 or above.
 */
export function formatPercentValue(value: string): string {
  const numeric = Number(value);
  const digits = numeric >= 100 ? 0 : 1;
  return `${typographicMinus(numeric.toFixed(digits))}%`;
}

/** "1.8 MB" (base 1,000, one decimal). */
export function formatBytes(bytes: number): string {
  const units = ["B", "KB", "MB", "GB"];
  let value = bytes;
  let unit = 0;
  while (value >= 1000 && unit < units.length - 1) {
    value /= 1000;
    unit += 1;
  }
  return unit === 0 ? `${value} B` : `${value.toFixed(1)} ${units[unit]}`;
}

/** Ledger deltas are always signed: "+40", "−3", "0" (DESIGN_SYSTEM §13). */
export function formatDelta(value: number): string {
  if (value === 0) return "0";
  return value > 0 ? `+${formatQuantity(value)}` : formatQuantity(value);
}
