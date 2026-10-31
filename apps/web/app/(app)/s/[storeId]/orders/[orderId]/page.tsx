import type { Metadata } from "next";

import { OrderScreen } from "@/features/orders/order-screen";

export const metadata: Metadata = { title: "Order" };

export default function OrderPage() {
  return <OrderScreen />;
}
