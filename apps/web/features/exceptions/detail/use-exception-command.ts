"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { isApiError, userMessage } from "@/lib/api/errors";
import { exceptionKeys, type ExceptionDetail } from "@/lib/api/exceptions-api";
import { storeKeys } from "@/lib/api/store-api";
import { exceptionStatusLabels } from "@/lib/status-maps";
import { useStore } from "@/lib/store/store-context";

export type CommandOutcome = "done" | "stale" | "conflict" | "failed";

/** Versions this tab produced, so a refetch can tell its own changes from other people's. */
const ownVersions = new Map<string, Set<number>>();

export function isOwnVersion(exceptionId: string, version: number): boolean {
  return ownVersions.get(exceptionId)?.has(version) ?? false;
}

type CommandOptions = {
  /** Toast after success, built from the updated exception. */
  successMessage?: (updated: ExceptionDetail) => string | null;
  /** One action on that toast, e.g. "Next in queue" (§0.3 "Success toast"). */
  successAction?: { label: string; onClick: () => void };
};

/**
 * Runs one lifecycle command against the version on screen (DESIGN_SYSTEM §10, S-04 Conflict).
 * Updates the cache with the server's answer, refreshes events, notes and lists, and turns
 * conflicts into the documented toasts. Never optimistic: the server may refuse a transition.
 */
export function useExceptionCommand(exception: ExceptionDetail) {
  const store = useStore();
  const queryClient = useQueryClient();

  const refresh = () =>
    Promise.all([
      queryClient.invalidateQueries({ queryKey: exceptionKeys.detail(store.id, exception.id) }),
      queryClient.invalidateQueries({ queryKey: storeKeys.dashboard(store.id) }),
      queryClient.invalidateQueries({ queryKey: exceptionKeys.all(store.id) }),
    ]);

  const mutation = useMutation({
    mutationFn: ({ run }: { run: (version: number) => Promise<ExceptionDetail | unknown>; options?: CommandOptions }) =>
      run(exception.version),
    onSuccess: (result, { options }) => {
      const updated = isDetail(result) ? result : undefined;
      if (updated) {
        const versions = ownVersions.get(exception.id) ?? new Set<number>();
        versions.add(updated.version);
        ownVersions.set(exception.id, versions);
        queryClient.setQueryData(exceptionKeys.detail(store.id, exception.id), updated);
      }
      void refresh();
      const message = updated ? options?.successMessage?.(updated) : null;
      if (message && options?.successAction) toast.success(message, { action: options.successAction });
      else if (message) toast.success(message);
    },
  });

  /** Runs the command; resolves to what happened so a dialog knows whether to stay open. */
  async function run(
    command: (version: number) => Promise<ExceptionDetail | unknown>,
    options?: CommandOptions,
  ): Promise<{ outcome: CommandOutcome; error?: unknown }> {
    try {
      await mutation.mutateAsync({ run: command, options });
      return { outcome: "done" };
    } catch (error) {
      if (isApiError(error) && error.status === 401) return { outcome: "failed", error };
      if (isApiError(error) && error.code === "STALE_VERSION") {
        toast.warning(`Someone else updated ${exception.reference}. The latest details are now shown. Review them and try again.`);
        await refresh();
        return { outcome: "stale", error };
      }
      if (isApiError(error) && error.status === 409) {
        await refresh();
        const latest = queryClient.getQueryData<ExceptionDetail>(exceptionKeys.detail(store.id, exception.id));
        toast.warning(
          latest && latest.status !== exception.status
            ? `${exception.reference} is now ${exceptionStatusLabels[latest.status]}. No change was made.`
            : error.message,
        );
        return { outcome: "conflict", error };
      }
      return { outcome: "failed", error };
    }
  }

  return { run, pending: mutation.isPending };
}

function isDetail(value: unknown): value is ExceptionDetail {
  return typeof value === "object" && value !== null && "version" in value && "status" in value;
}

/** Error text for an inline alert in a dialog (non-conflict failures keep the input). */
export function commandErrorMessage(error: unknown): string {
  return userMessage(error);
}
