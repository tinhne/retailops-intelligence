import type { Metadata } from "next";
import { Suspense } from "react";

import { OrdersScreen } from "@/features/orders/orders-screen";

export const metadata: Metadata = { title: "Orders" };

export default function OrdersPage() {
  return (
    <Suspense>
      <OrdersScreen />
    </Suspense>
  );
}
