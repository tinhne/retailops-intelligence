import type { Metadata } from "next";
import { Suspense } from "react";

import { PositionsScreen } from "@/features/inventory/positions-screen";

export const metadata: Metadata = { title: "Inventory" };

export default function InventoryPage() {
  return (
    <Suspense>
      <PositionsScreen />
    </Suspense>
  );
}
