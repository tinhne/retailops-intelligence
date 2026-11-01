import { screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { mockFetch } from "@/test/fetch";
import { renderWithProviders } from "@/test/render";

import { DemoScreen } from "./demo-screen";

vi.mock("next/navigation", () => ({ useRouter: () => ({ replace: vi.fn(), push: vi.fn() }) }));

describe("DemoScreen (/demo)", () => {
  it("offers the demo where the installation has one", async () => {
    mockFetch();
    renderWithProviders(<DemoScreen />);
    expect(await screen.findByRole("button", { name: "Start the demo" })).toBeEnabled();
  });

  it("explains and links to sign-in where there is no demo", async () => {
    mockFetch();
    renderWithProviders(<DemoScreen />, { demoAvailable: false });
    expect(await screen.findByRole("status")).toHaveTextContent("This installation does not offer the public demo.");
    expect(screen.queryByRole("button", { name: "Start the demo" })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Sign in with a workspace account" })).toHaveAttribute("href", "/login");
  });
});
