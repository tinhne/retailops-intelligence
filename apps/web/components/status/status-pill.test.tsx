import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ExceptionStatusPill, PriorityIndicator, SeverityBadge } from "./status-pill";

describe("status atoms (DESIGN_SYSTEM §3.5, §12)", () => {
  it("names severity with its dimension and marks only Critical as solid", () => {
    const { container, rerender } = render(<SeverityBadge severity="CRITICAL" />);
    expect(screen.getByText("Critical")).toBeInTheDocument();
    expect(container.textContent).toBe("Severity: Critical");
    expect(container.firstElementChild).toHaveClass("bg-tone-danger-solid-bg");
    rerender(<SeverityBadge severity="HIGH" />);
    expect(container.firstElementChild).not.toHaveClass("bg-tone-danger-solid-bg");
  });

  it.each([
    [{ resolutionCode: "STOCK_REPLENISHED" as const, verifiedAt: null }, "Resolved — awaiting verification", "bg-tone-info-bg"],
    [{ resolutionCode: "STOCK_REPLENISHED" as const, verifiedAt: "2026-11-01T00:00:00Z" }, "Verified", "bg-tone-success-bg"],
    [{ resolutionCode: "CONDITION_CLEARED" as const, verifiedAt: null }, "Resolved · condition cleared", "bg-tone-success-bg"],
    [{ resolutionCode: "SUPERSEDED" as const, verifiedAt: null }, "Superseded", "bg-tone-muted-bg"],
  ])("never shows a manual resolution as success before verification (%#)", (props, label, toneClass) => {
    const { container } = render(<ExceptionStatusPill status="RESOLVED" {...props} />);
    expect(screen.getByText(label)).toBeInTheDocument();
    expect(container.firstElementChild).toHaveClass(toneClass);
  });

  it("reads priority as band and score, with decorative bars", () => {
    render(<PriorityIndicator band="P2" score={63} />);
    expect(screen.getByRole("img", { name: "Priority P2, score 63 of 100" })).toBeInTheDocument();
  });
});
