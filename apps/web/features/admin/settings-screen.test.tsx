import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { toast } from "sonner";
import { describe, expect, it, vi } from "vitest";

import type { StoreSettings } from "@/lib/api/admin-api";
import type { Permission } from "@/lib/api/auth";
import { methodFetch, sentBody, settingsFixture } from "@/test/admin-fixtures";
import { errorResponse, jsonResponse } from "@/test/fetch";
import { renderInStore, testStore } from "@/test/render";

import { buildUpdate, changedFields, fieldProblem, maxPossibleScore, normalise, SETTING_FIELDS, toFormValues } from "./settings-fields";
import { SettingsScreen } from "./settings-screen";

const EDITOR: Permission[] = ["settings.read", "settings.manage"];
const field = (path: string) => SETTING_FIELDS.find((candidate) => candidate.path === path)!;

function routes(options: { reads?: StoreSettings[]; patch?: () => Response } = {}) {
  const reads = options.reads ?? [settingsFixture()];
  let call = 0;
  return methodFetch({
    "GET /settings": () => jsonResponse(reads[Math.min(call++, reads.length - 1)]),
    "PATCH /settings": options.patch ?? (() => jsonResponse(settingsFixture())),
  });
}

async function edit(user: ReturnType<typeof userEvent.setup>, name: string, value: string) {
  const input = await screen.findByRole("textbox", { name });
  await user.clear(input);
  await user.type(input, value);
  await user.tab();
  return input;
}

describe("SettingsScreen (S-16)", () => {
  it("saves only the changed fields after confirming old → new", async () => {
    const success = vi.spyOn(toast, "success");
    const fetchMock = routes({ patch: () => jsonResponse(settingsFixture({ fulfillment_sla_hours: 36, updated_at: "2026-10-31T15:00:00Z" })) });
    const user = userEvent.setup();
    renderInStore(<SettingsScreen />, testStore({ permissions: EDITOR }));
    expect(screen.getByRole("heading", { level: 1, name: "Settings" })).toBeInTheDocument();

    await edit(user, "Fulfillment SLA, hours", "36");
    const bar = screen.getByRole("region", { name: "Unsaved changes" });
    expect(within(bar).getByText("1 unsaved change")).toBeInTheDocument();
    await user.click(within(bar).getByRole("button", { name: "Save changes" }));

    const dialog = await screen.findByRole("dialog", { name: "Save 1 change?" });
    expect(within(dialog).getByText(/48 h → 36 h/)).toBeInTheDocument();
    expect(within(dialog).getByText(/recorded in the audit log/)).toBeInTheDocument();
    await user.click(within(dialog).getByRole("button", { name: "Save changes" }));

    await waitFor(() => expect(success).toHaveBeenCalledWith("Settings saved. They apply from the next evaluation."));
    expect(sentBody(fetchMock, "PATCH", "/settings")).toEqual({ fulfillment_sla_hours: 36 });
    await waitFor(() => expect(screen.queryByRole("region", { name: "Unsaved changes" })).not.toBeInTheDocument());
    expect(screen.getByRole("textbox", { name: "Fulfillment SLA, hours" })).toHaveValue("36");
  });

  it("validates inputs against the API's limits", async () => {
    routes();
    const user = userEvent.setup();
    renderInStore(<SettingsScreen />, testStore({ permissions: EDITOR }));
    await edit(user, "Fulfillment SLA, hours", "0");
    expect(await screen.findByText("Enter a whole number from 1 to 8,760.")).toBeInTheDocument();
    await edit(user, "Approaching reorder factor, times", "1.255");
    expect(await screen.findByText("Enter a number with at most 2 decimal places.")).toBeInTheDocument();
    await edit(user, "Sales velocity window, days", "6");
    expect(await screen.findByText("Enter a whole number from 7 to 90.")).toBeInTheDocument();
    await edit(user, "Exposure cap, USD", "0");
    expect(await screen.findByText("Enter an amount above 0.00 and at most 9,999,999,999.99.")).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "Exposure cap, USD" })).toHaveAttribute("aria-invalid", "true");
  });

  it("blocks weights whose maximum score exceeds 100 and sends all weights otherwise", async () => {
    const fetchMock = routes();
    const user = userEvent.setup();
    renderInStore(<SettingsScreen />, testStore({ permissions: EDITOR }));
    expect(await screen.findByText("Maximum possible score: 100 of 100")).toBeInTheDocument();

    await edit(user, "Critical, points", "60");
    expect(await screen.findByText("The maximum possible score is 110. It must be 100 or less.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Save changes" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();

    await edit(user, "Critical, points", "45");
    await edit(user, "Time unresolved cap, points", "13");
    expect(await screen.findByText("Maximum possible score: 100 of 100")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Save changes" }));
    const dialog = await screen.findByRole("dialog", { name: "Save 2 changes?" });
    expect(within(dialog).getByText(/Severity · Critical/)).toBeInTheDocument();
    await user.click(within(dialog).getByRole("button", { name: "Save changes" }));
    await waitFor(() =>
      expect(sentBody(fetchMock, "PATCH", "/settings")).toEqual({
        priority_weights: {
          severity: { CRITICAL: 45, HIGH: 35, MEDIUM: 20, LOW: 8 },
          affected_orders_per_order: 3,
          affected_orders_cap: 15,
          exposure_cap_points: 15,
          deadline: { overdue: 12, within_24h: 8, within_72h: 4 },
          age_points_per_day: 2,
          age_cap: 13,
        },
      }),
    );
  });

  it("refuses to save over a change made by someone else", async () => {
    const fetchMock = routes({ reads: [settingsFixture(), settingsFixture({ fulfillment_sla_hours: 24, updated_at: "2026-10-31T16:00:00Z" })] });
    const user = userEvent.setup();
    renderInStore(<SettingsScreen />, testStore({ permissions: EDITOR }));
    await edit(user, "Stalled after, hours", "10");
    await user.click(screen.getByRole("button", { name: "Save changes" }));
    expect(
      await screen.findByText("Settings were changed by someone else. Reload to see the latest values. Your edits will be lost."),
    ).toBeInTheDocument();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(fetchMock.mock.calls.some(([, init]) => init?.method === "PATCH")).toBe(false);
    await user.click(screen.getByRole("button", { name: "Reload" }));
    expect(await screen.findByRole("textbox", { name: "Fulfillment SLA, hours" })).toHaveValue("24");
    expect(screen.getByRole("textbox", { name: "Stalled after, hours" })).toHaveValue("12");
  });

  it("maps a server 422 to the field and keeps the values", async () => {
    routes({
      patch: () =>
        errorResponse(422, "VALIDATION_FAILED", "Request validation failed.", {
          requestId: "req-7",
          details: [{ loc: ["body", "velocity_window_days"], message: "Input should be less than or equal to 90", type: "less_than_equal" }],
        }),
    });
    const user = userEvent.setup();
    renderInStore(<SettingsScreen />, testStore({ permissions: EDITOR }));
    await edit(user, "Sales velocity window, days", "30");
    await user.click(screen.getByRole("button", { name: "Save changes" }));
    await user.click(within(await screen.findByRole("dialog")).getByRole("button", { name: "Save changes" }));
    expect(await screen.findByText("Input should be less than or equal to 90")).toBeInTheDocument();
    const bar = screen.getByRole("region", { name: "Unsaved changes" });
    expect(within(bar).getByText("req-7")).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "Sales velocity window, days" })).toHaveValue("30");
  });

  it("discards edits and resets a section to its defaults", async () => {
    routes({ reads: [settingsFixture({ fulfillment_sla_hours: 36 })] });
    const user = userEvent.setup();
    renderInStore(<SettingsScreen />, testStore({ permissions: EDITOR }));
    await edit(user, "Refund overdue after, hours", "30");
    await user.click(screen.getByRole("button", { name: "Discard" }));
    expect(screen.getByRole("textbox", { name: "Refund overdue after, hours" })).toHaveValue("24");
    expect(screen.queryByRole("region", { name: "Unsaved changes" })).not.toBeInTheDocument();

    const fulfillment = screen.getByRole("region", { name: "Fulfillment" });
    await user.click(within(fulfillment).getByRole("button", { name: "Reset section to defaults" }));
    expect(screen.getByRole("textbox", { name: "Fulfillment SLA, hours" })).toHaveValue("48");
    expect(within(screen.getByRole("region", { name: "Unsaved changes" })).getByText("1 unsaved change")).toBeInTheDocument();
  });

  it("shows readers values with defaults instead of inputs", async () => {
    routes({ reads: [settingsFixture({ fulfillment_sla_hours: 36 })] });
    renderInStore(<SettingsScreen />, testStore({ permissions: ["settings.read"], role: "ANALYST" }));
    expect(await screen.findByText("Only owners and managers can change settings.")).toBeInTheDocument();
    expect(screen.queryAllByRole("textbox")).toHaveLength(0);
    expect(screen.getByText("36 h")).toBeInTheDocument();
    expect(screen.getByText("Default 48 h")).toBeInTheDocument();
    expect(screen.getByText("$5,000.00")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Reset section/ })).not.toBeInTheDocument();
  });

  it("tells demo visitors the demo is read-only", async () => {
    routes();
    renderInStore(<SettingsScreen />, testStore({ permissions: ["settings.read"], role: "VIEWER", isDemo: true }));
    expect(await screen.findByText("The public demo is read-only.")).toBeInTheDocument();
  });

  it("shows an error with retry when settings fail to load", async () => {
    methodFetch({ "GET /settings": () => errorResponse(503, "UNAVAILABLE", "down") });
    renderInStore(<SettingsScreen />, testStore({ permissions: EDITOR }));
    expect(await screen.findByRole("heading", { name: "Couldn't load settings" })).toBeInTheDocument();
    expect(screen.getByText("The service is temporarily unavailable.")).toBeInTheDocument();
  });

  it("shows permission denied without settings.read", () => {
    renderInStore(<SettingsScreen />, testStore({ permissions: [] }));
    expect(screen.getByRole("heading", { name: "You don't have access to settings" })).toBeInTheDocument();
  });
});

describe("settings form model", () => {
  it("mirrors the API limits", () => {
    expect(fieldProblem(field("fulfillment_sla_hours"), "8760")).toBeNull();
    expect(fieldProblem(field("fulfillment_sla_hours"), "8761")).toMatch(/1 to 8,760/);
    expect(fieldProblem(field("fulfillment_sla_hours"), "4.5")).toBe("Enter a whole number.");
    expect(fieldProblem(field("approaching_reorder_factor"), "3.00")).toBeNull();
    expect(fieldProblem(field("approaching_reorder_factor"), "3.01")).toMatch(/1.00 to 3.00/);
    expect(fieldProblem(field("exposure_cap"), "9999999999.99")).toBeNull();
    expect(fieldProblem(field("exposure_cap"), "10000000000.00")).not.toBeNull();
    expect(fieldProblem(field("exposure_cap"), "0.01")).toBeNull();
    expect(fieldProblem(field("priority_weights.age_cap"), "101")).toMatch(/0 to 100/);
  });

  it("compares normalised values and builds a partial body with decimals as strings", () => {
    const saved = settingsFixture();
    const values = { ...toFormValues(saved), approaching_reorder_factor: "1.3", exposure_cap: "5000", fulfillment_sla_hours: "048" };
    const changes = changedFields(values, saved);
    expect(changes.map((change) => change.field.path)).toEqual(["approaching_reorder_factor"]);
    expect(normalise(field("approaching_reorder_factor"), "1.3")).toBe("1.30");
    expect(buildUpdate(values, changes)).toEqual({ approaching_reorder_factor: "1.30" });
  });

  it("computes the maximum possible score like PriorityWeights", () => {
    const values = toFormValues(settingsFixture());
    expect(maxPossibleScore(values)).toBe(100);
    expect(maxPossibleScore({ ...values, priority_weights__deadline__within_72h: "20" })).toBe(108);
    expect(maxPossibleScore({ ...values, priority_weights__age_cap: "x" })).toBeNull();
  });
});
