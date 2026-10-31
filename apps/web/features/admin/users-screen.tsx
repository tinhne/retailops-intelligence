"use client";

import { useQuery } from "@tanstack/react-query";
import { MoreHorizontal, SearchX, UserPlus, Users } from "lucide-react";
import { useState } from "react";

import { ActionButton } from "@/components/actions/action-button";
import { DataTable, type Column } from "@/components/data/data-table";
import { FilterChips, SearchInput, SelectField, type Chip } from "@/components/data/list-controls";
import { PageHeader } from "@/components/shell/page-header";
import { EmptyState } from "@/components/states/empty-state";
import { ErrorState } from "@/components/states/error-state";
import { PermissionDenied } from "@/components/states/permission-denied";
import { StatusPill } from "@/components/status/status-pill";
import { Button } from "@/components/ui/button";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { adminApi, adminKeys, type MemberCreated, type MemberStatus, type OrganizationMember } from "@/lib/api/admin-api";
import type { Role } from "@/lib/api/auth";
import { formatDateTime } from "@/lib/format/datetime";
import { formatCount } from "@/lib/format/number";
import { useDocumentTitle } from "@/lib/hooks/use-document-title";
import { useListState } from "@/lib/hooks/use-list-state";
import { useNow } from "@/lib/hooks/use-now";
import { defineListParams } from "@/lib/list-params";
import { DEMO_READ_ONLY_REASON, roleLabels, ROLES, type Gate } from "@/lib/permissions";
import { useStore } from "@/lib/store/store-context";

import { AddMemberDialog, ChangeRoleDialog, MemberStatusDialog, TemporaryPasswordDialog } from "./member-dialogs";
import { RoleMatrix } from "./role-matrix";

const STATUSES: MemberStatus[] = ["ACTIVE", "DEACTIVATED"];
const statusLabels: Record<MemberStatus, string> = { ACTIVE: "Active", DEACTIVATED: "Deactivated" };

/** Client-side filters over the member list (organizations are small, S-17), kept in the URL. */
export const membersList = defineListParams(
  {
    q: { kind: "text", max: 100 },
    role: { kind: "one", values: ROLES },
    status: { kind: "one", values: STATUSES },
  },
  { sorts: ["name"], defaultSort: "name", pageSizes: [100], defaultPageSize: 100 },
);

export const ONLY_OWNERS_REASON = "Only owners can add members, change roles or deactivate members.";
const ALLOWED: Gate = { allowed: true };

type MemberGates = { role: Gate; status: Gate };

/**
 * The guards the API enforces (ROLE_AND_PERMISSION_WORKFLOW §8.2), checked here first so the
 * menu explains them: never your own membership, and never the last active owner.
 */
export function memberGates(member: OrganizationMember, context: { manage: Gate; currentUserId: string; activeOwners: number }): MemberGates {
  if (!context.manage.allowed) return { role: context.manage, status: context.manage };
  if (member.user_id === context.currentUserId) {
    return {
      role: { allowed: false, reason: "You can't change your own role." },
      status: { allowed: false, reason: "You can't deactivate your own account." },
    };
  }
  const lastOwner = member.role === "OWNER" && member.status === "ACTIVE" && context.activeOwners <= 1;
  if (lastOwner) {
    const reason = "At least one owner is required.";
    return { role: { allowed: false, reason }, status: { allowed: false, reason } };
  }
  return { role: ALLOWED, status: ALLOWED };
}

function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  const letters = parts.length > 1 ? [parts[0][0], parts[parts.length - 1][0]] : [parts[0]?.[0] ?? "?"];
  return letters.join("").toUpperCase();
}

function MemberName({ member, isYou }: { member: OrganizationMember; isYou: boolean }) {
  return (
    <span className="flex min-w-0 items-center gap-2">
      <span aria-hidden className="flex size-7 shrink-0 items-center justify-center rounded-full bg-muted text-xs text-muted-foreground">
        {initials(member.full_name)}
      </span>
      <span className="min-w-0 font-medium break-words">{member.full_name}</span>
      {isYou ? <StatusPill tone="outline" label="You" /> : null}
    </span>
  );
}

function MemberStatusTag({ status }: { status: MemberStatus }) {
  return <StatusPill tone={status === "ACTIVE" ? "neutral" : "muted"} label={statusLabels[status]} srPrefix="Status:" />;
}

type DialogState = { kind: "role" | "status"; member: OrganizationMember } | null;

/** Users & roles (SCREEN_SPECIFICATIONS S-17): organization members and the role matrix. */
export function UsersScreen() {
  const store = useStore();
  const now = useNow();
  useDocumentTitle("Users & roles");
  const canRead = store.permissions.has("users.read");
  const { params, update, clearAll, isFiltered } = useListState(membersList);
  const [tab, setTab] = useState("members");
  const [adding, setAdding] = useState(false);
  const [created, setCreated] = useState<MemberCreated | null>(null);
  const [dialog, setDialog] = useState<DialogState>(null);

  const members = useQuery({
    queryKey: adminKeys.members(store.organization.id),
    queryFn: ({ signal }) => adminApi.members(store.organization.id, signal),
    enabled: canRead,
  });
  const roles = useQuery({
    queryKey: adminKeys.roles(),
    queryFn: ({ signal }) => adminApi.roles(signal),
    enabled: canRead,
    staleTime: Infinity,
  });

  if (!canRead) return <PermissionDenied pageName="users and roles" permission="users.read" />;

  // Same rule as `gateFor`, with copy that names who can do it: users.manage is OWNER only.
  const manage: Gate = store.permissions.has("users.manage")
    ? ALLOWED
    : { allowed: false, reason: store.organization.isDemo ? DEMO_READ_ONLY_REASON : ONLY_OWNERS_REASON };
  const all = members.data?.items ?? [];
  const activeOwners = all.filter((member) => member.role === "OWNER" && member.status === "ACTIVE").length;
  const gatesOf = (member: OrganizationMember) => memberGates(member, { manage, currentUserId: store.user.id, activeOwners });

  const q = params.q.trim().toLowerCase();
  const visible = members.data
    ? all.filter(
        (member) =>
          (!q || member.full_name.toLowerCase().includes(q) || member.email.toLowerCase().includes(q)) &&
          (!params.role || member.role === params.role) &&
          (!params.status || member.status === params.status),
      )
    : undefined;

  const chips: Chip[] = [
    ...(params.q ? [{ key: "q", label: `Search: ${params.q}`, onRemove: () => update({ q: "" }) }] : []),
    ...(params.role ? [{ key: "role", label: `Role: ${roleLabels[params.role as Role]}`, onRemove: () => update({ role: null }) }] : []),
    ...(params.status ? [{ key: "status", label: `Status: ${statusLabels[params.status as MemberStatus]}`, onRemove: () => update({ status: null }) }] : []),
  ];

  const lastSignIn = (member: OrganizationMember) =>
    member.last_login_at ? (
      <time dateTime={member.last_login_at}>{formatDateTime(member.last_login_at, store.timezone, now)}</time>
    ) : (
      <span className="text-muted-foreground">Never</span>
    );

  const rowMenu = (member: OrganizationMember) => {
    const gates = gatesOf(member);
    const items = [
      { key: "role", label: "Change role…", gate: gates.role, open: () => setDialog({ kind: "role", member }) },
      {
        key: "status",
        label: member.status === "ACTIVE" ? "Deactivate…" : "Reactivate…",
        gate: gates.status,
        open: () => setDialog({ kind: "status", member }),
      },
    ];
    return (
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button type="button" variant="ghost" size="icon-sm" aria-label={`Actions for ${member.full_name}`}>
            <MoreHorizontal aria-hidden />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-64">
          {items.map((item) => (
            <DropdownMenuItem key={item.key} disabled={!item.gate.allowed} onSelect={item.open} className="flex-col items-start gap-0.5">
              <span>{item.label}</span>
              {!item.gate.allowed ? <span className="text-xs font-normal text-muted-foreground">{item.gate.reason}</span> : null}
            </DropdownMenuItem>
          ))}
        </DropdownMenuContent>
      </DropdownMenu>
    );
  };

  // Managers read the list without a row menu (S-17); owners get the menu with explained guards.
  const showMenu = manage.allowed;
  const columns: Column<OrganizationMember>[] = [
    { id: "name", header: "Name", cell: (member) => <MemberName member={member} isYou={member.user_id === store.user.id} /> },
    { id: "email", header: "Email", cell: (member) => <span className="break-all">{member.email}</span> },
    { id: "role", header: "Role", cell: (member) => roleLabels[member.role] },
    { id: "status", header: "Status", cell: (member) => <MemberStatusTag status={member.status} /> },
    { id: "last_login", header: `Last sign-in`, hideBelow: "lg", cell: (member) => <span className="whitespace-nowrap">{lastSignIn(member)}</span> },
    ...(showMenu ? [{ id: "actions", header: "Actions", align: "right" as const, cell: rowMenu }] : []),
  ];

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Users & roles"
        subtitle={`${store.organization.name} · organization-wide`}
        actions={
          <ActionButton gate={manage} onClick={() => setAdding(true)}>
            <UserPlus aria-hidden />
            Add member
          </ActionButton>
        }
      />
      <Tabs value={tab} onValueChange={setTab}>
        <TabsList aria-label="Users and roles">
          <TabsTrigger value="members">Members</TabsTrigger>
          <TabsTrigger value="roles">Roles and permissions</TabsTrigger>
        </TabsList>
        <TabsContent value="members">
          <section aria-label="Members" className="rounded-lg border bg-card">
            <div className="flex flex-col gap-3 border-b p-4">
              <div className="flex flex-wrap items-center gap-3">
                <SearchInput label="Search members" placeholder="Name or email" value={params.q} onChange={(value) => update({ q: value })} />
                <SelectField
                  label="Role"
                  value={params.role ?? ""}
                  options={[{ value: "", label: "Any" }, ...ROLES.map((role) => ({ value: role, label: roleLabels[role] }))]}
                  onChange={(value) => update({ role: value || null })}
                />
                <SelectField
                  label="Status"
                  value={params.status ?? ""}
                  options={[{ value: "", label: "Any" }, ...STATUSES.map((status) => ({ value: status, label: statusLabels[status] }))]}
                  onChange={(value) => update({ status: value || null })}
                />
                <p className="ml-auto text-sm text-muted-foreground" aria-live="polite">
                  {visible ? formatCount(visible.length, "member") : null}
                </p>
              </div>
              <FilterChips chips={chips} onClearAll={clearAll} />
            </div>
            <DataTable
              caption="Members of the organization, sorted by name"
              columns={columns}
              rows={visible}
              getRowId={(member) => member.id}
              status={members.isPending ? "loading" : members.isError ? "error" : "success"}
              error={members.error}
              onRetry={() => void members.refetch()}
              errorTitle="Couldn't load members"
              isFiltered={isFiltered}
              renderStackedRow={(member) => (
                <div className="flex items-start justify-between gap-2 p-4">
                  <div className="flex min-w-0 flex-col gap-1">
                    <MemberName member={member} isYou={member.user_id === store.user.id} />
                    <p className="text-sm break-all text-muted-foreground">{member.email}</p>
                    <p className="flex flex-wrap items-center gap-x-1.5 gap-y-1 text-sm text-muted-foreground">
                      <span>{roleLabels[member.role]}</span>·<MemberStatusTag status={member.status} />·<span>Last sign-in {lastSignIn(member)}</span>
                    </p>
                  </div>
                  {showMenu ? rowMenu(member) : null}
                </div>
              )}
              noResults={
                <EmptyState
                  icon={SearchX}
                  title="No members match these filters"
                  action={
                    <Button type="button" variant="secondary" onClick={clearAll}>
                      Clear filters
                    </Button>
                  }
                />
              }
              empty={<EmptyState icon={Users} title="No members yet" description="Members of the organization appear here." />}
            />
          </section>
        </TabsContent>
        <TabsContent value="roles">
          {roles.isPending ? (
            <div aria-busy="true" className="flex flex-col gap-2 rounded-lg border bg-card p-4">
              <span className="sr-only">Loading roles and permissions</span>
              {Array.from({ length: 8 }, (_, index) => (
                <Skeleton key={index} className="h-8 w-full" />
              ))}
            </div>
          ) : roles.isError ? (
            <div className="rounded-lg border bg-card">
              <ErrorState title="Couldn't load roles and permissions" error={roles.error} onRetry={() => void roles.refetch()} />
            </div>
          ) : (
            <RoleMatrix roles={roles.data} />
          )}
        </TabsContent>
      </Tabs>

      <AddMemberDialog
        open={adding}
        onOpenChange={setAdding}
        onCreated={(result) => {
          setAdding(false);
          setCreated(result);
        }}
      />
      <TemporaryPasswordDialog created={created} onClose={() => setCreated(null)} />
      {dialog?.kind === "role" ? (
        <ChangeRoleDialog
          key={`${dialog.member.id}-${dialog.member.role}`}
          member={dialog.member}
          roles={roles.data}
          open
          onOpenChange={(open) => !open && setDialog(null)}
        />
      ) : null}
      {dialog?.kind === "status" ? (
        <MemberStatusDialog key={dialog.member.id} member={dialog.member} open onOpenChange={(open) => !open && setDialog(null)} />
      ) : null}
    </div>
  );
}
