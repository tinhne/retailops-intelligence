import type { Metadata } from "next";

import { ImportScreen } from "@/features/imports/import-screen";

export const metadata: Metadata = { title: "Import" };

export default function ImportPage() {
  return <ImportScreen />;
}
