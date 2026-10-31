"use client";

import { Info, ListChecks } from "lucide-react";

import { DateTime, Money, NoValue } from "@/components/data/values";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import type { ExceptionDetail } from "@/lib/api/exceptions-api";
import { formatQuantity } from "@/lib/format/number";
import { useStore } from "@/lib/store/store-context";
import { cn } from "@/lib/utils";

// The deterministic half of the investigation page (S-04): rule-authored text and numbers only.
// Every value comes from the stored evidence, calculation and priority breakdown; the UI only
// formats. JSON shapes per SCREEN_SPECIFICATIONS §0.4.

type Json = string | number | boolean | null | Json[] | { [key: string]: Json };

const ISO_DATETIME = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/;
const DECIMAL = /^-?\d+(\.\d+)?$/;
const MONEY_KEY = /(amount|value_at_risk|price|total|exposure|gmv)/;

/** "unit_price" → "Unit price". Keys come from rule code, so this is only for display. */
export function humanizeKey(key: string): string {
  const text = key.replace(/_/g, " ").trim();
  return text.charAt(0).toUpperCase() + text.slice(1);
}

/**
 * Formats a JSON value by its type: money strings in the store currency, ISO timestamps in the
 * store zone, negative numbers in danger tone with a typographic minus.
 */
export function AutoValue({ value, keyName, unit }: { value: Json | undefined; keyName?: string; unit?: string | null }) {
  const store = useStore();
  if (value === null || value === undefined) return <NoValue />;
  if (typeof value === "boolean") return <span>{value ? "Yes" : "No"}</span>;
  if (typeof value === "number") {
    return (
      <span className={cn("tabular-nums", value < 0 && "text-tone-danger-fg")}>
        {formatQuantity(value)}
        {unit && unit !== store.currency ? ` ${unit}` : null}
      </span>
    );
  }
  if (typeof value === "string") {
    if (ISO_DATETIME.test(value)) return <DateTime value={value} />;
    if (DECIMAL.test(value) && (unit === store.currency || (keyName && MONEY_KEY.test(keyName)))) {
      return <Money value={value} />;
    }
    return <span>{value}</span>;
  }
  return <code className="font-mono text-mono break-all">{JSON.stringify(value)}</code>;
}

type Component = { key: string; label: string; points: number; max_points: number; explanation: string };
type Breakdown = {
  components?: Component[];
  total?: number;
  uncapped_total?: number;
  band?: string;
  due?: { basis?: string; explanation?: string };
};

const BAND_THRESHOLD: Record<string, string> = { P1: "≥ 70", P2: "50–69", P3: "30–49", P4: "< 30" };

export function SectionCard({ id, title, aside, children }: { id: string; title: string; aside?: React.ReactNode; children: React.ReactNode }) {
  return (
    <section id={id} aria-labelledby={`${id}-title`} className="scroll-mt-20 rounded-lg border bg-card p-4 md:p-5">
      <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
        <h2 id={`${id}-title`} className="text-title-sm">
          {title}
        </h2>
        {aside ? <span className="text-sm text-muted-foreground">{aside}</span> : null}
      </div>
      {children}
    </section>
  );
}

export function RecommendedAction({ exception }: { exception: ExceptionDetail }) {
  return (
    <section aria-labelledby="recommended-title" className="flex gap-3 rounded-lg border border-tone-neutral-border bg-tone-neutral-bg p-4">
      <ListChecks aria-hidden className="mt-0.5 size-5 shrink-0 text-tone-neutral-fg" />
      <div className="flex flex-col gap-1">
        <h2 id="recommended-title" className="text-title-sm">
          Recommended action <span className="font-normal text-muted-foreground">· rule {exception.rule_id}</span>
        </h2>
        <p className="text-prose">{exception.recommended_action}</p>
      </div>
    </section>
  );
}

/** How the priority score was computed (C-50): every component, its points and why. */
export function PriorityBreakdown({ exception }: { exception: ExceptionDetail }) {
  const breakdown = exception.priority_breakdown as Breakdown;
  const components = breakdown.components ?? [];
  const total = breakdown.total ?? exception.priority_score;
  const band = breakdown.band ?? exception.priority_band;

  return (
    <SectionCard
      id="priority"
      title="Why this priority"
      aside={`${total} / 100 · ${band} (${BAND_THRESHOLD[band] ?? ""})${(breakdown.uncapped_total ?? 0) > 100 ? " · capped at 100" : ""}`}
    >
      {components.length === 0 ? (
        <p className="text-body text-muted-foreground">Priority breakdown unavailable for this exception.</p>
      ) : (
        <table className="w-full text-body">
          <caption className="sr-only">Why this priority</caption>
          <thead className="sr-only">
            <tr>
              <th scope="col">Component</th>
              <th scope="col">Explanation</th>
              <th scope="col">Points</th>
            </tr>
          </thead>
          <tbody>
            {components.map((component) => (
              <tr key={component.key} className="border-t first:border-t-0">
                <th scope="row" className="w-36 py-2 pr-3 text-left align-top font-medium">
                  {component.label}
                </th>
                <td className="py-2 pr-3 align-top text-muted-foreground">{component.explanation}</td>
                <td className="w-40 py-2 align-top">
                  <div className="flex items-center justify-end gap-2">
                    <span className="tabular-nums whitespace-nowrap">
                      {component.points} / {component.max_points}
                    </span>
                    <span aria-hidden className="hidden h-1.5 w-16 overflow-hidden rounded-full bg-priority-bar-empty min-[400px]:block">
                      <span
                        className="block h-full bg-chart-1"
                        style={{ width: `${component.max_points ? (100 * component.points) / component.max_points : 0}%` }}
                      />
                    </span>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <div className="mt-3 flex flex-col gap-1 border-t pt-3 text-sm text-muted-foreground">
        <p>
          Due <DateTime value={exception.due_at} />
          {exception.due_at_overridden ? ": set manually." : breakdown.due?.explanation ? `: ${breakdown.due.explanation}` : "."}
        </p>
        <p className="flex items-center gap-1">
          Priority ranks work; it does not measure money lost.
          <Popover>
            <PopoverTrigger asChild>
              <button type="button" aria-label="About the priority formula" className="inline-flex size-6 items-center justify-center rounded-md hover:bg-accent">
                <Info aria-hidden className="size-4" />
              </button>
            </PopoverTrigger>
            <PopoverContent className="w-80 text-sm">
              <p className="font-mono text-mono">min(100, S + A + E + D + T)</p>
              {/* The four limitations, as stated in PRIORITY_MODEL "Limitations". */}
              <ul className="mt-2 list-disc space-y-1 pl-4 text-muted-foreground">
                <li>The score is a heuristic. The default weights have not been validated with real operators; each team should tune them.</li>
                <li>Value at risk is the gross value of order lines at risk. It ignores margin, whether customers accept a delay, and how likely the risk is.</li>
                <li>Severity thresholds use calendar hours, not business hours.</li>
                <li>Customer impact (repeat customers, complaints) is not modelled.</li>
              </ul>
            </PopoverContent>
          </Popover>
        </p>
      </div>
    </SectionCard>
  );
}

type Calculation = { formulas?: string[]; inputs?: Record<string, Json>; outputs?: Record<string, Json>; steps?: Array<Record<string, Json>> };

function KeyValues({ title, values }: { title: string; values: Record<string, Json> }) {
  const entries = Object.entries(values);
  if (entries.length === 0) return null;
  return (
    <div className="flex flex-col gap-1">
      <h3 className="text-xs text-muted-foreground">{title}</h3>
      <dl className="grid grid-cols-[minmax(0,auto)_1fr] gap-x-4 gap-y-1 text-body">
        {entries.map(([key, value]) => (
          <div key={key} className="contents">
            <dt className="text-muted-foreground">{humanizeKey(key)}</dt>
            <dd>
              <AutoValue value={value} keyName={key} />
            </dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

/** A generic table for rule-specific rows: the columns are the row keys (C-51, C-53). */
export function RecordTable({ caption, rows, limit = 50 }: { caption: string; rows: Array<Record<string, Json>>; limit?: number }) {
  const columns = [...new Set(rows.flatMap((row) => Object.keys(row)))].filter(
    (key) => !key.endsWith("_id") && key !== "source",
  );
  const shown = rows.slice(0, limit);
  return (
    <div className="flex flex-col gap-2">
      <div className="relative overflow-x-auto rounded-md border">
        <table className="w-full text-sm">
          <caption className="sr-only">{caption}</caption>
          <thead className="bg-surface-subtle">
            <tr>
              {columns.map((column, index) => (
                <th
                  key={column}
                  scope="col"
                  className={cn(
                    "h-8 border-b px-3 text-left text-xs font-medium whitespace-nowrap text-muted-foreground",
                    index === 0 && "sticky left-0 bg-surface-subtle",
                  )}
                >
                  {humanizeKey(column)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {shown.map((row, rowIndex) => (
              <tr key={rowIndex} className="border-b last:border-b-0">
                {columns.map((column, index) => (
                  <td key={column} className={cn("h-8 px-3 whitespace-nowrap", index === 0 && "sticky left-0 bg-card font-medium")}>
                    <AutoValue value={row[column]} keyName={column} />
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {rows.length > limit ? (
        <p className="text-sm text-muted-foreground">
          Showing {limit} of {rows.length} rows.
        </p>
      ) : null}
    </div>
  );
}

export function CalculationBlock({ exception }: { exception: ExceptionDetail }) {
  const calculation = exception.calculation as Calculation;
  const asOf = (exception.priority_breakdown as { as_of?: string }).as_of;
  return (
    <SectionCard id="calculation" title="How this was detected" aside={asOf ? <>As of <DateTime value={asOf} /></> : undefined}>
      <div className="flex flex-col gap-4">
        {calculation.formulas?.length ? (
          <ol className="flex flex-col gap-1 rounded-md bg-surface-subtle p-3 font-mono text-mono">
            {calculation.formulas.map((formula) => (
              <li key={formula}>{formula}</li>
            ))}
          </ol>
        ) : null}
        <div className="grid gap-4 md:grid-cols-2">
          <KeyValues title="Inputs" values={calculation.inputs ?? {}} />
          <KeyValues title="Outputs" values={calculation.outputs ?? {}} />
        </div>
        {calculation.steps?.length ? <RecordTable caption="Calculation steps" rows={calculation.steps} /> : null}
      </div>
    </SectionCard>
  );
}

type Fact = { key: string; label: string; value: Json; unit: string | null; estimate: boolean; volatile: boolean; source: { type: string; label: string } | null };
type Evidence = { facts?: Fact[]; records?: Record<string, Array<Record<string, Json>>>; notes?: string[] };

export function EvidenceTable({ exception }: { exception: ExceptionDetail }) {
  const evidence = exception.evidence as Evidence;
  const facts = evidence.facts ?? [];
  const otherRecords = Object.entries(evidence.records ?? {}).filter(([group]) => group !== "affected_orders");
  return (
    <SectionCard id="evidence" title="Evidence">
      {facts.length === 0 ? (
        <p className="text-body text-muted-foreground">Evidence unavailable for this exception.</p>
      ) : (
        <div className="relative overflow-x-auto">
          <table className="w-full text-body">
            <caption className="sr-only">Evidence</caption>
            <thead>
              <tr className="text-xs text-muted-foreground">
                <th scope="col" className="pb-2 text-left font-medium">Fact</th>
                <th scope="col" className="pb-2 text-left font-medium">Value</th>
                <th scope="col" className="pb-2 text-left font-medium">Source</th>
              </tr>
            </thead>
            <tbody>
              {facts.map((fact) => (
                <tr key={fact.key} className="border-t">
                  <th scope="row" className="py-2 pr-4 text-left align-top font-normal">
                    {fact.label}
                  </th>
                  <td className="py-2 pr-4 align-top whitespace-nowrap">
                    <AutoValue value={fact.value} keyName={fact.key} unit={fact.unit} />
                    {fact.estimate ? <span className="ml-1 text-xs text-muted-foreground">est.</span> : null}
                    {fact.volatile ? <span className="ml-1 text-xs text-muted-foreground" title="Changes over time">(changes over time)</span> : null}
                  </td>
                  <td className="py-2 align-top text-sm text-muted-foreground">{fact.source ? fact.source.label : "Calculated"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {otherRecords.map(([group, rows]) => (
        <div key={group} className="mt-4 flex flex-col gap-2">
          <h3 className="text-title-sm">{humanizeKey(group)}</h3>
          <RecordTable caption={humanizeKey(group)} rows={rows} />
        </div>
      ))}
      {evidence.notes?.length ? (
        <ul className="mt-3 list-disc space-y-1 pl-5 text-sm text-muted-foreground">
          {evidence.notes.map((note) => (
            <li key={note}>{note}</li>
          ))}
        </ul>
      ) : null}
    </SectionCard>
  );
}

const AFFECTED_COLUMNS = ["order_number", "paid_at", "ship_by", "quantity", "covered_quantity", "uncovered_quantity", "value_at_risk"];

/** Orders the condition puts at risk (C-53), from the evidence records. */
export function AffectedOrders({ exception }: { exception: ExceptionDetail }) {
  const rows = ((exception.evidence as Evidence).records?.affected_orders ?? []).map((row) =>
    Object.fromEntries(
      [...AFFECTED_COLUMNS.filter((key) => key in row), ...Object.keys(row).filter((key) => !AFFECTED_COLUMNS.includes(key))].map((key) => [key, row[key]]),
    ),
  );
  if (exception.category !== "INVENTORY" && rows.length === 0) return null;
  return (
    <SectionCard id="affected" title={`Affected orders (${rows.length})`}>
      {rows.length === 0 ? (
        <p className="text-body text-muted-foreground">
          No orders are affected. Out-of-stock and below-reorder-point exceptions don&apos;t block existing orders (value at risk{" "}
          <Money value="0" />
          ).
        </p>
      ) : (
        <RecordTable caption="Affected orders" rows={rows} />
      )}
    </SectionCard>
  );
}
