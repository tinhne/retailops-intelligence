import { z } from "zod";

import type { PriorityWeights, StoreSettings, StoreSettingsUpdate } from "@/lib/api/admin-api";
import { formatMoney } from "@/lib/format/number";

// Store settings form model (SCREEN_SPECIFICATIONS S-16). Limits mirror `StoreSettingsUpdate` and
// `PriorityWeights` in apps/api/app/domains/identity/store_schemas.py; the UI adds no rule the
// API does not enforce. Defaults are BUSINESS_RULES.md §7 and PRIORITY_MODEL.md, shown as hints.

export type SectionId = "fulfillment" | "inventory" | "exceptions" | "priority";
export type Unit = "hours" | "days" | "minutes" | "factor" | "currency" | "points";

export type SettingField = {
  /** Form field name (flat, so react-hook-form does not nest it). */
  name: string;
  /** Path in the API body and in 422 `loc`, e.g. `priority_weights.severity.HIGH`. */
  path: string;
  label: string;
  helper?: string;
  unit: Unit;
  section: SectionId;
  /** Sub-heading inside the priority model section. */
  group?: string;
  kind: "int" | "decimal";
  min: number;
  max: number;
  /** `exposure_cap` must be greater than 0, not equal to it. */
  minExclusive?: boolean;
  defaultValue: string;
};

const HOURS = { kind: "int", min: 1, max: 8760, unit: "hours" } as const;
const WEIGHT = { kind: "int", min: 0, max: 100, unit: "points", section: "priority" } as const;
const weight = (path: string, label: string, group: string, defaultValue: number, helper?: string): SettingField => ({
  ...WEIGHT,
  name: path.replaceAll(".", "__"),
  path,
  label,
  group,
  helper,
  defaultValue: String(defaultValue),
});

export const SETTING_FIELDS: SettingField[] = [
  {
    ...HOURS,
    name: "fulfillment_sla_hours",
    path: "fulfillment_sla_hours",
    label: "Fulfillment SLA",
    section: "fulfillment",
    defaultValue: "48",
    helper: "Ship-by deadline when the import has none: paid at + this many hours (BR-201).",
  },
  {
    ...HOURS,
    name: "stall_threshold_hours",
    path: "stall_threshold_hours",
    label: "Stalled after",
    section: "fulfillment",
    defaultValue: "12",
    helper: "A paid order not yet processing after this many hours is “stalled” (BR-203).",
  },
  {
    ...HOURS,
    name: "refund_overdue_hours",
    path: "refund_overdue_hours",
    label: "Refund overdue after",
    section: "fulfillment",
    defaultValue: "24",
    helper: "A cancelled, still-paid order becomes “refund pending” after this many hours (BR-206).",
  },
  {
    name: "approaching_reorder_factor",
    path: "approaching_reorder_factor",
    label: "Approaching reorder factor",
    section: "inventory",
    kind: "decimal",
    unit: "factor",
    min: 1,
    max: 3,
    defaultValue: "1.25",
    helper: "Approaching reorder point up to reorder point × this factor (BR §2.5).",
  },
  {
    name: "velocity_window_days",
    path: "velocity_window_days",
    label: "Sales velocity window",
    section: "inventory",
    kind: "int",
    unit: "days",
    min: 7,
    max: 90,
    defaultValue: "28",
    helper: "Days of sales used for average daily units and days of cover (BR-150).",
  },
  {
    ...HOURS,
    name: "reopen_window_hours",
    path: "reopen_window_hours",
    label: "Reopen window",
    section: "exceptions",
    defaultValue: "72",
    helper: "A resolved exception that recurs within this window is reopened instead of recreated.",
  },
  {
    name: "evaluation_interval_minutes",
    path: "evaluation_interval_minutes",
    label: "Analysis interval",
    section: "exceptions",
    kind: "int",
    unit: "minutes",
    min: 5,
    max: 1440,
    defaultValue: "15",
    helper: "How often scheduled analysis runs.",
  },
  {
    name: "exposure_cap",
    path: "exposure_cap",
    label: "Exposure cap",
    section: "priority",
    kind: "decimal",
    unit: "currency",
    min: 0,
    minExclusive: true,
    max: 9_999_999_999.99,
    defaultValue: "5000.00",
    helper: "Value at risk at which the exposure component reaches its maximum.",
  },
  weight("priority_weights.severity.CRITICAL", "Critical", "Severity", 50, "Points for each severity."),
  weight("priority_weights.severity.HIGH", "High", "Severity", 35),
  weight("priority_weights.severity.MEDIUM", "Medium", "Severity", 20),
  weight("priority_weights.severity.LOW", "Low", "Severity", 8),
  weight("priority_weights.affected_orders_per_order", "Per affected order", "Affected orders", 3, "Points per affected order, up to the cap."),
  weight("priority_weights.affected_orders_cap", "Affected orders cap", "Affected orders", 15),
  weight(
    "priority_weights.exposure_cap_points",
    "Exposure points",
    "Value at risk",
    15,
    "Points when value at risk reaches the exposure cap (logarithmic below it).",
  ),
  weight("priority_weights.deadline.overdue", "Overdue", "Deadline", 12, "Points by how close the business deadline is."),
  weight("priority_weights.deadline.within_24h", "Due within 24 h", "Deadline", 8),
  weight("priority_weights.deadline.within_72h", "Due within 72 h", "Deadline", 4),
  weight("priority_weights.age_points_per_day", "Per day unresolved", "Time unresolved", 2, "Points per whole day unresolved, up to the cap."),
  weight("priority_weights.age_cap", "Time unresolved cap", "Time unresolved", 8),
];

export const SECTIONS: Array<{ id: SectionId; title: string }> = [
  { id: "fulfillment", title: "Fulfillment" },
  { id: "inventory", title: "Inventory" },
  { id: "exceptions", title: "Exceptions" },
  { id: "priority", title: "Priority model" },
];

export const MAX_PRIORITY_SCORE = 100;

export type SettingsFormValues = Record<string, string>;

function valueAt(settings: StoreSettings, path: string): unknown {
  return path.split(".").reduce<unknown>((node, key) => (node as Record<string, unknown> | undefined)?.[key], settings);
}

export function toFormValues(settings: StoreSettings): SettingsFormValues {
  return Object.fromEntries(SETTING_FIELDS.map((field) => [field.name, String(valueAt(settings, field.path))]));
}

const WHOLE = /^\d+$/;
// BigInt() rather than `100n` literals: the TypeScript target is ES2017.
const HUNDRED = BigInt(100);
const DECIMAL = /^(\d+)(?:\.(\d{1,2}))?$/;

/** Cents of a decimal string with at most two places, exact (no floating point, BR-503). */
function cents(text: string): bigint | null {
  const match = DECIMAL.exec(text);
  if (!match) return null;
  return BigInt(match[1]) * HUNDRED + BigInt((match[2] ?? "").padEnd(2, "0"));
}

const toCents = (value: number) => BigInt(Math.round(value * 100));
const integer = (value: number) => value.toLocaleString("en-US");
const decimal = (value: number) => value.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

/** The validation message for one input, or `null` when it is valid. */
export function fieldProblem(field: SettingField, raw: string): string | null {
  const text = raw.trim();
  if (text === "") return "Enter a value.";
  if (field.kind === "int") {
    if (!WHOLE.test(text)) return "Enter a whole number.";
    const value = Number(text);
    if (value < field.min || value > field.max) return `Enter a whole number from ${integer(field.min)} to ${integer(field.max)}.`;
    return null;
  }
  const amount = cents(text);
  if (amount === null) return "Enter a number with at most 2 decimal places.";
  const tooLow = field.minExclusive ? amount <= toCents(field.min) : amount < toCents(field.min);
  if (tooLow || amount > toCents(field.max)) {
    return field.minExclusive
      ? `Enter an amount above ${decimal(field.min)} and at most ${decimal(field.max)}.`
      : `Enter a value from ${decimal(field.min)} to ${decimal(field.max)}.`;
  }
  return null;
}

export const settingsSchema = z.object(
  Object.fromEntries(
    SETTING_FIELDS.map((field) => [
      field.name,
      z.string().superRefine((raw, ctx) => {
        const problem = fieldProblem(field, raw);
        if (problem) ctx.addIssue({ code: "custom", message: problem });
      }),
    ]),
  ),
);

/** The canonical text of a valid value ("1.3" → "1.30", "036" → "36"), for comparisons and display. */
export function normalise(field: SettingField, raw: string): string {
  const text = raw.trim();
  if (fieldProblem(field, text)) return text;
  if (field.kind === "int") return String(Number(text));
  const amount = cents(text) as bigint;
  const whole = amount / HUNDRED;
  const fraction = (amount % HUNDRED).toString().padStart(2, "0");
  return `${whole}.${fraction}`;
}

export type SettingChange = { field: SettingField; from: string; to: string };

/** Fields whose value differs from the saved settings. Invalid input counts as a change. */
export function changedFields(values: SettingsFormValues, saved: StoreSettings): SettingChange[] {
  const before = toFormValues(saved);
  return SETTING_FIELDS.flatMap((field) => {
    const from = normalise(field, before[field.name] ?? "");
    const to = normalise(field, values[field.name] ?? "");
    return from === to ? [] : [{ field, from, to }];
  });
}

/**
 * The PATCH body: only the changed settings (S-16). The API takes `priority_weights` as one
 * object, so any weight change sends all weights. Integers go as JSON numbers (the API is
 * strict), decimals as strings (BR-503).
 */
export function buildUpdate(values: SettingsFormValues, changes: SettingChange[]): StoreSettingsUpdate {
  const body: Record<string, unknown> = {};
  const parsed = (field: SettingField) => {
    const text = normalise(field, values[field.name] ?? "");
    return field.kind === "int" ? Number(text) : text;
  };
  for (const { field } of changes) {
    if (!field.path.startsWith("priority_weights.")) body[field.path] = parsed(field);
  }
  if (changes.some(({ field }) => field.path.startsWith("priority_weights."))) {
    const weights: Record<string, unknown> = {};
    for (const field of SETTING_FIELDS.filter((candidate) => candidate.path.startsWith("priority_weights."))) {
      const keys = field.path.split(".").slice(1);
      let node = weights;
      for (const key of keys.slice(0, -1)) node = (node[key] ??= {}) as Record<string, unknown>;
      node[keys[keys.length - 1]] = parsed(field);
    }
    body.priority_weights = weights as PriorityWeights;
  }
  return body as StoreSettingsUpdate;
}

/**
 * The highest score the weights allow, the same sum as `PriorityWeights.max_possible_score`:
 * highest severity + affected-orders cap + exposure points + highest deadline + age cap.
 * `null` while any of those inputs is invalid (its own field error explains why).
 */
export function maxPossibleScore(values: SettingsFormValues): number | null {
  const read = (path: string) => {
    const field = SETTING_FIELDS.find((candidate) => candidate.path === path) as SettingField;
    const raw = values[field.name] ?? "";
    return fieldProblem(field, raw) ? null : Number(raw.trim());
  };
  const parts = [
    ["CRITICAL", "HIGH", "MEDIUM", "LOW"].map((key) => read(`priority_weights.severity.${key}`)),
    [read("priority_weights.affected_orders_cap")],
    [read("priority_weights.exposure_cap_points")],
    ["overdue", "within_24h", "within_72h"].map((key) => read(`priority_weights.deadline.${key}`)),
    [read("priority_weights.age_cap")],
  ];
  if (parts.some((group) => group.some((value) => value === null))) return null;
  return parts.reduce((sum, group) => sum + Math.max(...(group as number[])), 0);
}

/** "48 h", "28 days", "1.25×", "$5,000.00", "50 points". */
export function formatSetting(field: SettingField, value: string, currency: string): string {
  switch (field.unit) {
    case "hours":
      return `${integer(Number(value))} h`;
    case "days":
      return `${integer(Number(value))} days`;
    case "minutes":
      return `${integer(Number(value))} min`;
    case "factor":
      return `${value}×`;
    case "currency":
      return formatMoney(value, currency);
    case "points":
      return `${value} ${value === "1" ? "point" : "points"}`;
  }
}

export const unitSuffix = (unit: Unit, currency: string): string =>
  ({ hours: "h", days: "days", minutes: "min", factor: "×", currency, points: "pts" })[unit];

export const unitSpoken = (unit: Unit, currency: string): string =>
  ({ hours: "hours", days: "days", minutes: "minutes", factor: "times", currency, points: "points" })[unit];

/** A stable signature of the saved values, to notice changes made by someone else. */
export function settingsSignature(settings: StoreSettings): string {
  return JSON.stringify(toFormValues(settings));
}

export const FIELD_BY_PATH = new Map(SETTING_FIELDS.map((field) => [field.path, field]));
