import type { Metadata } from "next";

import { ProductScreen } from "@/features/inventory/product-screen";

export const metadata: Metadata = { title: "Product" };

export default function ProductPage() {
  return <ProductScreen />;
}
