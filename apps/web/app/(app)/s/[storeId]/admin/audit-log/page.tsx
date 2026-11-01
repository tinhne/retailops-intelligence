import type { Metadata } from "next";
import { Suspense } from "react";

import { AuditLogScreen } from "@/features/admin/audit-log-screen";

export const metadata: Metadata = { title: "Audit log" };

export default function AuditLogPage() {
  return (
    <Suspense>
      <AuditLogScreen />
    </Suspense>
  );
}
