"use client";

import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowRightLeft,
  CalendarClock,
  CircleCheck,
  CircleDot,
  CornerUpRight,
  FileSearch,
  Gauge,
  MessageSquare,
  RotateCcw,
  ScanSearch,
  Sparkles,
  UserRound,
  type LucideIcon,
} from "lucide-react";
import { useRef, useState } from "react";

import { DateTime } from "@/components/data/values";
import { ErrorState } from "@/components/states/error-state";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { copilotApi } from "@/lib/api/copilot-api";
import { isApiError, userMessage } from "@/lib/api/errors";
import { exceptionKeys, exceptionsApi, type ExceptionDetail, type ExceptionEvent, type ExceptionNote } from "@/lib/api/exceptions-api";
import { formatDateTime } from "@/lib/format/datetime";
import {
  dismissalReasonLabels,
  exceptionStatusLabels,
  exceptionTypeLabels,
  resolutionCodeLabels,
  severityMeta,
  type DismissalReason,
  type ExceptionStatus,
  type ExceptionType,
  type ResolutionCode,
  type Severity,
} from "@/lib/status-maps";
import { useStore } from "@/lib/store/store-context";
import { cn } from "@/lib/utils";

import { gateFor } from "./actions";
import { useExceptionCommand } from "./use-exception-command";

const EVENTS_PAGE = 50;
const NOTE_MAX = 4000;

export type TimelineItem = {
  id: string;
  kind: "event" | "note";
  occurredAt: string;
  icon: LucideIcon;
  title: string;
  body?: string;
  badge?: string;
};

type Payload = Record<string, unknown>;
const text = (value: unknown) => (typeof value === "string" ? value : undefined);

const REOPEN_REASONS: Record<string, string> = {
  VERIFICATION_FAILED: "verification failed, the condition was still present",
  RECURRED_WITHIN_WINDOW: "the condition came back soon after it was resolved",
  MANUAL: "reopened by hand",
};

/** Timeline copy per event type (SCREEN_SPECIFICATIONS S-04 "Timeline event copy"). */
export function describeEvent(event: ExceptionEvent, names: Map<string, string>, timeZone: string): Omit<TimelineItem, "id" | "kind" | "occurredAt"> {
  const actor = event.actor_type === "SYSTEM" ? "System" : (event.actor?.full_name ?? "Someone");
  const payload = (event.payload ?? {}) as Payload;
  const status = (value: ExceptionStatus | null) => (value ? exceptionStatusLabels[value] : "");
  const when = (value: unknown) => (text(value) ? formatDateTime(text(value) as string, timeZone) : "");

  switch (event.event_type) {
    case "DETECTED":
      return {
        icon: ScanSearch,
        title: "Detected by an evaluation",
        body: text(payload.previous_occurrence_reference)
          ? `This condition occurred before as ${text(payload.previous_occurrence_reference)}.`
          : undefined,
      };
    case "EVIDENCE_UPDATED": {
      const changed = Array.isArray(payload.changed_facts) ? (payload.changed_facts as string[]) : [];
      return {
        icon: FileSearch,
        title: "Evidence updated",
        body: changed.length ? `Changed: ${changed.map((key) => key.replace(/_/g, " ")).join(", ")}` : undefined,
      };
    }
    case "SEVERITY_CHANGED": {
      const from = severityMeta[payload.from as Severity]?.label ?? String(payload.from ?? "");
      const to = severityMeta[payload.to as Severity]?.label ?? String(payload.to ?? "");
      return { icon: Gauge, title: `Severity changed from ${from} to ${to}` };
    }
    case "STATUS_CHANGED": {
      const details: string[] = [];
      if (text(payload.resolution_code)) details.push(resolutionCodeLabels[payload.resolution_code as ResolutionCode] ?? String(payload.resolution_code));
      if (text(payload.dismissal_reason)) details.push(dismissalReasonLabels[payload.dismissal_reason as DismissalReason]?.label ?? String(payload.dismissal_reason));
      const note = text(payload.resolution_note) ?? text(payload.note);
      return {
        icon: event.to_status === "RESOLVED" ? CircleCheck : CircleDot,
        title: `${actor} changed status from ${status(event.from_status)} to ${status(event.to_status)}`,
        body: [details.join(" · "), note].filter(Boolean).join(": ") || undefined,
      };
    }
    case "ASSIGNED": {
      const assignee = names.get(String(payload.assignee_id)) ?? "a team member";
      if (payload.reason === "CLAIMED") return { icon: UserRound, title: `${actor} claimed this exception` };
      if (payload.reason === "CARRIED_OVER") {
        return { icon: UserRound, title: `Assigned to ${assignee}, carried over from ${text(payload.carried_over_from_reference) ?? "the previous occurrence"}` };
      }
      if (event.actor?.id && event.actor.id === payload.assignee_id) return { icon: UserRound, title: `${actor} took this exception` };
      return { icon: UserRound, title: `${actor} assigned ${assignee}` };
    }
    case "UNASSIGNED":
      return { icon: UserRound, title: `${actor} removed the assignee` };
    case "DUE_DATE_CHANGED":
      return {
        icon: CalendarClock,
        title: `${actor} changed the due date from ${when(payload.from)} to ${when(payload.to)}`,
        body: text(payload.note),
      };
    case "AUTO_RESOLVED":
      return { icon: CircleCheck, title: "Resolved automatically: the condition cleared" };
    case "VERIFIED":
      return { icon: CircleCheck, title: "Verified: the condition was no longer detected" };
    case "REOPENED": {
      const reason = REOPEN_REASONS[String(payload.reason)] ?? "reopened";
      const due = (payload.due_date_changed ?? {}) as Payload;
      return {
        icon: RotateCcw,
        title: `Reopened: ${reason}${text(due.to) ? `. Due date recalculated to ${when(due.to)}` : ""}`,
        body: text(payload.note),
      };
    }
    case "SUPERSEDED": {
      const type = exceptionTypeLabels[payload.superseded_by_type as ExceptionType];
      return {
        icon: CornerUpRight,
        title: `Superseded by ${text(payload.superseded_by_reference) ?? "another exception"}${type ? ` (${type})` : ""}`,
      };
    }
    default:
      return { icon: ArrowRightLeft, title: event.event_type.replace(/_/g, " ").toLowerCase() };
  }
}

/** Events and notes as one history, newest first. NOTE_ADDED events are shown as the notes. */
export function toTimelineItems(events: ExceptionEvent[], notes: ExceptionNote[], names: Map<string, string>, timeZone: string): TimelineItem[] {
  const fromEvents: TimelineItem[] = events
    .filter((event) => event.event_type !== "NOTE_ADDED")
    .map((event) => ({ id: event.id, kind: "event", occurredAt: event.occurred_at, ...describeEvent(event, names, timeZone) }));
  const fromNotes: TimelineItem[] = notes.map((note) => ({
    id: note.id,
    kind: "note",
    occurredAt: note.created_at,
    icon: MessageSquare,
    title: `${note.author?.full_name ?? "Former user"} added a note`,
    body: note.body,
    badge: note.source === "AI_DRAFT_ACCEPTED" ? `AI draft, accepted by ${note.author?.full_name ?? "a team member"}` : undefined,
  }));
  return [...fromEvents, ...fromNotes].sort((a, b) => b.occurredAt.localeCompare(a.occurredAt));
}

/**
 * Append-only notes (C-55). "Draft with copilot" only fills the text box: a person reviews, edits
 * and saves it, and the note records that it started as an AI draft.
 */
function NoteComposer({ exception }: { exception: ExceptionDetail }) {
  const store = useStore();
  const queryClient = useQueryClient();
  const gate = gateFor(exception, "add_note", store.organization.isDemo);
  const [body, setBody] = useState("");
  const [fromDraft, setFromDraft] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const command = useExceptionCommand(exception);
  const save = useMutation({
    mutationFn: () => exceptionsApi.addNote(store.id, exception.id, exception.version, body.trim(), fromDraft ? "AI_DRAFT_ACCEPTED" : "USER"),
  });
  const draft = useMutation({
    mutationFn: () => copilotApi.noteDraft(store.id, exception.id),
    onSuccess: (result) => {
      setBody(result.draft.body.slice(0, NOTE_MAX));
      setFromDraft(true);
      setError(null);
    },
    onError: (caught) => setError(userMessage(caught)),
  });
  const canDraft = store.permissions.has("copilot.use");

  if (!gate?.allowed) {
    return (
      <p className="rounded-md bg-surface-subtle p-3 text-body text-muted-foreground">
        {store.organization.isDemo ? "The public demo is read-only." : "Notes can be added by people who work on exceptions."}
      </p>
    );
  }

  const submit = async () => {
    const trimmed = body.trim();
    if (!trimmed) return setError("Write a note first.");
    if (trimmed.length > NOTE_MAX) return setError(`Notes are at most ${NOTE_MAX.toLocaleString("en-US")} characters.`);
    setError(null);
    try {
      await save.mutateAsync();
      setBody("");
      setFromDraft(false);
      await queryClient.invalidateQueries({ queryKey: exceptionKeys.detail(store.id, exception.id) });
    } catch (caught) {
      if (isApiError(caught) && caught.code === "STALE_VERSION") {
        // Someone changed the exception meanwhile: refresh, keep the text, and let the person resend.
        await command.run(() => Promise.reject(caught));
        return;
      }
      setError(userMessage(caught));
    }
  };

  return (
    <form
      noValidate
      className="flex flex-col gap-2"
      onSubmit={(event) => {
        event.preventDefault();
        void submit();
      }}
    >
      <Label htmlFor="note-body" className="sr-only">
        Add a note
      </Label>
      <Textarea
        id="note-body"
        placeholder="Add a note…"
        value={body}
        maxLength={NOTE_MAX}
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? "note-error" : undefined}
        onChange={(event) => {
          setBody(event.target.value);
          if (!event.target.value) setFromDraft(false);
        }}
        onKeyDown={(event) => {
          if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) {
            event.preventDefault();
            void submit();
          }
        }}
      />
      <div className="flex items-center justify-between gap-2">
        {error ? (
          <p id="note-error" role="alert" className="text-xs text-tone-danger-fg">
            {error}
          </p>
        ) : body.length >= NOTE_MAX * 0.8 ? (
          <p className="text-xs font-normal text-muted-foreground">
            {body.length.toLocaleString("en-US")} / {NOTE_MAX.toLocaleString("en-US")}
          </p>
        ) : (
          <span />
        )}
        <div className="flex items-center gap-2">
          {canDraft ? (
            <Button
              type="button"
              variant="secondary"
              size="sm"
              disabled={save.isPending}
              pending={draft.isPending}
              pendingLabel="Drafting…"
              onClick={() => draft.mutate()}
            >
              <Sparkles aria-hidden />
              Draft with copilot
            </Button>
          ) : null}
          <Button type="submit" size="sm" disabled={save.isPending} pending={save.isPending} pendingLabel="Adding…">
            {fromDraft ? "Save note" : "Add note"}
          </Button>
        </div>
      </div>
      {fromDraft ? (
        <p className="text-xs text-muted-foreground">AI draft. Review and edit it before saving; it is saved only when you choose Save note.</p>
      ) : null}
    </form>
  );
}

/** Notes and history of one exception (S-04 "Activity", C-54). */
export function Activity({ exception }: { exception: ExceptionDetail }) {
  const store = useStore();
  const [filter, setFilter] = useState<"all" | "notes">("all");
  const live = useRef<HTMLDivElement>(null);

  const events = useInfiniteQuery({
    queryKey: [...exceptionKeys.events(store.id, exception.id), exception.version],
    queryFn: ({ pageParam, signal }) => exceptionsApi.events(store.id, exception.id, { page: pageParam, page_size: EVENTS_PAGE }, signal),
    initialPageParam: 1,
    getNextPageParam: (last) => (last.page * last.page_size < last.total ? last.page + 1 : undefined),
  });
  const notes = useQuery({
    queryKey: [...exceptionKeys.notes(store.id, exception.id), exception.version],
    queryFn: ({ signal }) => exceptionsApi.notes(store.id, exception.id, { page_size: 100 }, signal),
  });
  const members = useQuery({
    queryKey: exceptionKeys.members(store.id),
    queryFn: ({ signal }) => exceptionsApi.members(store.id, signal),
    staleTime: 5 * 60_000,
  });

  const names = new Map<string, string>((members.data?.items ?? []).map((member) => [member.id, member.full_name]));
  if (exception.assignee) names.set(exception.assignee.id, exception.assignee.full_name);
  const allEvents = events.data?.pages.flatMap((page) => page.items) ?? [];
  const items = toTimelineItems(allEvents, notes.data?.items ?? [], names, store.timezone).filter(
    (item) => filter === "all" || item.kind === "note",
  );

  return (
    <section id="activity" aria-labelledby="activity-title" className="scroll-mt-20 rounded-lg border bg-card p-4 md:p-5">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h2 id="activity-title" className="text-title-sm">
          Activity
        </h2>
        <div role="group" aria-label="Show" className="inline-flex rounded-md border border-input p-0.5">
          {(["all", "notes"] as const).map((option) => (
            <button
              key={option}
              type="button"
              aria-pressed={filter === option}
              onClick={() => setFilter(option)}
              className={cn("h-6 rounded-sm px-2 text-xs", filter === option ? "bg-muted text-foreground" : "text-muted-foreground hover:bg-accent")}
            >
              {option === "all" ? "All" : "Notes"}
            </button>
          ))}
        </div>
      </div>
      <NoteComposer exception={exception} />
      <div ref={live} aria-live="polite" className="sr-only" />
      {events.isPending || notes.isPending ? (
        <div aria-busy="true" className="mt-4 flex flex-col gap-3">
          {[0, 1, 2].map((row) => (
            <Skeleton key={row} className="h-10 w-full" />
          ))}
        </div>
      ) : events.isError || notes.isError ? (
        <ErrorState title="Couldn't load the activity" error={events.error ?? notes.error} onRetry={() => void Promise.all([events.refetch(), notes.refetch()])} />
      ) : items.length === 0 ? (
        <p className="mt-4 text-body text-muted-foreground">{filter === "notes" ? "No notes yet." : "No activity yet."}</p>
      ) : (
        <ol className="mt-4 flex flex-col">
          {items.map((item) => {
            const Icon = item.icon;
            return (
              <li key={`${item.kind}-${item.id}`} className="flex gap-3 border-t py-3 first:border-t-0">
                <span className={cn("mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-full", item.kind === "note" ? "bg-tone-primary-bg text-tone-primary-fg" : "bg-muted text-muted-foreground")}>
                  <Icon aria-hidden className="size-4" />
                </span>
                <div className="flex min-w-0 flex-1 flex-col gap-0.5">
                  <p className="text-body">
                    {item.title}
                    {item.badge ? <span className="ml-2 rounded-sm bg-tone-neutral-bg px-1.5 text-xs text-tone-neutral-fg">{item.badge}</span> : null}
                  </p>
                  {item.body ? <p className="text-prose whitespace-pre-wrap text-text-secondary">{item.body}</p> : null}
                  <p className="text-xs font-normal text-muted-foreground">
                    <DateTime value={item.occurredAt} />
                  </p>
                </div>
              </li>
            );
          })}
        </ol>
      )}
      {events.hasNextPage ? (
        <Button type="button" variant="secondary" size="sm" className="mt-2" pending={events.isFetchingNextPage} pendingLabel="Loading…" onClick={() => void events.fetchNextPage()}>
          Show earlier activity
        </Button>
      ) : null}
    </section>
  );
}
