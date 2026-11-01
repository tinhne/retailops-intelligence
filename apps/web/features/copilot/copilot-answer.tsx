"use client";

import { ChevronDown, ChevronRight, Info, Sigma } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import type { AnswerMeta, CopilotReference, StructuredAnswer } from "@/lib/api/copilot-api";
import type { Permission } from "@/lib/api/auth";
import { formatDate, formatDateTimeShort, zoneGenericName } from "@/lib/format/datetime";
import { formatQuantity } from "@/lib/format/number";
import { copilotToolLabels, toolCallStatusLabels } from "@/lib/status-maps";
import { useStore } from "@/lib/store/store-context";
import { cn } from "@/lib/utils";

const TARGETS: Partial<Record<CopilotReference["type"], { segment: string; permission: Permission }>> = {
  exception: { segment: "exceptions", permission: "exceptions.read" },
  order: { segment: "orders", permission: "orders.read" },
  product: { segment: "products", permission: "catalog.read" },
  import: { segment: "imports", permission: "imports.read" },
};

/** "EXC-1042 · Oversold: …" → "EXC-1042": chips show the record's code, the full label is its title. */
export const chipLabel = (label: string) => label.split(" · ")[0];

/** A record the answer cites (C-81): a link when the person may open it, plain text otherwise. */
export function ReferenceChip({ reference }: { reference: CopilotReference }) {
  const store = useStore();
  const target = TARGETS[reference.type];
  // Truncated so a long label can never widen a narrow column.
  const className = "inline-block max-w-full truncate rounded-sm border bg-surface-subtle px-1.5 py-0.5 align-middle font-mono text-xs";
  const text = chipLabel(reference.label);
  const title = text === reference.label ? undefined : reference.label;
  if (target && store.permissions.has(target.permission)) {
    return (
      <Link href={`/s/${store.id}/${target.segment}/${reference.id}`} title={title} className={cn(className, "text-link hover:underline")}>
        {text}
      </Link>
    );
  }
  return (
    <span title={title} className={cn(className, "text-muted-foreground")}>
      {text}
    </span>
  );
}

function Refs({ refs, byKey }: { refs: string[]; byKey: Map<string, CopilotReference> }) {
  const chips = refs.map((ref) => byKey.get(ref)).filter((ref): ref is CopilotReference => ref !== undefined && ref.type !== "aggregate");
  if (chips.length === 0) return null;
  return (
    <span className="ml-1 inline-flex max-w-full flex-wrap gap-1 align-middle">
      {chips.map((ref) => (
        <ReferenceChip key={`${ref.type}:${ref.id}`} reference={ref} />
      ))}
    </span>
  );
}

function SectionTitle({ children }: { children: React.ReactNode }) {
  return <h4 className="text-xs font-medium tracking-wide text-muted-foreground uppercase">{children}</h4>;
}

function MetricRow({ metric, byKey }: { metric: StructuredAnswer["metrics"][number]; byKey: Map<string, CopilotReference> }) {
  const [showFormula, setShowFormula] = useState(false);
  return (
    <div className="flex flex-col gap-1 border-b py-1.5 last:border-b-0">
      <div className="flex items-baseline justify-between gap-3">
        <dt className="text-body">
          {metric.label}
          <Refs refs={metric.refs} byKey={byKey} />
        </dt>
        <dd className="flex items-center gap-1 text-body font-medium tabular-nums">
          {metric.value}
          {metric.unit ? <span className="font-normal text-muted-foreground">{metric.unit}</span> : null}
          {metric.formula ? (
            <button
              type="button"
              aria-pressed={showFormula}
              aria-label={`${showFormula ? "Hide" : "Show"} the formula for ${metric.label}`}
              onClick={() => setShowFormula(!showFormula)}
              className={cn("rounded-sm p-0.5 text-muted-foreground hover:bg-accent", showFormula && "bg-accent text-foreground")}
            >
              <Sigma aria-hidden className="size-3.5" />
            </button>
          ) : null}
        </dd>
      </div>
      {showFormula && metric.formula ? <code className="relative block overflow-x-auto font-mono text-mono whitespace-pre text-muted-foreground">{metric.formula}</code> : null}
    </div>
  );
}

/** "Data used: 3 read-only tools" with each call's rows, duration and status (C-82). */
function ToolCalls({ meta }: { meta: AnswerMeta }) {
  const [open, setOpen] = useState(false);
  if (meta.tool_calls.length === 0) return null;
  return (
    <Collapsible open={open} onOpenChange={setOpen}>
      <CollapsibleTrigger className="inline-flex items-center gap-1 text-xs text-link hover:underline">
        {open ? <ChevronDown aria-hidden className="size-3.5" /> : <ChevronRight aria-hidden className="size-3.5" />}
        Data used: {meta.tool_calls.length} read-only {meta.tool_calls.length === 1 ? "tool" : "tools"}
      </CollapsibleTrigger>
      <CollapsibleContent>
        <ul className="mt-1 flex flex-col gap-0.5 text-xs text-muted-foreground">
          {meta.tool_calls.map((call, index) => (
            <li key={`${call.tool_name}-${index}`} className={cn(call.status !== "SUCCESS" && "text-tone-warning-fg")}>
              {copilotToolLabels[call.tool_name] ?? call.tool_name}
              {call.row_count !== null ? ` · ${formatQuantity(call.row_count)} ${call.row_count === 1 ? "row" : "rows"}` : ""}
              {call.duration_ms !== null ? ` · ${formatQuantity(call.duration_ms)} ms` : ""} · {toolCallStatusLabels[call.status]}
            </li>
          ))}
        </ul>
      </CollapsibleContent>
    </Collapsible>
  );
}

/** Who produced the answer, from which data window and when (S-14 "Provenance"). */
export function Provenance({ answer, meta, createdAt }: { answer: Pick<StructuredAnswer, "generated_by" | "data_window">; meta: AnswerMeta | null; createdAt: string }) {
  const store = useStore();
  const zone = zoneGenericName(store.timezone);
  const by =
    answer.generated_by === "deterministic"
      ? "Generated by the deterministic engine"
      : `Generated by LLM provider · ${answer.generated_by.replace(/^llm:/, "")}`;
  const window = answer.data_window.from
    ? `Data ${formatDate(answer.data_window.from, store.timezone).replace(/, \d{4}$/, "")} – ${formatDate(answer.data_window.to, store.timezone)} (${zone})`
    : `Data as of ${formatDateTimeShort(answer.data_window.to, store.timezone)}`;
  const reused = meta?.cache.hit && meta.cache.generated_at ? `Generated ${formatDateTimeShort(meta.cache.generated_at, store.timezone)} (reused)` : null;
  return (
    <div className="flex flex-col gap-1 border-t pt-2 text-xs text-muted-foreground">
      <p>
        {by} · {window} · {reused ?? formatDateTimeShort(createdAt, store.timezone)}
      </p>
      {meta ? <ToolCalls meta={meta} /> : null}
    </div>
  );
}

/**
 * A structured copilot answer (COMPONENT_INVENTORY C-80): summary, facts, metrics, estimates,
 * recommendations, limitations (always), references and provenance, in that order. Every fact
 * and metric carries the references it rests on.
 */
export function CopilotAnswer({
  answer,
  meta,
  createdAt,
  variant = "full",
}: {
  answer: StructuredAnswer;
  meta: AnswerMeta | null;
  createdAt: string;
  variant?: "full" | "compact";
}) {
  const byKey = new Map(answer.references.map((ref) => [`${ref.type}:${ref.id}`, ref] as const));
  const visibleRefs = answer.references.filter((ref) => ref.type !== "aggregate");
  return (
    <div className="flex min-w-0 flex-col gap-3">
      {meta?.fallback.used && meta.fallback.notice ? (
        <Alert tone="info">
          <Info aria-hidden />
          <AlertDescription>
            <p>{meta.fallback.notice}</p>
          </AlertDescription>
        </Alert>
      ) : null}
      {answer.summary ? <p className="text-body whitespace-pre-line">{answer.summary}</p> : null}

      {answer.facts.length ? (
        <section className="flex flex-col gap-1">
          <SectionTitle>Facts</SectionTitle>
          <ul className="flex list-disc flex-col gap-1 pl-5 text-body">
            {answer.facts.map((fact, index) => (
              <li key={index}>
                {fact.text}
                <Refs refs={fact.refs} byKey={byKey} />
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      {answer.metrics.length ? (
        <section className="flex flex-col gap-1">
          <SectionTitle>Metrics</SectionTitle>
          <dl>
            {answer.metrics.map((metric, index) => (
              <MetricRow key={index} metric={metric} byKey={byKey} />
            ))}
          </dl>
        </section>
      ) : null}

      {answer.estimates.length ? (
        <section className="flex flex-col gap-1">
          <SectionTitle>Estimates</SectionTitle>
          <ul className="flex flex-col gap-1 text-body">
            {answer.estimates.map((estimate, index) => (
              <li key={index}>
                <span className="mr-1 rounded-sm border px-1 text-xs text-muted-foreground">est.</span>
                {estimate.text}
                <span className="block text-sm text-muted-foreground">{estimate.basis}</span>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      {answer.recommendations.length ? (
        <section className="flex flex-col gap-1">
          <SectionTitle>Recommendations</SectionTitle>
          {variant === "full" ? (
            <p className="text-xs text-muted-foreground">Suggestions from the copilot. Rule-based recommended actions are shown on each exception.</p>
          ) : null}
          <ol className="flex list-decimal flex-col gap-1 pl-5 text-body">
            {answer.recommendations.map((item, index) => (
              <li key={index}>
                {item.text}
                {item.rationale ? <span className="block text-sm text-muted-foreground">{item.rationale}</span> : null}
              </li>
            ))}
          </ol>
        </section>
      ) : null}

      <section className="flex flex-col gap-1">
        <SectionTitle>Limitations</SectionTitle>
        {answer.limitations.length ? (
          <ul className="flex list-disc flex-col gap-0.5 pl-5 text-sm text-muted-foreground">
            {answer.limitations.map((limitation, index) => (
              <li key={index}>{limitation}</li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-muted-foreground">No specific limitations reported.</p>
        )}
      </section>

      {visibleRefs.length ? (
        <section className="flex flex-col gap-1">
          <SectionTitle>References</SectionTitle>
          <div className="flex flex-wrap gap-1">
            {visibleRefs.map((ref) => (
              <ReferenceChip key={`${ref.type}:${ref.id}`} reference={ref} />
            ))}
          </div>
        </section>
      ) : null}

      <Provenance answer={answer} meta={meta} createdAt={createdAt} />
    </div>
  );
}
