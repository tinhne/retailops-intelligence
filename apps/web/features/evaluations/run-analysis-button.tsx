"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Play } from "lucide-react";
import { useRef } from "react";
import { toast } from "sonner";

import { ActionButton } from "@/components/actions/action-button";
import { isApiError, userMessage } from "@/lib/api/errors";
import { storeApi, storeKeys, type EvaluationRun } from "@/lib/api/store-api";
import type { Gate } from "@/lib/permissions";
import { usePermission, useStore } from "@/lib/store/store-context";

const POLL_INTERVAL_MS = 2000;
const POLL_LIMIT = 30;
const SKIPPED_REFETCH_MS = 15_000;

const wait = (ms: number) => new Promise((resolve) => window.setTimeout(resolve, ms));

/** "Analysis complete: 2 new, 5 refreshed, 1 resolved, 0 reopened" (S-02 success toast). */
export function completionMessage(counts: Record<string, number>): string {
  const n = (key: string) => counts[key] ?? 0;
  return `Analysis complete: ${n("created")} new, ${n("refreshed")} refreshed, ${n("resolved")} resolved, ${n("reopened")} reopened`;
}

/**
 * "Run analysis" (COMPONENT_INVENTORY C-61): a synchronous manual evaluation. The Idempotency-Key
 * is created on click and reused if the same attempt is retried after an error, so a retry never
 * starts a second run.
 */
export function RunAnalysisButton({ running = false }: { running?: boolean }) {
  const store = useStore();
  const queryClient = useQueryClient();
  const permission = usePermission("evaluations.run");
  const keyRef = useRef<string | null>(null);

  const gate: Gate = !permission.allowed
    ? permission
    : running
      ? { allowed: false, reason: "An analysis is already running." }
      : { allowed: true };

  const mutation = useMutation({
    mutationFn: async (): Promise<EvaluationRun> => {
      keyRef.current ??= crypto.randomUUID();
      let run = await storeApi.runEvaluation(store.id, keyRef.current);
      for (let attempt = 0; run.status === "RUNNING" && attempt < POLL_LIMIT; attempt += 1) {
        await wait(POLL_INTERVAL_MS);
        run = await storeApi.evaluation(store.id, run.id);
      }
      return run;
    },
    onSuccess: (run) => {
      keyRef.current = null;
      if (run.status === "SUCCEEDED") {
        toast.success(completionMessage(run.counts));
      } else if (run.status === "SKIPPED") {
        toast.info("An analysis is already running. Results will appear when it finishes.");
        window.setTimeout(
          () => void queryClient.invalidateQueries({ queryKey: storeKeys.dashboard(store.id) }),
          SKIPPED_REFETCH_MS,
        );
      } else if (run.status === "FAILED") {
        toast.error("Analysis failed. No exceptions were changed.");
      } else {
        toast.info("The analysis is still running. Results will appear when it finishes.");
      }
      void queryClient.invalidateQueries({ queryKey: storeKeys.all(store.id) });
    },
    onError: (error) => {
      if (isApiError(error) && error.status === 401) return; // handled by the session redirect
      toast.error(userMessage(error), {
        description: isApiError(error) && error.requestId ? `Request ID ${error.requestId}` : undefined,
      });
    },
  });

  return (
    <ActionButton
      gate={gate}
      type="button"
      pending={mutation.isPending}
      pendingLabel="Running analysis…"
      onClick={() => mutation.mutate()}
    >
      <Play aria-hidden />
      Run analysis
    </ActionButton>
  );
}
