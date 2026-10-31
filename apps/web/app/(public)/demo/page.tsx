import type { Metadata } from "next";

import { DemoScreen } from "@/features/auth/demo-screen";

export const metadata: Metadata = { title: "Explore the demo" };

export default function DemoPage() {
  return <DemoScreen />;
}
