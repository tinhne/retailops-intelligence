import type { Metadata } from "next";
import { Suspense } from "react";

import { CopilotScreen } from "@/features/copilot/copilot-screen";

export const metadata: Metadata = { title: "Copilot" };

export default function CopilotPage() {
  return (
    <Suspense>
      <CopilotScreen />
    </Suspense>
  );
}
