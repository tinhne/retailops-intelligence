import type { Metadata } from "next";
import { Suspense } from "react";

import { InboxScreen } from "@/features/exceptions/inbox-screen";

export const metadata: Metadata = { title: "Exceptions" };

export default function ExceptionsPage() {
  return (
    <Suspense>
      <InboxScreen />
    </Suspense>
  );
}
