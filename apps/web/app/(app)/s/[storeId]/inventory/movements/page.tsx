import type { Metadata } from "next";
import { Suspense } from "react";

import { MovementsScreen } from "@/features/inventory/movements-screen";

export const metadata: Metadata = { title: "Movements" };

export default function MovementsPage() {
  return (
    <Suspense>
      <MovementsScreen />
    </Suspense>
  );
}
