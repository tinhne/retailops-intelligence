import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { toast } from "sonner";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { OrganizationMember } from "@/lib/api/admin-api";
import type { Permission } from "@/lib/api/auth";
import { memberFixture, methodFetch, ownerMember, rolesFixture, sentBody } from "@/test/admin-fixtures";
import { errorResponse, jsonResponse } from "@/test/fetch";
import { renderInStore, testStore } from "@/test/render";

import { roleChangeDiff } from "./member-dialogs";
import { memberGates, UsersScreen } from "./users-screen";

const replace = vi.fn();
let search = new URLSearchParams();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace, push: vi.fn() }),
  usePathname: () => "/s/f0da0f22-b9e0-4483-b144-e9f0f8703d13/admin/users",
  useSearchParams: () => search,
}));

const OWNER: Permission[] = ["users.read", "users.manage", "settings.read", "audit.read"];
const MANAGER: Permission[] = ["users.read", "settings.read", "settings.manage", "audit.read"];

const deactivated = memberFixture({
  id: "m-analyst",
  user_id: "u-analyst",
  full_name: "Lee Chen",
  email: "analyst@kestrel.example",
  role: "ANALYST",
  status: "DEACTIVATED",
  last_login_at: null,
});

function routes(members: OrganizationMember[] = [ownerMember(), memberFixture(), deactivated], extra: Parameters<typeof methodFetch>[0] = {}) {
  return methodFetch({
    "GET /organizations/org-1/members": () => jsonResponse({ items: members }),
    "GET /roles": () => jsonResponse(rolesFixture()),
    ...extra,
  });
}

const asOwner = () => testStore({ permissions: OWNER, role: "OWNER" });
const membersTable = async () => (await screen.findAllByRole("table"))[0];

beforeEach(() => {
  replace.mockReset();
  search = new URLSearchParams();
});

describe("UsersScreen (S-17)", () => {
  it("lists members with email, role, status and a You tag", async () => {
    routes();
    renderInStore(<UsersScreen />, asOwner());
    expect(screen.getByRole("heading", { level: 1, name: "Users & roles" })).toBeInTheDocument();
    expect(screen.getByText("Kestrel Commerce · organization-wide")).toBeInTheDocument();
    const table = await membersTable();
    expect(await within(table).findByText("staff@kestrel.example")).toBeInTheDocument();
    const own = within(table).getByText("Priya Raman").closest("tr") as HTMLElement;
    expect(within(own).getByText("You")).toBeInTheDocument();
    expect(within(own).getByText("Owner")).toBeInTheDocument();
    const lee = within(table).getByText("Lee Chen").closest("tr") as HTMLElement;
    expect(within(lee).getByText("Deactivated")).toBeInTheDocument();
    expect(within(lee).getByText("Never")).toBeInTheDocument();
    expect(screen.getByText("3 members")).toBeInTheDocument();
  });

  it("explains why the owner's own row can't be changed", async () => {
    routes();
    const user = userEvent.setup();
    renderInStore(<UsersScreen />, asOwner());
    const table = await membersTable();
    await user.click(await within(table).findByRole("button", { name: "Actions for Priya Raman" }));
    expect(await screen.findByRole("menuitem", { name: /Change role/ })).toHaveAttribute("aria-disabled", "true");
    expect(screen.getByText("You can't change your own role.")).toBeInTheDocument();
    expect(screen.getByRole("menuitem", { name: /Deactivate/ })).toHaveAttribute("aria-disabled", "true");
    expect(screen.getByText("You can't deactivate your own account.")).toBeInTheDocument();
  });

  it("changes a role and shows what changes", async () => {
    const success = vi.spyOn(toast, "success");
    const fetchMock = routes(undefined, {
      "PATCH /members/m-staff": () => jsonResponse(memberFixture({ role: "MANAGER" })),
    });
    const user = userEvent.setup();
    renderInStore(<UsersScreen />, asOwner());
    const table = await membersTable();
    await user.click(await within(table).findByRole("button", { name: "Actions for Sam Ortiz" }));
    await user.click(await screen.findByRole("menuitem", { name: /Change role/ }));
    const dialog = await screen.findByRole("dialog", { name: "Change role for Sam Ortiz" });

    await user.click(within(dialog).getByRole("button", { name: "Change role" }));
    expect(await within(dialog).findByText("Choose a different role.")).toBeInTheDocument();

    await user.click(within(dialog).getByRole("radio", { name: /^Manager/ }));
    const changes = within(dialog).getByRole("region", { name: "What changes" });
    expect(within(changes).getByText("Assign exceptions")).toBeInTheDocument();
    expect(within(changes).getByText("View users")).toBeInTheDocument();
    expect(within(changes).queryByText("Manage users")).not.toBeInTheDocument();
    await user.click(within(dialog).getByRole("button", { name: "Change role" }));

    await waitFor(() => expect(success).toHaveBeenCalledWith("Role changed: Sam Ortiz is now Manager."));
    expect(sentBody(fetchMock, "PATCH", "/members/m-staff")).toEqual({ role: "MANAGER" });
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  });

  it("keeps the dialog open with the last-owner message on 409", async () => {
    const second = ownerMember({ id: "m-owner-2", user_id: "u-owner-2", full_name: "Alex Kim", email: "alex@kestrel.example" });
    routes([ownerMember(), second, memberFixture()], {
      "PATCH /members/m-owner-2": () =>
        errorResponse(409, "LAST_OWNER", "At least one owner is required. Make another member an owner first.", { requestId: "req-9" }),
    });
    const user = userEvent.setup();
    renderInStore(<UsersScreen />, asOwner());
    const table = await membersTable();
    await user.click(await within(table).findByRole("button", { name: "Actions for Alex Kim" }));
    await user.click(await screen.findByRole("menuitem", { name: /Change role/ }));
    const dialog = await screen.findByRole("dialog");
    await user.click(within(dialog).getByRole("radio", { name: /^Manager/ }));
    await user.click(within(dialog).getByRole("button", { name: "Change role" }));
    expect(await within(dialog).findByText("At least one owner is required. Make another member an owner first.")).toBeInTheDocument();
    expect(within(dialog).getByText("req-9")).toBeInTheDocument();
  });

  it("deactivates a member after confirmation", async () => {
    const success = vi.spyOn(toast, "success");
    const fetchMock = routes(undefined, {
      "PATCH /members/m-staff": () => jsonResponse(memberFixture({ status: "DEACTIVATED" })),
    });
    const user = userEvent.setup();
    renderInStore(<UsersScreen />, asOwner());
    const table = await membersTable();
    await user.click(await within(table).findByRole("button", { name: "Actions for Sam Ortiz" }));
    await user.click(await screen.findByRole("menuitem", { name: /Deactivate/ }));
    const dialog = await screen.findByRole("dialog", { name: "Deactivate Sam Ortiz?" });
    expect(within(dialog).getByText(/signed out everywhere at once/)).toBeInTheDocument();
    await user.click(within(dialog).getByRole("button", { name: "Deactivate member" }));
    await waitFor(() => expect(success).toHaveBeenCalledWith("Sam Ortiz deactivated. Their sessions were ended."));
    expect(sentBody(fetchMock, "PATCH", "/members/m-staff")).toEqual({ status: "DEACTIVATED" });
  });

  it("offers reactivation for a deactivated member", async () => {
    const fetchMock = routes(undefined, {
      "PATCH /members/m-analyst": () => jsonResponse({ ...deactivated, status: "ACTIVE" }),
    });
    const user = userEvent.setup();
    renderInStore(<UsersScreen />, asOwner());
    const table = await membersTable();
    await user.click(await within(table).findByRole("button", { name: "Actions for Lee Chen" }));
    await user.click(await screen.findByRole("menuitem", { name: /Reactivate/ }));
    const dialog = await screen.findByRole("dialog", { name: "Reactivate Lee Chen?" });
    await user.click(within(dialog).getByRole("button", { name: "Reactivate member" }));
    await waitFor(() => expect(sentBody(fetchMock, "PATCH", "/members/m-analyst")).toEqual({ status: "ACTIVE" }));
  });

  it("adds a member and shows the temporary password once", async () => {
    const fetchMock = routes(undefined, {
      "POST /organizations/org-1/members": () =>
        jsonResponse(
          {
            member: memberFixture({ id: "m-new", user_id: "u-new", full_name: "Jordan Lee", email: "jordan@kestrel.example", role: "ANALYST", last_login_at: null }),
            temporary_password: "q7Lr-2xVb_9KpT4m",
          },
          { status: 201 },
        ),
    });
    const user = userEvent.setup();
    renderInStore(<UsersScreen />, asOwner());
    await membersTable();
    await user.click(screen.getByRole("button", { name: "Add member" }));
    const dialog = await screen.findByRole("dialog", { name: "Add member" });

    await user.click(within(dialog).getByRole("button", { name: "Add member" }));
    expect(await within(dialog).findByText("Enter the member's full name.")).toBeInTheDocument();
    expect(within(dialog).getByText("Enter an email address.")).toBeInTheDocument();
    expect(within(dialog).getByText("Choose a role.")).toBeInTheDocument();

    await user.type(within(dialog).getByLabelText("Full name"), "  Jordan Lee ");
    await user.type(within(dialog).getByLabelText("Email"), "jordan-at-kestrel");
    await user.click(within(dialog).getByRole("radio", { name: /^Analyst/ }));
    await user.click(within(dialog).getByRole("button", { name: "Add member" }));
    expect(await within(dialog).findByText("Enter an email address such as name@example.com.")).toBeInTheDocument();
    await user.clear(within(dialog).getByLabelText("Email"));
    await user.type(within(dialog).getByLabelText("Email"), "jordan@kestrel.example");
    await user.click(within(dialog).getByRole("button", { name: "Add member" }));

    const done = await screen.findByRole("dialog", { name: "Member added" });
    expect(within(done).getByText("q7Lr-2xVb_9KpT4m")).toBeInTheDocument();
    expect(within(done).getByText("jordan@kestrel.example")).toBeInTheDocument();
    expect(within(done).getByRole("button", { name: "Copy temporary password" })).toBeInTheDocument();
    expect(sentBody(fetchMock, "POST", "/organizations/org-1/members")).toEqual({
      full_name: "Jordan Lee",
      email: "jordan@kestrel.example",
      role: "ANALYST",
    });
    await user.click(within(done).getByRole("button", { name: "Done" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  });

  it("shows an email that already has an account on the email field", async () => {
    routes(undefined, {
      "POST /organizations/org-1/members": () =>
        errorResponse(409, "EMAIL_IN_USE", "An account with this email already exists. Adding an existing account to another organization is not supported yet."),
    });
    const user = userEvent.setup();
    renderInStore(<UsersScreen />, asOwner());
    await membersTable();
    await user.click(screen.getByRole("button", { name: "Add member" }));
    const dialog = await screen.findByRole("dialog", { name: "Add member" });
    await user.type(within(dialog).getByLabelText("Full name"), "Sam Again");
    await user.type(within(dialog).getByLabelText("Email"), "staff@other.example");
    await user.click(within(dialog).getByRole("radio", { name: /^Staff/ }));
    await user.click(within(dialog).getByRole("button", { name: "Add member" }));
    expect(await within(dialog).findByText(/An account with this email already exists/)).toBeInTheDocument();
    expect(within(dialog).getByLabelText("Email")).toHaveAttribute("aria-invalid", "true");
  });

  it("lets managers read without managing", async () => {
    routes();
    renderInStore(<UsersScreen />, testStore({ permissions: MANAGER, role: "MANAGER" }));
    const table = await membersTable();
    await within(table).findByText("staff@kestrel.example");
    expect(screen.queryByRole("button", { name: /^Actions for/ })).not.toBeInTheDocument();
    const add = screen.getByRole("button", { name: "Add member" });
    expect(add).toHaveAttribute("aria-disabled", "true");
    expect(add).toHaveAccessibleDescription("Only owners can add members, change roles or deactivate members.");
  });

  it("filters the list from the URL and offers to clear", async () => {
    search = new URLSearchParams("q=nobody&role=OWNER");
    routes();
    const user = userEvent.setup();
    renderInStore(<UsersScreen />, asOwner());
    expect(await screen.findByText("No members match these filters")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Clear filters" }));
    expect(replace).toHaveBeenCalledWith("/s/f0da0f22-b9e0-4483-b144-e9f0f8703d13/admin/users", { scroll: false });
  });

  it("shows an error with retry when members fail to load", async () => {
    routes(undefined, { "GET /organizations/org-1/members": () => errorResponse(500, "INTERNAL_ERROR", "boom", { requestId: "req-5" }) });
    renderInStore(<UsersScreen />, asOwner());
    expect(await screen.findByRole("heading", { name: "Couldn't load members" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
  });

  it("shows permission denied without users.read", () => {
    renderInStore(<UsersScreen />, testStore({ permissions: ["settings.read"], role: "STAFF" }));
    expect(screen.getByRole("heading", { name: "You don't have access to users and roles" })).toBeInTheDocument();
    expect(screen.getByText("This page requires the View users permission. Your role: Staff.")).toBeInTheDocument();
  });

  it("renders the role matrix from the API", async () => {
    routes();
    const user = userEvent.setup();
    renderInStore(<UsersScreen />, asOwner());
    await user.click(screen.getByRole("tab", { name: "Roles and permissions" }));
    const matrix = await screen.findByRole("table");
    expect(within(matrix).getByText("Roles are defined in code (ADR-0007) and can't be edited here.")).toBeInTheDocument();
    const row = within(matrix).getByRole("rowheader", { name: /Manage users/ }).closest("tr") as HTMLElement;
    const cells = within(row).getAllByRole("cell");
    expect(cells.map((cell) => cell.textContent)).toEqual(["Granted", "—Not granted", "—Not granted", "—Not granted", "—Not granted"]);
    expect(within(matrix).getAllByRole("columnheader").map((header) => header.textContent)).toEqual([
      "Permission",
      "Owner",
      "Manager",
      "Staff",
      "Analyst",
      "Viewer",
    ]);
  });
});

describe("member guards", () => {
  const manage = { allowed: true } as const;
  it("protects your own membership and the last active owner", () => {
    expect(memberGates(ownerMember(), { manage, currentUserId: "user-1", activeOwners: 2 }).role).toEqual({
      allowed: false,
      reason: "You can't change your own role.",
    });
    const other = ownerMember({ id: "m2", user_id: "u2" });
    expect(memberGates(other, { manage, currentUserId: "user-1", activeOwners: 1 }).status).toEqual({
      allowed: false,
      reason: "At least one owner is required.",
    });
    expect(memberGates(other, { manage, currentUserId: "user-1", activeOwners: 2 }).role.allowed).toBe(true);
    expect(memberGates(memberFixture(), { manage: { allowed: false, reason: "No" }, currentUserId: "user-1", activeOwners: 1 }).role).toEqual({
      allowed: false,
      reason: "No",
    });
  });

  it("lists permissions gained and lost by a role change", () => {
    const { gained, lost } = roleChangeDiff(rolesFixture(), "MANAGER", "ANALYST");
    expect(gained).toEqual([]);
    expect(lost).toEqual([
      "exceptions.work",
      "exceptions.assign",
      "exceptions.manage",
      "evaluations.run",
      "imports.run",
      "settings.manage",
      "users.read",
    ]);
  });
});
