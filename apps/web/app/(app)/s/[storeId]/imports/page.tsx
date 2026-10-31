import type { Metadata } from "next";
import { Suspense } from "react";

import { ImportsScreen } from "@/features/imports/imports-screen";

export const metadata: Metadata = { title: "Imports" };

export default function ImportsPage() {
  return (
    <Suspense>
      <ImportsScreen />
    </Suspense>
  );
}
