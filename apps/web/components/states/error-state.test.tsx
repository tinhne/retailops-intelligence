import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { TooltipProvider } from "@/components/ui/tooltip";
import { ApiError } from "@/lib/api/errors";

import { ErrorState } from "./error-state";

const renderState = (ui: React.ReactElement) => render(<TooltipProvider>{ui}</TooltipProvider>);

describe("ErrorState (C-35)", () => {
  it("shows a generic message and the request ID for server errors", () => {
    renderState(
      <ErrorState
        title="Couldn't load exceptions"
        error={new ApiError({ status: 500, code: "INTERNAL_ERROR", message: "boom", requestId: "req-1" })}
      />,
    );
    expect(screen.getByRole("heading", { name: "Couldn't load exceptions" })).toBeInTheDocument();
    expect(screen.getByText("Something went wrong on our side.")).toBeInTheDocument();
    expect(screen.getByText("req-1")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Copy request ID" })).toBeInTheDocument();
  });

  it("retries on request", async () => {
    const onRetry = vi.fn();
    renderState(
      <ErrorState title="Couldn't load orders" error={new ApiError({ status: 503, code: "X", message: "x" })} onRetry={onRetry} />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(onRetry).toHaveBeenCalledOnce();
  });

  it("blocks retry during a rate-limit countdown", async () => {
    const onRetry = vi.fn();
    renderState(
      <ErrorState
        title="Couldn't load orders"
        error={new ApiError({ status: 429, code: "RATE_LIMITED", message: "x", retryAfterSeconds: 34 })}
        onRetry={onRetry}
      />,
    );
    expect(screen.getByText("Too many requests. Try again in 34 s.")).toBeInTheDocument();
    const button = screen.getByRole("button", { name: "Try again" });
    expect(button).toHaveAttribute("aria-disabled", "true");
    await userEvent.click(button);
    expect(onRetry).not.toHaveBeenCalled();
  });
});
