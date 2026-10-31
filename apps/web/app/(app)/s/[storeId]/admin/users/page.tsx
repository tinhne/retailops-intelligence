import type { Metadata } from "next";
import { Suspense } from "react";

import { UsersScreen } from "@/features/admin/users-screen";

export const metadata: Metadata = { title: "Users & roles" };

export default function UsersPage() {
  return (
    <Suspense>
      <UsersScreen />
    </Suspense>
  );
}
