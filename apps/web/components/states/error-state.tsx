"use client";

import { CircleAlert, Clock } from "lucide-react";

import { Button } from "@/components/ui/button";
import { isApiError, userMessage } from "@/lib/api/errors";
import { useCountdown } from "@/lib/hooks/use-countdown";
import { cn } from "@/lib/utils";

import { CopyButton } from "./copy-button";

type ErrorStateProps = {
  title: string;
  error?: unknown;
  onRetry?: () => void;
  size?: "page" | "section";
  className?: string;
};

/**
 * "API error with retry" and "Rate limited" states (SCREEN_SPECIFICATIONS §0.3,
 * COMPONENT_INVENTORY C-35). Shows the request ID so a failure can be traced in the logs.
 */
export function ErrorState({ title, error, onRetry, size = "section", className }: ErrorStateProps) {
  const apiError = isApiError(error) ? error : undefined;
  const rateLimited = apiError?.status === 429;
  const secondsLeft = useCountdown(rateLimited ? (apiError?.retryAfterSeconds ?? 60) : undefined, error);
  const waiting = rateLimited && secondsLeft > 0;

  return (
    <div
      role="status"
      className={cn(
        "flex flex-col items-center gap-3 text-center",
        size === "page" ? "mx-auto max-w-md py-16" : "py-10",
        className,
      )}
    >
      <span className="flex size-10 items-center justify-center rounded-full bg-muted text-muted-foreground">
        {rateLimited ? <Clock aria-hidden className="size-6" /> : <CircleAlert aria-hidden className="size-6" />}
      </span>
      <h2 className={size === "page" ? "text-title" : "text-title-sm"}>{title}</h2>
      <p className="max-w-prose text-body text-muted-foreground">
        {rateLimited
          ? waiting
            ? `Too many requests. Try again in ${secondsLeft} s.`
            : "You can try again now."
          : userMessage(error)}
      </p>
      {apiError?.requestId ? (
        <p className="flex items-center gap-1 text-xs text-muted-foreground">
          Request ID <code className="font-mono text-mono slashed-zero">{apiError.requestId}</code>
          <CopyButton value={apiError.requestId} label="Copy request ID" />
        </p>
      ) : null}
      {onRetry ? (
        <Button
          type="button"
          variant="secondary"
          onClick={onRetry}
          aria-disabled={waiting || undefined}
        >
          Try again
        </Button>
      ) : null}
    </div>
  );
}
