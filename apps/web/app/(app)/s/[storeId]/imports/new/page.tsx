import type { Metadata } from "next";
import { Suspense } from "react";

import { NewImportScreen } from "@/features/imports/new-import-screen";

export const metadata: Metadata = { title: "New import" };

export default function NewImportPage() {
  return (
    <Suspense>
      <NewImportScreen />
    </Suspense>
  );
}
