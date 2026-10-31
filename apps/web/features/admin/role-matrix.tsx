import { Check } from "lucide-react";

import type { RolePermissions } from "@/lib/api/admin-api";
import type { Permission } from "@/lib/api/auth";
import { permissionDescriptions, permissionLabels, roleLabels, ROLES } from "@/lib/permissions";

/**
 * C-91: the code-defined role → permission matrix from `GET /roles` (ADR-0007). Nothing here is
 * editable, and the grants come from the API, never from a copy in the UI.
 */
export function RoleMatrix({ roles }: { roles: RolePermissions[] }) {
  const columns = [...roles].sort((a, b) => ROLES.indexOf(a.role) - ROLES.indexOf(b.role));
  const granted = new Map(columns.map((entry) => [entry.role, new Set<string>(entry.permissions)]));
  const known = Object.keys(permissionLabels) as Permission[];
  const extra = [...new Set(columns.flatMap((entry) => entry.permissions))].filter((permission) => !known.includes(permission));
  const rows = [...known, ...extra];

  return (
    <div className="relative overflow-x-auto rounded-lg border bg-card">
      <table className="w-full border-collapse text-body">
        <caption className="caption-bottom border-t px-4 py-3 text-left text-sm text-muted-foreground">
          Roles are defined in code (ADR-0007) and can&apos;t be edited here.
        </caption>
        <thead className="bg-surface-subtle">
          <tr>
            <th scope="col" className="sticky left-0 z-[1] h-9 border-b bg-surface-subtle px-4 text-left text-xs font-medium text-muted-foreground">
              Permission
            </th>
            {columns.map((entry) => (
              <th key={entry.role} scope="col" className="h-9 border-b px-3 text-center text-xs font-medium whitespace-nowrap text-muted-foreground">
                {roleLabels[entry.role] ?? entry.role}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((permission) => (
            <tr key={permission} className="border-b last:border-b-0">
              <th scope="row" className="sticky left-0 z-[1] min-w-44 bg-card px-4 py-2 text-left align-top font-normal sm:min-w-64">
                <span className="block text-body-strong">{permissionLabels[permission] ?? permission}</span>
                {permissionDescriptions[permission] ? (
                  <span className="block text-sm text-muted-foreground">{permissionDescriptions[permission]}</span>
                ) : null}
                <code className="font-mono text-xs text-muted-foreground">{permission}</code>
              </th>
              {columns.map((entry) => (
                <td key={entry.role} className="px-3 py-2 text-center align-middle">
                  {granted.get(entry.role)?.has(permission) ? (
                    <>
                      <Check aria-hidden className="mx-auto size-4 text-tone-success-fg" />
                      <span className="sr-only">Granted</span>
                    </>
                  ) : (
                    <>
                      <span aria-hidden className="text-muted-foreground">
                        —
                      </span>
                      <span className="sr-only">Not granted</span>
                    </>
                  )}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
