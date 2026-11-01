"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Info, Minus, Plus } from "lucide-react";
import { useMemo } from "react";
import { Controller, useForm, useWatch } from "react-hook-form";
import { toast } from "sonner";
import { z } from "zod";

import { CopyButton } from "@/components/states/copy-button";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import {
  adminApi,
  adminKeys,
  type MemberCreated,
  type MemberUpdate,
  type OrganizationMember,
  type RolePermissions,
} from "@/lib/api/admin-api";
import type { Permission, Role } from "@/lib/api/auth";
import { isApiError } from "@/lib/api/errors";
import { permissionLabels, roleDescriptions, roleLabels, ROLES } from "@/lib/permissions";
import { useStore } from "@/lib/store/store-context";

import { FieldError, ServerError, validationFieldErrors } from "./form-parts";

const ROLE_VALUES = ROLES as [Role, ...Role[]];
// Mirrors `MemberCreate` in the API (email pattern and length limits).
const EMAIL_PATTERN = /^[^@\s]+@[^@\s]+$/;
const NAME_MAX = 200;
const EMAIL_MAX = 254;

export const addMemberSchema = z.object({
  full_name: z.string().superRefine((value, ctx) => {
    const text = value.trim();
    if (!text) ctx.addIssue({ code: "custom", message: "Enter the member's full name." });
    else if (text.length > NAME_MAX) {
      ctx.addIssue({ code: "custom", message: `Names are at most ${NAME_MAX} characters (currently ${text.length}).` });
    }
  }),
  email: z.string().superRefine((value, ctx) => {
    const text = value.trim();
    if (!text) ctx.addIssue({ code: "custom", message: "Enter an email address." });
    else if (text.length > EMAIL_MAX) {
      ctx.addIssue({ code: "custom", message: `Email addresses are at most ${EMAIL_MAX} characters (currently ${text.length}).` });
    } else if (!EMAIL_PATTERN.test(text)) {
      ctx.addIssue({ code: "custom", message: "Enter an email address such as name@example.com." });
    }
  }),
  role: z.enum(ROLE_VALUES, { message: "Choose a role." }),
});

type AddMemberValues = z.infer<typeof addMemberSchema>;

/** Role choice with the one-line description of each role (S-17). */
function RoleChoice({
  value,
  onChange,
  invalid,
  describedBy,
}: {
  value: Role | undefined;
  onChange: (role: Role) => void;
  invalid: boolean;
  describedBy?: string;
}) {
  return (
    <RadioGroup value={value ?? ""} onValueChange={(next) => onChange(next as Role)} className="gap-2" aria-describedby={describedBy}>
      {ROLES.map((role) => (
        <label key={role} className="flex cursor-pointer items-start gap-2 text-body">
          <RadioGroupItem value={role} className="mt-0.5" aria-invalid={invalid || undefined} />
          <span>
            <span className="font-medium">{roleLabels[role]}</span>
            <span className="text-muted-foreground">: {roleDescriptions[role]}</span>
          </span>
        </label>
      ))}
    </RadioGroup>
  );
}

/** Replaces one member in the cached list with the server's answer, then refreshes the list. */
function useMembersCache() {
  const store = useStore();
  const queryClient = useQueryClient();
  const key = adminKeys.members(store.organization.id);
  return {
    replace: (updated: OrganizationMember) => {
      queryClient.setQueryData<{ items: OrganizationMember[] }>(key, (current) =>
        current ? { items: current.items.map((member) => (member.id === updated.id ? updated : member)) } : current,
      );
      void queryClient.invalidateQueries({ queryKey: key });
    },
    refresh: () => queryClient.invalidateQueries({ queryKey: key }),
  };
}

export function AddMemberDialog({
  open,
  onOpenChange,
  onCreated,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onCreated: (created: MemberCreated) => void;
}) {
  const store = useStore();
  const members = useMembersCache();
  const form = useForm<AddMemberValues>({
    resolver: zodResolver(addMemberSchema),
    mode: "onTouched",
    defaultValues: { full_name: "", email: "" },
  });
  const add = useMutation({
    mutationFn: (values: AddMemberValues) =>
      adminApi.addMember(store.organization.id, { full_name: values.full_name.trim(), email: values.email.trim(), role: values.role }),
    onSuccess: (created) => {
      void members.refresh();
      toast.success(`Member added: ${created.member.full_name}`);
      form.reset();
      onCreated(created);
    },
    onError: (error) => {
      if (isApiError(error) && (error.code === "MEMBER_EXISTS" || error.code === "EMAIL_IN_USE")) {
        form.setError("email", { message: error.message });
        return;
      }
      const fields = validationFieldErrors(error);
      for (const name of ["full_name", "email", "role"] as const) {
        const message = fields.get(name);
        if (message) form.setError(name, { message });
      }
    },
  });
  const { errors } = form.formState;
  const fieldError = isApiError(add.error) && ["MEMBER_EXISTS", "EMAIL_IN_USE"].includes(add.error.code);
  const close = (next: boolean) => {
    if (add.isPending) return;
    if (!next) {
      form.reset();
      add.reset();
    }
    onOpenChange(next);
  };

  return (
    <Dialog open={open} onOpenChange={close}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Add member</DialogTitle>
          <DialogDescription>
            Creates an account in {store.organization.name}. The role applies to every store of the organization.
          </DialogDescription>
        </DialogHeader>
        <form noValidate className="flex flex-col gap-4" onSubmit={form.handleSubmit((values) => add.mutate(values))}>
          <Alert tone="info">
            <Info aria-hidden />
            <AlertDescription>
              RetailOps doesn&apos;t send email. You get a temporary password to hand over yourself, shown only once.
            </AlertDescription>
          </Alert>
          {add.isError && !fieldError && validationFieldErrors(add.error).size === 0 ? <ServerError error={add.error} /> : null}
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="member_full_name">Full name</Label>
            <Input
              id="member_full_name"
              autoComplete="off"
              autoFocus
              maxLength={NAME_MAX + 50}
              aria-invalid={errors.full_name ? true : undefined}
              aria-describedby={errors.full_name ? "member_full_name-error" : undefined}
              {...form.register("full_name")}
            />
            <FieldError id="member_full_name-error" message={errors.full_name?.message} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="member_email">Email</Label>
            <Input
              id="member_email"
              type="email"
              autoComplete="off"
              maxLength={EMAIL_MAX + 50}
              aria-invalid={errors.email ? true : undefined}
              aria-describedby={errors.email ? "member_email-error" : undefined}
              {...form.register("email")}
            />
            <FieldError id="member_email-error" message={errors.email?.message} />
          </div>
          <fieldset className="flex flex-col gap-2">
            <legend className="mb-1 text-body-strong">Role</legend>
            <Controller
              control={form.control}
              name="role"
              render={({ field }) => (
                <RoleChoice
                  value={field.value}
                  onChange={field.onChange}
                  invalid={Boolean(errors.role)}
                  describedBy={errors.role ? "member_role-error" : undefined}
                />
              )}
            />
            <FieldError id="member_role-error" message={errors.role?.message} />
          </fieldset>
          <DialogFooter>
            <Button type="button" variant="secondary" disabled={add.isPending} onClick={() => close(false)}>
              Cancel
            </Button>
            <Button type="submit" pending={add.isPending} pendingLabel="Adding…">
              Add member
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

/** The one-time temporary password after adding a member (ROLE_AND_PERMISSION_WORKFLOW §8.1). */
export function TemporaryPasswordDialog({ created, onClose }: { created: MemberCreated | null; onClose: () => void }) {
  return (
    <Dialog open={created !== null} onOpenChange={(open) => !open && onClose()}>
      <DialogContent onInteractOutside={(event) => event.preventDefault()}>
        <DialogHeader>
          <DialogTitle>Member added</DialogTitle>
          <DialogDescription>
            Give {created?.member.full_name} this temporary password outside RetailOps. It is shown only once and can&apos;t be
            recovered later.
          </DialogDescription>
        </DialogHeader>
        {created ? (
          <dl className="grid grid-cols-1 gap-3 rounded-md border p-3 sm:grid-cols-[max-content_1fr] sm:gap-x-4">
            <dt className="text-sm text-muted-foreground">Sign-in email</dt>
            <dd className="min-w-0 break-all">{created.member.email}</dd>
            <dt className="text-sm text-muted-foreground">Temporary password</dt>
            <dd className="flex min-w-0 items-center gap-1">
              <code className="font-mono text-mono break-all slashed-zero">{created.temporary_password}</code>
              <CopyButton value={created.temporary_password} label="Copy temporary password" />
            </dd>
          </dl>
        ) : null}
        <DialogFooter>
          <Button type="button" onClick={onClose}>
            Done
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

/** Permissions gained and lost when moving from one role to another, in catalogue order. */
export function roleChangeDiff(roles: RolePermissions[], from: Role, to: Role): { gained: Permission[]; lost: Permission[] } {
  const of = (role: Role) => new Set(roles.find((entry) => entry.role === role)?.permissions ?? []);
  const before = of(from);
  const after = of(to);
  const order = Object.keys(permissionLabels) as Permission[];
  return {
    gained: order.filter((permission) => after.has(permission) && !before.has(permission)),
    lost: order.filter((permission) => before.has(permission) && !after.has(permission)),
  };
}

function WhatChanges({ roles, from, to }: { roles: RolePermissions[] | undefined; from: Role; to: Role }) {
  if (from === to) return null;
  if (!roles) return <p className="text-sm text-muted-foreground">Loading what changes…</p>;
  const { gained, lost } = roleChangeDiff(roles, from, to);
  return (
    <section aria-labelledby="what-changes-title" className="flex flex-col gap-2 rounded-md border p-3">
      <h3 id="what-changes-title" className="text-title-sm">
        What changes
      </h3>
      {gained.length === 0 && lost.length === 0 ? (
        <p className="text-sm text-muted-foreground">Both roles have the same permissions.</p>
      ) : (
        <ul className="flex flex-col gap-1 text-sm">
          {gained.map((permission) => (
            <li key={permission} className="flex items-start gap-1.5">
              <Plus aria-hidden className="mt-0.5 size-3.5 shrink-0 text-tone-success-fg" />
              <span>
                <span className="sr-only">Gains: </span>
                {permissionLabels[permission]}
              </span>
            </li>
          ))}
          {lost.map((permission) => (
            <li key={permission} className="flex items-start gap-1.5">
              <Minus aria-hidden className="mt-0.5 size-3.5 shrink-0 text-tone-danger-fg" />
              <span>
                <span className="sr-only">Loses: </span>
                {permissionLabels[permission]}
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function useMemberUpdate(member: OrganizationMember) {
  const store = useStore();
  const members = useMembersCache();
  return useMutation({
    mutationFn: (body: MemberUpdate) => adminApi.updateMember(store.organization.id, member.id, body),
    onSuccess: (updated) => members.replace(updated),
    onError: (error) => {
      // A conflict means the list on screen is out of date (another owner acted).
      if (isApiError(error) && error.status === 409) void members.refresh();
    },
  });
}

/** C-92: owner-only role change with the "What changes" list. */
export function ChangeRoleDialog({
  member,
  roles,
  open,
  onOpenChange,
}: {
  member: OrganizationMember;
  roles: RolePermissions[] | undefined;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const schema = useMemo(
    () =>
      z.object({ role: z.enum(ROLE_VALUES, { message: "Choose a role." }) }).superRefine((values, ctx) => {
        if (values.role === member.role) ctx.addIssue({ code: "custom", path: ["role"], message: "Choose a different role." });
      }),
    [member.role],
  );
  const form = useForm<{ role: Role }>({ resolver: zodResolver(schema), defaultValues: { role: member.role } });
  const role = useWatch({ control: form.control, name: "role" }) ?? member.role;
  const update = useMemberUpdate(member);
  const close = (next: boolean) => {
    if (update.isPending) return;
    if (!next) update.reset();
    onOpenChange(next);
  };
  const { errors } = form.formState;

  return (
    <Dialog open={open} onOpenChange={close}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Change role for {member.full_name}</DialogTitle>
          <DialogDescription>
            Current role: {roleLabels[member.role]}. The new role applies from their next request, in every store of the organization.
          </DialogDescription>
        </DialogHeader>
        <form
          noValidate
          className="flex flex-col gap-4"
          onSubmit={form.handleSubmit((values) =>
            update.mutate(
              { role: values.role },
              {
                onSuccess: (updated) => {
                  toast.success(`Role changed: ${updated.full_name} is now ${roleLabels[updated.role]}.`);
                  onOpenChange(false);
                },
              },
            ),
          )}
        >
          <ServerError error={update.error} />
          <fieldset className="flex flex-col gap-2">
            <legend className="mb-1 text-body-strong">New role</legend>
            <Controller
              control={form.control}
              name="role"
              render={({ field }) => (
                <RoleChoice
                  value={field.value}
                  onChange={field.onChange}
                  invalid={Boolean(errors.role)}
                  describedBy={errors.role ? "change_role-error" : undefined}
                />
              )}
            />
            <FieldError id="change_role-error" message={errors.role?.message} />
          </fieldset>
          <WhatChanges roles={roles} from={member.role} to={role} />
          <DialogFooter>
            <Button type="button" variant="secondary" disabled={update.isPending} onClick={() => close(false)}>
              Cancel
            </Button>
            <Button type="submit" pending={update.isPending} pendingLabel="Changing role…">
              Change role
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

/** Deactivate (sessions end at once) or reactivate a member (ROLE_AND_PERMISSION_WORKFLOW §8.3). */
export function MemberStatusDialog({
  member,
  open,
  onOpenChange,
}: {
  member: OrganizationMember;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const update = useMemberUpdate(member);
  const deactivating = member.status === "ACTIVE";
  const close = (next: boolean) => {
    if (update.isPending) return;
    if (!next) update.reset();
    onOpenChange(next);
  };
  const submit = () =>
    update.mutate(
      { status: deactivating ? "DEACTIVATED" : "ACTIVE" },
      {
        onSuccess: (updated) => {
          toast.success(deactivating ? `${updated.full_name} deactivated. Their sessions were ended.` : `${updated.full_name} reactivated`);
          onOpenChange(false);
        },
      },
    );

  return (
    <Dialog open={open} onOpenChange={close}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{deactivating ? `Deactivate ${member.full_name}?` : `Reactivate ${member.full_name}?`}</DialogTitle>
          <DialogDescription>
            {deactivating
              ? "They are signed out everywhere at once and can't sign in until reactivated. Their notes, history and audit entries keep their name. Exceptions assigned to them stay assigned until a manager reassigns them."
              : "They can sign in again with their existing password, with the role shown here."}
          </DialogDescription>
        </DialogHeader>
        <ServerError error={update.error} />
        <DialogFooter>
          <Button type="button" variant="secondary" disabled={update.isPending} onClick={() => close(false)}>
            Cancel
          </Button>
          <Button
            type="button"
            variant={deactivating ? "destructive" : "primary"}
            pending={update.isPending}
            pendingLabel={deactivating ? "Deactivating…" : "Reactivating…"}
            onClick={submit}
          >
            {deactivating ? "Deactivate member" : "Reactivate member"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
