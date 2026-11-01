import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { errorResponse, jsonResponse, mockFetch } from "@/test/fetch";
import { renderWithProviders } from "@/test/render";

import { LoginScreen } from "./login-screen";

const replace = vi.fn();
let search = new URLSearchParams();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace, push: vi.fn() }),
  useSearchParams: () => search,
}));

const me = {
  user: { id: "u1", email: "staff@kestrel.example", full_name: "Marcus Lee" },
  memberships: [
    {
      organization_id: "o1",
      organization_name: "Kestrel Commerce",
      is_demo: true,
      role: "STAFF",
      permissions: ["dashboard.read"],
      stores: [{ id: "store-1", name: "Kestrel Home & Kitchen", code: "KHK", currency: "USD", timezone: "America/New_York" }],
    },
  ],
  csrf_token: "t",
};

/** `GET /auth/csrf`: every sign-in attempt fetches a pre-session CSRF token first (ADR-0004). */
const csrf = () => jsonResponse({ csrf_token: "pre-session-token" });

function expectSignInRequest(fetchMock: ReturnType<typeof mockFetch>, path: string) {
  expect(fetchMock.mock.calls[0][0]).toBe("/api/v1/auth/csrf");
  const [url, init] = fetchMock.mock.calls[1];
  expect(url).toBe(path);
  expect(init?.method).toBe("POST");
  expect((init?.headers as Record<string, string>)["X-CSRF-Token"]).toBe("pre-session-token");
}

async function fillAndSubmit(email: string, password: string) {
  const user = userEvent.setup();
  await user.type(await screen.findByLabelText("Email"), email);
  await user.type(screen.getByLabelText("Password"), password);
  await user.click(screen.getByRole("button", { name: "Sign in" }));
  return user;
}

describe("LoginScreen (S-01)", () => {
  beforeEach(() => {
    replace.mockReset();
    search = new URLSearchParams();
  });

  it("validates both fields before calling the API", async () => {
    const fetchMock = mockFetch();
    const user = userEvent.setup();
    renderWithProviders(<LoginScreen />);

    await user.click(await screen.findByRole("button", { name: "Sign in" }));

    expect(await screen.findByText("Enter your email address.")).toBeInTheDocument();
    expect(screen.getByText("Enter your password.")).toBeInTheDocument();
    expect(screen.getByLabelText("Email")).toHaveAttribute("aria-invalid", "true");
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("explains a malformed email address", async () => {
    mockFetch();
    renderWithProviders(<LoginScreen />);
    await fillAndSubmit("not-an-email", "secret");
    expect(await screen.findByText("Enter an email address like name@company.com")).toBeInTheDocument();
  });

  it("shows the generic credentials message on 401, keeps the email and clears the password", async () => {
    const fetchMock = mockFetch(csrf(), errorResponse(401, "INVALID_CREDENTIALS", "Invalid email or password."));
    renderWithProviders(<LoginScreen />);

    await fillAndSubmit("staff@kestrel.example", "wrong");

    expect(await screen.findByRole("alert")).toHaveTextContent("Email or password is incorrect.");
    expectSignInRequest(fetchMock, "/api/v1/auth/login");
    expect(screen.getByLabelText("Email")).toHaveValue("staff@kestrel.example");
    expect(screen.getByLabelText("Password")).toHaveValue("");
    expect(replace).not.toHaveBeenCalled();
  });

  it("counts down after a 429 and keeps the button focusable but inert", async () => {
    const fetchMock = mockFetch(
      csrf(),
      errorResponse(429, "RATE_LIMITED", "Too many attempts.", { headers: { "retry-after": "60" } }),
    );
    renderWithProviders(<LoginScreen />);

    const user = await fillAndSubmit("staff@kestrel.example", "wrong");

    expect(await screen.findByRole("alert")).toHaveTextContent("Too many sign-in attempts. Try again in 60 s.");
    const button = screen.getByRole("button", { name: "Sign in" });
    expect(button).toHaveAttribute("aria-disabled", "true");

    await user.type(screen.getByLabelText("Password"), "again");
    await user.click(button);
    expect(fetchMock).toHaveBeenCalledTimes(2); // the token and the refused attempt; no retry
  });

  it("shows the request ID when sign-in is unavailable", async () => {
    mockFetch(csrf(), errorResponse(503, "UNAVAILABLE", "Down.", { requestId: "req-503" }));
    renderWithProviders(<LoginScreen />);
    await fillAndSubmit("staff@kestrel.example", "secret");
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Sign-in is unavailable right now. Try again in a moment.");
    expect(alert).toHaveTextContent("req-503");
  });

  it("redirects to a same-origin next path after signing in", async () => {
    search = new URLSearchParams({ next: "/s/store-1/overview" });
    const fetchMock = mockFetch(csrf(), jsonResponse(me));
    renderWithProviders(<LoginScreen />);

    await fillAndSubmit("staff@kestrel.example", "secret");

    await waitFor(() => expect(replace).toHaveBeenCalledWith("/s/store-1/overview"));
    expectSignInRequest(fetchMock, "/api/v1/auth/login");
  });

  it("explains a failed CSRF token request like any unavailable sign-in", async () => {
    const fetchMock = mockFetch(errorResponse(503, "UNAVAILABLE", "Down.", { requestId: "req-csrf" }));
    renderWithProviders(<LoginScreen />);
    await fillAndSubmit("staff@kestrel.example", "secret");
    expect(await screen.findByRole("alert")).toHaveTextContent("req-csrf");
    expect(fetchMock).toHaveBeenCalledTimes(1); // no sign-in attempt without a token
  });

  it("ignores an off-site next path", async () => {
    search = new URLSearchParams({ next: "https://evil.example" });
    mockFetch(csrf(), jsonResponse(me));
    renderWithProviders(<LoginScreen />);
    await fillAndSubmit("staff@kestrel.example", "secret");
    await waitFor(() => expect(replace).toHaveBeenCalledWith("/"));
  });

  it("starts the demo and opens the demo store's overview", async () => {
    const fetchMock = mockFetch(csrf(), jsonResponse(me));
    const user = userEvent.setup();
    renderWithProviders(<LoginScreen />);

    await user.click(await screen.findByRole("button", { name: "Explore the demo" }));

    await waitFor(() => expect(replace).toHaveBeenCalledWith("/s/store-1/overview"));
    expectSignInRequest(fetchMock, "/api/v1/auth/demo");
  });

  it("explains an unavailable demo inside the demo card", async () => {
    mockFetch(csrf(), errorResponse(404, "DEMO_UNAVAILABLE", "The demo is not available right now."));
    const user = userEvent.setup();
    renderWithProviders(<LoginScreen />);
    await user.click(await screen.findByRole("button", { name: "Explore the demo" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "The demo is temporarily unavailable. Try again in a few minutes.",
    );
  });

  it("shows the session-expired notice", async () => {
    search = new URLSearchParams({ reason: "expired" });
    mockFetch();
    renderWithProviders(<LoginScreen />);
    expect(
      await screen.findByText("Your session expired. Sign in again to continue. Unsaved changes were not kept."),
    ).toBeInTheDocument();
  });

  it("skips the form when an existing session answers /auth/me", async () => {
    document.cookie = "ro_csrf=t; path=/";
    search = new URLSearchParams({ next: "/s/store-1/overview" });
    mockFetch(jsonResponse(me));
    renderWithProviders(<LoginScreen />);

    await waitFor(() => expect(replace).toHaveBeenCalledWith("/s/store-1/overview"));
    expect(screen.queryByLabelText("Email")).not.toBeInTheDocument();
  });

  it("shows the form when the session probe answers 401, without the expiry redirect", async () => {
    document.cookie = "ro_csrf=stale; path=/";
    const fetchMock = mockFetch(errorResponse(401, "SESSION_EXPIRED", "Your session has expired."));
    const { onSessionExpired } = renderWithProviders(<LoginScreen />);

    expect(await screen.findByLabelText("Email")).toBeInTheDocument();
    expect(fetchMock.mock.calls[0][0]).toBe("/api/v1/auth/me");
    expect(onSessionExpired).not.toHaveBeenCalled();
    expect(replace).not.toHaveBeenCalled();
  });
});
