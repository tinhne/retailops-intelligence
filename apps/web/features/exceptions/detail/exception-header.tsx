"use client";

import { useQuery } from "@tanstack/react-query";
import { CircleAlert, MoreHorizontal, Pencil, UserRound } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { ActionButton } from "@/components/actions/action-button";
import { DateTime, DueLabel } from "@/components/data/values";
import { CopyButton } from "@/components/states/copy-button";
import { ExceptionStatusPill, PriorityIndicator, SeverityBadge } from "@/components/status/status-pill";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { Textarea } from "@/components/ui/textarea";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { userMessage } from "@/lib/api/errors";
import { exceptionKeys, exceptionsApi, type ExceptionDetail } from "@/lib/api/exceptions-api";
import { formatDateTime, utcToZonedInputs, zonedTimeToUtc } from "@/lib/format/datetime";
import { useMediaQuery } from "@/lib/hooks/browser";
import type { Gate } from "@/lib/permissions";
import { roleLabels } from "@/lib/permissions";
import { categoryLabels, exceptionTypeLabels } from "@/lib/status-maps";
import { useStore } from "@/lib/store/store-context";
import { cn } from "@/lib/utils";

import { getExceptionActions, gateFor, type ActionItem, type BarAction } from "./actions";
import { DismissDialog, ReopenDialog, ResolveDialog } from "./lifecycle-dialogs";
import { LifecycleExplainer } from "./lifecycle-explainer";
import { useExceptionCommand } from "./use-exception-command";

const BUSY: Gate = { allowed: false, reason: "Another action is in progress." };

/** Read-only value with its reason reachable by focus (C-58 read-only state). */
function ReadOnlyField({ children, reason }: { children: React.ReactNode; reason?: string }) {
  if (!reason) return <span>{children}</span>;
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span tabIndex={0} className="rounded-sm outline-offset-2">
          {children}
        </span>
      </TooltipTrigger>
      <TooltipContent>{reason}</TooltipContent>
    </Tooltip>
  );
}

/** Assign, reassign, claim or unassign (C-58). Selecting a person submits at once. */
function AssigneeControl({ exception }: { exception: ExceptionDetail }) {
  const store = useStore();
  const [open, setOpen] = useState(false);
  const command = useExceptionCommand(exception);
  const assignGate = gateFor(exception, "assign", store.organization.isDemo);
  const canAssign = assignGate?.allowed === true;
  const members = useQuery({
    queryKey: exceptionKeys.members(store.id),
    queryFn: ({ signal }) => exceptionsApi.members(store.id, signal),
    enabled: canAssign,
    staleTime: 5 * 60_000,
  });
  const current = exception.assignee?.full_name ?? "Unassigned";

  if (!canAssign) {
    return (
      <span className="inline-flex items-center gap-1.5 text-body">
        <UserRound aria-hidden className="size-4 text-muted-foreground" />
        <span className="text-muted-foreground">Assignee:</span>
        <ReadOnlyField reason={assignGate && !assignGate.allowed ? assignGate.reason : undefined}>{current}</ReadOnlyField>
      </span>
    );
  }

  const assign = async (assigneeId: string | null, name: string) => {
    setOpen(false);
    const result = await command.run((version) => exceptionsApi.assign(store.id, exception.id, version, assigneeId), {
      successMessage: () => (assigneeId ? `Assigned to ${name}` : "Assignee removed"),
    });
    if (result.outcome === "failed") toast.error(userMessage(result.error));
  };
  const workers = (members.data?.items ?? []).filter((member) => member.can_work_exceptions);

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button type="button" variant="ghost" size="sm" aria-label={`Assignee: ${current}, change`} pending={command.pending} pendingLabel="Assigning…">
          <UserRound aria-hidden />
          <span className="text-muted-foreground">Assignee:</span> {current}
        </Button>
      </PopoverTrigger>
      <PopoverContent align="start" className="w-64 p-1">
        <ul role="listbox" aria-label="Assign to" className="flex max-h-72 flex-col overflow-y-auto">
          {[
            ...(store.permissions.has("exceptions.work") && exception.assignee?.id !== store.user.id
              ? [{ id: store.user.id, label: "Assign to me", detail: "" }]
              : []),
            ...workers
              .filter((member) => member.id !== exception.assignee?.id && member.id !== store.user.id)
              .map((member) => ({ id: member.id, label: member.full_name, detail: roleLabels[member.role] })),
          ].map((option) => (
            <li key={option.id}>
              <button
                type="button"
                role="option"
                aria-selected={false}
                className="flex min-h-8 w-full items-center justify-between gap-2 rounded-md px-2 text-left text-body hover:bg-accent"
                onClick={() => void assign(option.id, option.id === store.user.id ? "you" : option.label)}
              >
                {option.label}
                {option.detail ? <span className="text-xs text-muted-foreground">{option.detail}</span> : null}
              </button>
            </li>
          ))}
          {members.isPending ? <li className="px-2 py-1.5 text-sm text-muted-foreground">Loading members…</li> : null}
          {exception.assignee ? (
            <li className="mt-1 border-t pt-1">
              <button
                type="button"
                role="option"
                aria-selected={false}
                className="flex min-h-8 w-full items-center rounded-md px-2 text-left text-body text-tone-danger-fg hover:bg-tone-danger-bg"
                onClick={() => void assign(null, "")}
              >
                Remove assignee
              </button>
            </li>
          ) : null}
        </ul>
      </PopoverContent>
    </Popover>
  );
}

/** Due label plus a manual override (C-59). Times are entered in the store zone. */
function DueDateControl({ exception }: { exception: ExceptionDetail }) {
  const store = useStore();
  const command = useExceptionCommand(exception);
  const gate = gateFor(exception, "set_due_date", store.organization.isDemo);
  const [open, setOpen] = useState(false);
  const initial = utcToZonedInputs(exception.due_at, store.timezone);
  const [date, setDate] = useState(initial.date);
  const [time, setTime] = useState(initial.time);
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);

  const zone = formatDateTime(exception.due_at, store.timezone).split(" ").pop();
  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!date || !time) return setError("Enter a date and time.");
    const dueAt = zonedTimeToUtc(date, time, store.timezone);
    if (dueAt.getTime() <= Date.now()) return setError("Choose a time in the future.");
    if (!reason.trim()) return setError("Explain why the due date changes.");
    setError(null);
    const result = await command.run(
      (version) => exceptionsApi.setDueDate(store.id, exception.id, version, { due_at: dueAt.toISOString(), note: reason.trim() }),
      { successMessage: () => "Due date updated" },
    );
    if (result.outcome === "done" || result.outcome === "conflict") {
      setOpen(false);
      setReason("");
    } else if (result.outcome === "failed") setError("The due date couldn't be updated. Try again.");
  };

  return (
    <span className="inline-flex items-center gap-1 text-body">
      <DueLabel dueAt={exception.due_at} />
      {exception.due_at_overridden ? <span className="text-xs text-muted-foreground">(set manually)</span> : null}
      {gate?.allowed ? (
        <Popover open={open} onOpenChange={setOpen}>
          <PopoverTrigger asChild>
            <Button type="button" variant="ghost" size="icon-sm" aria-label="Change due date">
              <Pencil aria-hidden />
            </Button>
          </PopoverTrigger>
          <PopoverContent align="start" className="w-80">
            <form noValidate onSubmit={submit} className="flex flex-col gap-3">
              <p className="text-body-strong">Change due date</p>
              <div className="flex gap-2">
                <div className="flex flex-1 flex-col gap-1">
                  <Label htmlFor="due-date">Date</Label>
                  <Input id="due-date" type="date" value={date} onChange={(e) => setDate(e.target.value)} />
                </div>
                <div className="flex w-32 flex-col gap-1">
                  <Label htmlFor="due-time">Time ({zone})</Label>
                  <Input id="due-time" type="time" value={time} onChange={(e) => setTime(e.target.value)} />
                </div>
              </div>
              <div className="flex flex-col gap-1">
                <Label htmlFor="due-reason">Reason</Label>
                <Textarea id="due-reason" value={reason} onChange={(e) => setReason(e.target.value)} className="min-h-16" />
                <p className="text-xs font-normal text-muted-foreground">
                  A manual due date is kept until the exception is reopened. Reopening recalculates it from the reopen time.
                </p>
              </div>
              {error ? (
                <p role="alert" className="flex items-center gap-1 text-xs text-tone-danger-fg">
                  <CircleAlert aria-hidden className="size-3.5" />
                  {error}
                </p>
              ) : null}
              <Button type="submit" disabled={command.pending} pending={command.pending} pendingLabel="Updating…">
                Update due date
              </Button>
            </form>
          </PopoverContent>
        </Popover>
      ) : null}
    </span>
  );
}

/** Lifecycle buttons (C-56): what the API allows, plus refused actions with their reasons. */
function ActionBar({ exception }: { exception: ExceptionDetail }) {
  const store = useStore();
  const command = useExceptionCommand(exception);
  const [dialog, setDialog] = useState<"resolve" | "dismiss" | "reopen" | null>(null);
  const [pendingKind, setPendingKind] = useState<BarAction | null>(null);
  const [sheetOpen, setSheetOpen] = useState(false);
  const wide = useMediaQuery("(min-width: 768px)");
  const layout = getExceptionActions(exception, store.organization.isDemo);

  const runDirect = async (kind: BarAction) => {
    setPendingKind(kind);
    const messages: Partial<Record<BarAction, string>> = {
      acknowledge: "Exception acknowledged",
      start: exception.assignee ? "Work started." : "Work started. Assigned to you.",
      claim: "Assigned to you",
    };
    const call =
      kind === "acknowledge"
        ? (version: number) => exceptionsApi.acknowledge(store.id, exception.id, version)
        : kind === "start"
          ? (version: number) => exceptionsApi.start(store.id, exception.id, version)
          : (version: number) => exceptionsApi.assign(store.id, exception.id, version, store.user.id);
    const result = await command.run(call, { successMessage: () => messages[kind] ?? null });
    setPendingKind(null);
    if (result.outcome === "failed") toast.error(userMessage(result.error));
  };
  const trigger = (item: ActionItem) => {
    if (item.opensDialog) setDialog(item.kind as "resolve" | "dismiss" | "reopen");
    else void runDirect(item.kind);
  };
  const gateOf = (item: ActionItem): Gate => (pendingKind && pendingKind !== item.kind ? BUSY : item.gate);
  const explainer = store.role === "VIEWER" ? <LifecycleExplainer /> : null;

  if (!layout.primary && layout.secondary.length === 0 && layout.more.length === 0) return explainer;

  const dialogs = (
    <>
      <ResolveDialog exception={exception} open={dialog === "resolve"} onOpenChange={(open) => setDialog(open ? "resolve" : null)} />
      <DismissDialog exception={exception} open={dialog === "dismiss"} onOpenChange={(open) => setDialog(open ? "dismiss" : null)} />
      <ReopenDialog exception={exception} open={dialog === "reopen"} onOpenChange={(open) => setDialog(open ? "reopen" : null)} />
    </>
  );

  // Below 768 px the actions sit in a bar fixed to the bottom of the screen (S-04 "Responsive"):
  // the primary action, and More opening a sheet with the others and their disabled reasons.
  if (!wide) {
    const others = [...layout.secondary, ...layout.more];
    return (
      <>
        {explainer}
        <div
          role="toolbar"
          aria-label="Exception actions"
          className="fixed inset-x-0 bottom-0 z-(--z-sticky-bar) flex h-16 items-center gap-2 border-t bg-card px-4"
        >
          {layout.primary ? (
            <ActionButton
              gate={gateOf(layout.primary)}
              type="button"
              size="lg"
              className="min-w-0 flex-1"
              pending={pendingKind === layout.primary.kind}
              pendingLabel={`${layout.primary.label.replace("…", "")}…`}
              onClick={() => layout.primary && trigger(layout.primary)}
            >
              {layout.primary.label}
            </ActionButton>
          ) : null}
          {others.length > 0 ? (
            <Sheet open={sheetOpen} onOpenChange={setSheetOpen}>
              <SheetTrigger asChild>
                <Button type="button" variant="secondary" size="lg" className={cn(!layout.primary && "flex-1")} aria-label="More actions">
                  More
                  <MoreHorizontal aria-hidden />
                </Button>
              </SheetTrigger>
              <SheetContent side="bottom" className="gap-0 rounded-t-lg">
                <SheetHeader className="border-b">
                  <SheetTitle>Actions</SheetTitle>
                  <SheetDescription>{exception.reference}</SheetDescription>
                </SheetHeader>
                <ul className="flex flex-col gap-1 p-2">
                  {others.map((item) => {
                    const gate = gateOf(item);
                    return (
                      <li key={item.kind}>
                        <button
                          type="button"
                          aria-disabled={gate.allowed ? undefined : true}
                          onClick={() => {
                            if (!gate.allowed) return;
                            setSheetOpen(false);
                            trigger(item);
                          }}
                          className={cn(
                            "flex min-h-12 w-full flex-col items-start justify-center gap-0.5 rounded-md px-3 py-2 text-left text-body",
                            gate.allowed ? "hover:bg-accent" : "cursor-not-allowed text-text-disabled",
                          )}
                        >
                          <span className="font-medium">{item.label}</span>
                          {!gate.allowed ? <span className="text-xs text-muted-foreground">{gate.reason}</span> : null}
                        </button>
                      </li>
                    );
                  })}
                </ul>
              </SheetContent>
            </Sheet>
          ) : null}
        </div>
        {dialogs}
      </>
    );
  }

  return (
    <>
      <div className="flex flex-wrap items-center gap-2">
        <div role="toolbar" aria-label="Exception actions" className="flex flex-wrap items-center gap-2">
          {layout.primary ? (
            <ActionButton
              gate={gateOf(layout.primary)}
              type="button"
              pending={pendingKind === layout.primary.kind}
              pendingLabel={`${layout.primary.label.replace("…", "")}…`}
              onClick={() => layout.primary && trigger(layout.primary)}
            >
              {layout.primary.label}
            </ActionButton>
          ) : null}
          {layout.secondary.map((item) => (
            <ActionButton
              key={item.kind}
              gate={gateOf(item)}
              type="button"
              variant="secondary"
              pending={pendingKind === item.kind}
              pendingLabel={`${item.label.replace("…", "")}…`}
              onClick={() => trigger(item)}
            >
              {item.label}
            </ActionButton>
          ))}
          {layout.more.length > 0 ? (
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button type="button" variant="secondary" aria-label="More actions">
                  More
                  <MoreHorizontal aria-hidden />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-72">
                {layout.more.map((item) => {
                  const gate = gateOf(item);
                  return (
                    <DropdownMenuItem
                      key={item.kind}
                      disabled={!gate.allowed}
                      onSelect={() => trigger(item)}
                      className="flex-col items-start gap-0.5"
                    >
                      <span>{item.label}</span>
                      {!gate.allowed ? <span className="text-xs font-normal text-muted-foreground">{gate.reason}</span> : null}
                    </DropdownMenuItem>
                  );
                })}
              </DropdownMenuContent>
            </DropdownMenu>
          ) : null}
        </div>
        {explainer}
      </div>
      {dialogs}
    </>
  );
}

/** Header block (S-04): title, meta line, status row, detection line and actions. */
export function ExceptionHeader({ exception }: { exception: ExceptionDetail }) {
  const entity = exception.primary_entity;
  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-col gap-1">
        <h1 tabIndex={-1} className="text-title-lg outline-none">
          {exception.title}
        </h1>
        <p className="flex flex-wrap items-center gap-x-1.5 text-sm text-muted-foreground">
          <span className="font-medium text-foreground">{exception.reference}</span>
          <CopyButton value={exception.reference} label={`Copy ${exception.reference}`} />
          <span>· {exceptionTypeLabels[exception.exception_type]}</span>
          <span>· {categoryLabels[exception.category]}</span>
          <span>
            · {entity.type === "product" ? "Product" : "Order"} {entity.label}
            {entity.name ? ` (${entity.name})` : ""}
          </span>
          <span>
            · Rule <code className="font-mono text-mono">{exception.rule_id}</code>
          </span>
        </p>
      </div>
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        <SeverityBadge severity={exception.severity} size="md" />
        <PriorityIndicator band={exception.priority_band} score={exception.priority_score} />
        <ExceptionStatusPill
          status={exception.status}
          resolutionCode={exception.resolution?.resolution_code}
          verifiedAt={exception.resolution?.verified_at}
          size="md"
        />
        <AssigneeControl exception={exception} />
        {exception.status === "RESOLVED" || exception.status === "DISMISSED" ? null : <DueDateControl exception={exception} />}
      </div>
      <p className="text-sm text-muted-foreground">
        First detected <DateTime value={exception.first_detected_at} /> · Last detected{" "}
        <DateTime value={exception.last_detected_at} compact /> · Detected {exception.detection_count}{" "}
        {exception.detection_count === 1 ? "time" : "times"}
      </p>
      <ActionBar exception={exception} />
    </div>
  );
}
