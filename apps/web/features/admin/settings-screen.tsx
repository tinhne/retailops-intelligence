"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CircleAlert, Info, RotateCcw, TriangleAlert } from "lucide-react";
import { useEffect, useState } from "react";
import { useForm, useWatch, type UseFormReturn } from "react-hook-form";
import { toast } from "sonner";

import { Section } from "@/components/data/section";
import { PageHeader } from "@/components/shell/page-header";
import { ErrorState } from "@/components/states/error-state";
import { PermissionDenied } from "@/components/states/permission-denied";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { adminApi, adminKeys, type StoreSettings, type StoreSettingsUpdate } from "@/lib/api/admin-api";
import { useDocumentTitle } from "@/lib/hooks/use-document-title";
import { DEMO_READ_ONLY_REASON } from "@/lib/permissions";
import { useStore } from "@/lib/store/store-context";

import { FieldError, ServerError, validationFieldErrors } from "./form-parts";
import {
  buildUpdate,
  changedFields,
  FIELD_BY_PATH,
  formatSetting,
  MAX_PRIORITY_SCORE,
  maxPossibleScore,
  SECTIONS,
  SETTING_FIELDS,
  settingsSchema,
  settingsSignature,
  toFormValues,
  unitSpoken,
  unitSuffix,
  type SectionId,
  type SettingChange,
  type SettingField,
  type SettingsFormValues,
} from "./settings-fields";

const READERS_NOTE = "Only owners and managers can change settings.";
const plural = (count: number, word: string) => `${count} ${word}${count === 1 ? "" : "s"}`;
const changeLabel = (field: SettingField) => (field.group ? `${field.group} · ${field.label}` : field.label);

/** Settings (SCREEN_SPECIFICATIONS S-16): thresholds and priority weights, each tied to its rule. */
export function SettingsScreen() {
  const store = useStore();
  useDocumentTitle("Settings");
  const canRead = store.permissions.has("settings.read");
  const canEdit = store.permissions.has("settings.manage");
  const settings = useQuery({
    queryKey: adminKeys.settings(store.id),
    queryFn: ({ signal }) => adminApi.settings(store.id, signal),
    enabled: canRead,
  });
  // The values the form was opened with. Background refetches never overwrite someone's edits;
  // a difference from the latest values is shown as a conflict instead.
  const [baseline, setBaseline] = useState<StoreSettings | null>(null);
  if (settings.data && baseline === null) setBaseline(settings.data);

  if (!canRead) return <PermissionDenied pageName="settings" permission="settings.read" />;

  const initial = baseline ?? settings.data;
  let body: React.ReactNode;
  if (settings.isPending) {
    body = (
      <div aria-busy="true" className="flex flex-col gap-8">
        <span className="sr-only">Loading settings</span>
        {SECTIONS.map((section) => (
          <div key={section.id} className="flex flex-col gap-3 rounded-lg border bg-card p-4 md:p-5">
            <Skeleton className="h-5 w-40" />
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-2/3" />
          </div>
        ))}
      </div>
    );
  } else if (settings.isError || !initial || !settings.data) {
    body = (
      <div className="rounded-lg border bg-card">
        <ErrorState title="Couldn't load settings" error={settings.error} onRetry={() => void settings.refetch()} />
      </div>
    );
  } else if (canEdit) {
    body = (
      <SettingsForm
        key={settingsSignature(initial)}
        initial={initial}
        latest={settings.data}
        refetch={async () => (await settings.refetch()).data}
        onSaved={setBaseline}
        onReload={() => setBaseline(settings.data ?? null)}
      />
    );
  } else {
    body = <SettingsReadOnly settings={settings.data} note={store.organization.isDemo ? DEMO_READ_ONLY_REASON : READERS_NOTE} />;
  }

  return (
    <div className="flex flex-col gap-6">
      <PageHeader title="Settings" subtitle={store.name} />
      <div className="flex w-full max-w-[720px] flex-col gap-8">
        <StoreProfile />
        {body}
      </div>
    </div>
  );
}

function StoreProfile() {
  const store = useStore();
  const rows: Array<[string, string]> = [
    ["Store", store.name],
    ["Code", store.code],
    ["Currency", store.currency],
    ["Time zone", store.timezone],
    ["Organization", store.organization.name],
  ];
  return (
    <Section id="store-profile" title="Store profile">
      <dl className="grid grid-cols-1 gap-x-6 gap-y-2 sm:grid-cols-[max-content_1fr]">
        {rows.map(([label, value]) => (
          <div key={label} className="contents">
            <dt className="text-sm text-muted-foreground">{label}</dt>
            <dd className="min-w-0 break-words">{value}</dd>
          </div>
        ))}
      </dl>
      <p className="mt-3 text-sm text-muted-foreground">Currency and time zone are fixed after the store is created.</p>
    </Section>
  );
}

function ScoreLine({ score }: { score: number | null }) {
  if (score === null) return null;
  return (
    <p className="text-sm text-muted-foreground tabular-nums">
      Maximum possible score: {score} of {MAX_PRIORITY_SCORE}
    </p>
  );
}

/** Readers see values with their defaults, not disabled inputs (S-16). */
function SettingsReadOnly({ settings, note }: { settings: StoreSettings; note: string }) {
  const { currency } = useStore();
  const values = toFormValues(settings);
  return (
    <div className="flex flex-col gap-8">
      <Alert tone="neutral">
        <Info aria-hidden />
        <AlertDescription>{note}</AlertDescription>
      </Alert>
      {SECTIONS.map((section) => (
        <Section key={section.id} id={`settings-${section.id}`} title={section.title}>
          <dl className="flex flex-col">
            {SETTING_FIELDS.filter((field) => field.section === section.id).map((field) => (
              <div key={field.name} className="flex flex-col gap-1 border-b py-2 last:border-b-0 sm:flex-row sm:items-start sm:justify-between sm:gap-6">
                <dt className="min-w-0">
                  <span className="text-body-strong">{changeLabel(field)}</span>
                  {field.helper ? <span className="block text-sm text-muted-foreground">{field.helper}</span> : null}
                </dt>
                <dd className="flex flex-col tabular-nums sm:items-end sm:text-right">
                  <span>{formatSetting(field, values[field.name], currency)}</span>
                  <span className="text-xs font-normal text-muted-foreground">Default {formatSetting(field, field.defaultValue, currency)}</span>
                </dd>
              </div>
            ))}
          </dl>
          {section.id === "priority" ? (
            <div className="mt-3">
              <ScoreLine score={maxPossibleScore(values)} />
            </div>
          ) : null}
        </Section>
      ))}
    </div>
  );
}

function SettingInput({ field, form }: { field: SettingField; form: UseFormReturn<SettingsFormValues> }) {
  const { currency } = useStore();
  const id = `setting-${field.name}`;
  const error = form.formState.errors[field.name]?.message;
  return (
    <div className="flex min-w-0 flex-col gap-1.5">
      <Label htmlFor={id}>
        {field.label}
        <span className="sr-only">, {unitSpoken(field.unit, currency)}</span>
      </Label>
      <div className="relative w-full sm:max-w-56">
        <Input
          id={id}
          inputMode={field.kind === "int" ? "numeric" : "decimal"}
          autoComplete="off"
          className="pr-14 tabular-nums"
          aria-invalid={error ? true : undefined}
          aria-describedby={error ? `${id}-error ${id}-help` : `${id}-help`}
          {...form.register(field.name)}
        />
        <span aria-hidden className="pointer-events-none absolute top-1/2 right-3 -translate-y-1/2 text-sm text-muted-foreground">
          {unitSuffix(field.unit, currency)}
        </span>
      </div>
      <p id={`${id}-help`} className="text-xs font-normal text-muted-foreground">
        {field.group ? "" : field.helper ? `${field.helper} ` : ""}Default {formatSetting(field, field.defaultValue, currency)}.
      </p>
      <FieldError id={`${id}-error`} message={error} />
    </div>
  );
}

function SectionFields({ section, form }: { section: SectionId; form: UseFormReturn<SettingsFormValues> }) {
  const fields = SETTING_FIELDS.filter((field) => field.section === section);
  const ungrouped = fields.filter((field) => !field.group);
  const groups = [...new Set(fields.flatMap((field) => (field.group ? [field.group] : [])))];
  return (
    <div className="flex flex-col gap-6">
      {ungrouped.length ? (
        <div className="grid grid-cols-1 gap-4">
          {ungrouped.map((field) => (
            <SettingInput key={field.name} field={field} form={form} />
          ))}
        </div>
      ) : null}
      {groups.map((group) => {
        const members = fields.filter((field) => field.group === group);
        const helper = members.find((field) => field.helper)?.helper;
        return (
          <fieldset key={group} className="flex min-w-0 flex-col gap-3">
            <legend className="text-body-strong">{group}</legend>
            {helper ? <p className="-mt-2 text-sm text-muted-foreground">{helper}</p> : null}
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              {members.map((field) => (
                <SettingInput key={field.name} field={field} form={form} />
              ))}
            </div>
          </fieldset>
        );
      })}
    </div>
  );
}

/** Warns before closing the tab with unsaved changes (S-16 navigation guard). */
function useUnsavedChangesWarning(active: boolean) {
  useEffect(() => {
    if (!active) return;
    const warn = (event: BeforeUnloadEvent) => event.preventDefault();
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [active]);
}

function SettingsForm({
  initial,
  latest,
  refetch,
  onSaved,
  onReload,
}: {
  initial: StoreSettings;
  latest: StoreSettings;
  refetch: () => Promise<StoreSettings | undefined>;
  onSaved: (settings: StoreSettings) => void;
  onReload: () => void;
}) {
  const store = useStore();
  const queryClient = useQueryClient();
  const form = useForm<SettingsFormValues>({
    resolver: zodResolver(settingsSchema),
    mode: "onTouched",
    defaultValues: toFormValues(initial),
  });
  const watched = useWatch({ control: form.control }) as SettingsFormValues;
  const values = { ...toFormValues(initial), ...watched };
  const changes = changedFields(values, initial);
  const score = maxPossibleScore(values);
  const overLimit = score !== null && score > MAX_PRIORITY_SCORE;
  const stale = settingsSignature(latest) !== settingsSignature(initial);
  const [confirm, setConfirm] = useState<{ changes: SettingChange[]; body: StoreSettingsUpdate } | null>(null);
  const [checking, setChecking] = useState(false);
  useUnsavedChangesWarning(changes.length > 0);

  const save = useMutation({
    mutationFn: (body: StoreSettingsUpdate) => adminApi.updateSettings(store.id, body),
    onSuccess: (updated) => {
      queryClient.setQueryData(adminKeys.settings(store.id), updated);
      toast.success("Settings saved. They apply from the next evaluation.");
      setConfirm(null);
      onSaved(updated);
    },
    onError: (error) => {
      setConfirm(null);
      for (const [path, message] of validationFieldErrors(error)) {
        const field = FIELD_BY_PATH.get(path);
        if (field) form.setError(field.name, { message });
      }
    },
  });

  const review = async (submitted: SettingsFormValues) => {
    if (overLimit) {
      document.getElementById("priority-guard")?.focus();
      return;
    }
    const pending = changedFields(submitted, initial);
    if (pending.length === 0) return;
    setChecking(true);
    try {
      const fresh = await refetch();
      // Someone else saved meanwhile: the conflict alert explains, nothing is sent.
      if (fresh && settingsSignature(fresh) !== settingsSignature(initial)) return;
    } finally {
      setChecking(false);
    }
    save.reset();
    setConfirm({ changes: pending, body: buildUpdate(submitted, pending) });
  };

  const resetSection = (section: SectionId) => {
    for (const field of SETTING_FIELDS.filter((candidate) => candidate.section === section)) {
      form.setValue(field.name, field.defaultValue, { shouldDirty: true, shouldValidate: true });
    }
  };

  return (
    <form id="settings-form" noValidate className="flex flex-col gap-8" onSubmit={form.handleSubmit(review)}>
      {stale ? (
        <Alert tone="warning" role="alert">
          <TriangleAlert aria-hidden />
          <AlertDescription>
            <p>
              Settings were changed by someone else. Reload to see the latest values.
              {changes.length > 0 ? " Your edits will be lost." : ""}
            </p>
            <Button type="button" variant="secondary" size="sm" onClick={onReload}>
              Reload
            </Button>
          </AlertDescription>
        </Alert>
      ) : null}
      {SECTIONS.map((section) => (
        <Section
          key={section.id}
          id={`settings-${section.id}`}
          title={section.title}
          aside={
            <Button type="button" variant="ghost" size="sm" onClick={() => resetSection(section.id)}>
              <RotateCcw aria-hidden />
              Reset section to defaults
            </Button>
          }
        >
          <SectionFields section={section.id} form={form} />
          {section.id === "priority" ? (
            <div className="mt-4 flex flex-col gap-2">
              <ScoreLine score={score} />
              {overLimit ? (
                <div id="priority-guard" tabIndex={-1} className="outline-none">
                  <Alert tone="danger">
                    <CircleAlert aria-hidden />
                    <AlertDescription>
                      The maximum possible score is {score}. It must be {MAX_PRIORITY_SCORE} or less.
                    </AlertDescription>
                  </Alert>
                </div>
              ) : null}
            </div>
          ) : null}
        </Section>
      ))}

      {changes.length > 0 || save.isError ? (
        <div role="region" aria-label="Unsaved changes" className="sticky bottom-0 z-10 flex flex-col gap-3 rounded-lg border bg-card p-3 shadow-popover">
          {save.isError ? <ServerError error={save.error} /> : null}
          <div className="flex flex-col gap-2 min-[400px]:flex-row min-[400px]:items-center min-[400px]:justify-between">
            <p className="text-body-strong" aria-live="polite">
              {plural(changes.length, "unsaved change")}
            </p>
            <div className="flex flex-col gap-2 min-[400px]:flex-row">
              <Button
                type="button"
                variant="secondary"
                disabled={save.isPending}
                onClick={() => {
                  form.reset(toFormValues(initial));
                  save.reset();
                }}
              >
                Discard
              </Button>
              <Button type="submit" disabled={changes.length === 0} pending={checking} pendingLabel="Checking…">
                Save changes
              </Button>
            </div>
          </div>
        </div>
      ) : null}

      <Dialog open={confirm !== null} onOpenChange={(open) => !open && !save.isPending && setConfirm(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Save {plural(confirm?.changes.length ?? 0, "change")}?</DialogTitle>
            <DialogDescription>
              Changes apply from the next evaluation. Existing exceptions are re-ranked then. The change is recorded in the audit log.
            </DialogDescription>
          </DialogHeader>
          <ul className="flex flex-col gap-1 text-body">
            {confirm?.changes.map(({ field, from, to }) => (
              <li key={field.name} className="break-words">
                <span className="font-medium">{changeLabel(field)}:</span> {formatSetting(field, from, store.currency)} →{" "}
                {formatSetting(field, to, store.currency)}
              </li>
            ))}
          </ul>
          <DialogFooter>
            <Button type="button" variant="secondary" disabled={save.isPending} onClick={() => setConfirm(null)}>
              Cancel
            </Button>
            <Button type="button" pending={save.isPending} pendingLabel="Saving…" onClick={() => confirm && save.mutate(confirm.body)}>
              Save changes
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </form>
  );
}
