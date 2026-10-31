"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { CircleAlert, Info } from "lucide-react";
import { useRouter } from "next/navigation";
import { Controller, useForm, useWatch } from "react-hook-form";
import { z } from "zod";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Textarea } from "@/components/ui/textarea";
import { exceptionsApi, type ExceptionDetail } from "@/lib/api/exceptions-api";
import { dismissalReasonLabels, manualResolutionLabels, type DismissalReason, type ManualResolutionCode } from "@/lib/status-maps";
import { useStore } from "@/lib/store/store-context";

import { useQueueNeighbours } from "../queue";
import { commandErrorMessage, useExceptionCommand } from "./use-exception-command";

// Closing notes need at least 10 non-whitespace characters, as the API counts them
// (CLOSING_NOTE_MIN_CHARS in the lifecycle module).
const NOTE_MIN = 10;
const NOTE_MAX = 4000;
export const nonWhitespaceLength = (text: string) => text.replace(/\s/g, "").length;

const closingNote = z
  .string()
  .max(NOTE_MAX, `Notes are at most ${NOTE_MAX.toLocaleString("en-US")} characters.`)
  .superRefine((text, ctx) => {
    const count = nonWhitespaceLength(text);
    if (count < NOTE_MIN) {
      ctx.addIssue({ code: "custom", message: `Enter at least ${NOTE_MIN} characters (currently ${count}).` });
    }
  });

const RESOLUTION_CODES = Object.keys(manualResolutionLabels) as [ManualResolutionCode, ...ManualResolutionCode[]];
const DISMISSAL_REASONS = Object.keys(dismissalReasonLabels) as [DismissalReason, ...DismissalReason[]];

export const resolveSchema = z.object({
  resolution_code: z.enum(RESOLUTION_CODES, { message: "Choose how it was resolved." }),
  resolution_note: closingNote,
});
export const dismissSchema = z.object({
  dismissal_reason: z.enum(DISMISSAL_REASONS, { message: "Choose a reason." }),
  note: closingNote,
});
export const reopenSchema = z.object({
  reason: z
    .string()
    .max(NOTE_MAX, `The reason is at most ${NOTE_MAX.toLocaleString("en-US")} characters.`)
    .refine((text) => text.trim().length > 0, "Explain why it needs attention again."),
});

type DialogProps = { exception: ExceptionDetail; open: boolean; onOpenChange: (open: boolean) => void };

function FieldError({ id, message }: { id: string; message?: string }) {
  if (!message) return null;
  return (
    <p id={id} className="flex items-center gap-1 text-xs text-tone-danger-fg">
      <CircleAlert aria-hidden className="size-3.5 shrink-0" />
      {message}
    </p>
  );
}

function NoteCounter({ value, min }: { value: string; min?: number }) {
  const count = nonWhitespaceLength(value);
  if (min !== undefined && count < min) {
    return <p className="text-xs font-normal text-muted-foreground">{count} / {min} minimum</p>;
  }
  if (value.length >= NOTE_MAX * 0.8) {
    return <p className="text-xs font-normal text-muted-foreground">{value.length.toLocaleString("en-US")} / {NOTE_MAX.toLocaleString("en-US")}</p>;
  }
  return null;
}

/** A failed submit that isn't a conflict: the message, with the input kept for a retry. */
function ServerError({ message }: { message?: string }) {
  if (!message) return null;
  return (
    <Alert tone="danger" role="alert">
      <CircleAlert aria-hidden />
      <AlertDescription>{message}</AlertDescription>
    </Alert>
  );
}

/**
 * Closes on success or when the action is no longer possible; stays open on a stale version.
 * Closing actions offer "Next in queue" on their toast when the person came from a list (S-04).
 */
function useDialogSubmit(exception: ExceptionDetail, onOpenChange: (open: boolean) => void, options: { nextInQueue?: boolean } = {}) {
  const store = useStore();
  const router = useRouter();
  const command = useExceptionCommand(exception);
  const next = useQueueNeighbours(store.id, exception.id)?.next;
  const nextHref = options.nextInQueue && next ? `/s/${store.id}/exceptions/${next.id}` : undefined;
  return {
    pending: command.pending,
    submit: async (
      run: (version: number) => Promise<unknown>,
      message: (updated: ExceptionDetail) => string,
      setError: (error: unknown) => void,
    ) => {
      setError(null);
      const result = await command.run(run, {
        successMessage: message,
        successAction: nextHref ? { label: "Next in queue", onClick: () => router.push(nextHref) } : undefined,
      });
      if (result.outcome === "done" || result.outcome === "conflict") onOpenChange(false);
      else if (result.outcome === "failed") setError(result.error);
    },
  };
}

export function ResolveDialog({ exception, open, onOpenChange }: DialogProps) {
  const store = useStore();
  const form = useForm<z.infer<typeof resolveSchema>>({
    resolver: zodResolver(resolveSchema),
    mode: "onTouched",
    defaultValues: { resolution_note: "" },
  });
  const { pending, submit } = useDialogSubmit(exception, onOpenChange, { nextInQueue: true });
  const serverError = form.formState.errors.root?.serverError;
  const setError = (error: unknown) =>
    error ? form.setError("root.serverError", { message: commandErrorMessage(error) }) : form.clearErrors("root.serverError");
  const note = useWatch({ control: form.control, name: "resolution_note" }) ?? "";
  const { errors } = form.formState;

  return (
    <Dialog open={open} onOpenChange={(next) => !pending && onOpenChange(next)}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Resolve {exception.reference}</DialogTitle>
          <DialogDescription>{exception.title}</DialogDescription>
        </DialogHeader>
        <form
          noValidate
          className="flex flex-col gap-4"
          onSubmit={form.handleSubmit((values) =>
            submit(
              (version) => exceptionsApi.resolve(store.id, exception.id, version, values),
              (updated) => `${updated.reference} resolved. Awaiting verification after the next import, or within 24 h.`,
              setError,
            ),
          )}
        >
          <Alert tone="info">
            <Info aria-hidden />
            <AlertDescription>
              After you resolve, this exception shows Resolved — awaiting verification. RetailOps re-checks the condition after
              the next import completes, or after 24 h. If the condition is still present then, the exception reopens. For
              long-running work, such as waiting for a delivery, keep it In progress. It resolves automatically when the
              condition clears.
            </AlertDescription>
          </Alert>
          <ServerError message={serverError?.message} />
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="resolution_code">How was it resolved?</Label>
            <select
              id="resolution_code"
              autoFocus
              aria-invalid={errors.resolution_code ? true : undefined}
              aria-describedby={errors.resolution_code ? "resolution_code-error" : undefined}
              className="h-10 rounded-md border border-input bg-card px-3 text-base hover:border-input-hover focus-visible:border-ring focus-visible:shadow-[0_0_0_1px_var(--ring)] focus-visible:outline-none aria-invalid:border-tone-danger-fg sm:h-8 sm:text-body"
              defaultValue=""
              {...form.register("resolution_code")}
            >
              <option value="" disabled>
                Choose…
              </option>
              {RESOLUTION_CODES.map((code) => (
                <option key={code} value={code}>
                  {manualResolutionLabels[code]}
                </option>
              ))}
            </select>
            <FieldError id="resolution_code-error" message={errors.resolution_code?.message} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="resolution_note">What was done</Label>
            <Textarea
              id="resolution_note"
              aria-invalid={errors.resolution_note ? true : undefined}
              aria-describedby="resolution_note-error resolution_note-help"
              {...form.register("resolution_note")}
            />
            <div id="resolution_note-help">
              {errors.resolution_note ? null : <NoteCounter value={note} min={NOTE_MIN} />}
            </div>
            <FieldError id="resolution_note-error" message={errors.resolution_note?.message} />
          </div>
          <DialogFooter>
            <Button type="button" variant="secondary" disabled={pending} onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={pending} pending={pending} pendingLabel="Resolving…">
              Resolve exception
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

export function DismissDialog({ exception, open, onOpenChange }: DialogProps) {
  const store = useStore();
  const form = useForm<z.infer<typeof dismissSchema>>({
    resolver: zodResolver(dismissSchema),
    mode: "onTouched",
    defaultValues: { note: "" },
  });
  const { pending, submit } = useDialogSubmit(exception, onOpenChange, { nextInQueue: true });
  const serverError = form.formState.errors.root?.serverError;
  const setError = (error: unknown) =>
    error ? form.setError("root.serverError", { message: commandErrorMessage(error) }) : form.clearErrors("root.serverError");
  const note = useWatch({ control: form.control, name: "note" }) ?? "";
  const { errors } = form.formState;

  return (
    <Dialog open={open} onOpenChange={(next) => !pending && onOpenChange(next)}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Dismiss {exception.reference}</DialogTitle>
          <DialogDescription>
            Dismissed exceptions stop being tracked. If the condition clears and comes back later, a new exception is created.
          </DialogDescription>
        </DialogHeader>
        <form
          noValidate
          className="flex flex-col gap-4"
          onSubmit={form.handleSubmit((values) =>
            submit((version) => exceptionsApi.dismiss(store.id, exception.id, version, values), () => "Exception dismissed", setError),
          )}
        >
          <ServerError message={serverError?.message} />
          <fieldset className="flex flex-col gap-2" aria-describedby={errors.dismissal_reason ? "dismissal_reason-error" : undefined}>
            <legend className="mb-1 text-body-strong">Reason</legend>
            <Controller
              control={form.control}
              name="dismissal_reason"
              render={({ field }) => (
                <RadioGroup value={field.value ?? ""} onValueChange={field.onChange} className="gap-2">
                  {DISMISSAL_REASONS.map((reason) => (
                    <label key={reason} className="flex cursor-pointer items-start gap-2 text-body">
                      <RadioGroupItem value={reason} className="mt-0.5" aria-invalid={errors.dismissal_reason ? true : undefined} />
                      <span>
                        <span className="font-medium">{dismissalReasonLabels[reason].label}</span>
                        <span className="text-muted-foreground">: {dismissalReasonLabels[reason].description}</span>
                      </span>
                    </label>
                  ))}
                </RadioGroup>
              )}
            />
            <FieldError id="dismissal_reason-error" message={errors.dismissal_reason?.message} />
          </fieldset>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="dismiss_note">Note</Label>
            <Textarea
              id="dismiss_note"
              aria-invalid={errors.note ? true : undefined}
              aria-describedby="dismiss_note-error dismiss_note-help"
              {...form.register("note")}
            />
            <div id="dismiss_note-help">{errors.note ? null : <NoteCounter value={note} min={NOTE_MIN} />}</div>
            <FieldError id="dismiss_note-error" message={errors.note?.message} />
          </div>
          <DialogFooter>
            <Button type="button" variant="secondary" disabled={pending} onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" variant="destructive" disabled={pending} pending={pending} pendingLabel="Dismissing…">
              Dismiss exception
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

export function ReopenDialog({ exception, open, onOpenChange }: DialogProps) {
  const store = useStore();
  const form = useForm<z.infer<typeof reopenSchema>>({
    resolver: zodResolver(reopenSchema),
    mode: "onTouched",
    defaultValues: { reason: "" },
  });
  const { pending, submit } = useDialogSubmit(exception, onOpenChange);
  const serverError = form.formState.errors.root?.serverError;
  const setError = (error: unknown) =>
    error ? form.setError("root.serverError", { message: commandErrorMessage(error) }) : form.clearErrors("root.serverError");
  const { errors } = form.formState;

  return (
    <Dialog open={open} onOpenChange={(next) => !pending && onOpenChange(next)}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Reopen {exception.reference}</DialogTitle>
          <DialogDescription>The exception returns to Reopened and appears in the triage queue.</DialogDescription>
        </DialogHeader>
        <form
          noValidate
          className="flex flex-col gap-4"
          onSubmit={form.handleSubmit((values) =>
            submit(
              (version) => exceptionsApi.reopen(store.id, exception.id, version, { reason: values.reason.trim() }),
              () => "Exception reopened",
              setError,
            ),
          )}
        >
          <ServerError message={serverError?.message} />
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="reopen_reason">Why does it need attention again?</Label>
            <Textarea
              id="reopen_reason"
              autoFocus
              aria-invalid={errors.reason ? true : undefined}
              aria-describedby={errors.reason ? "reopen_reason-error" : undefined}
              {...form.register("reason")}
            />
            <FieldError id="reopen_reason-error" message={errors.reason?.message} />
          </div>
          <DialogFooter>
            <Button type="button" variant="secondary" disabled={pending} onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={pending} pending={pending} pendingLabel="Reopening…">
              Reopen exception
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
