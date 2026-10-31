import { Suspense } from "react";

import { FullPageLoading, StoreShell } from "@/features/session/session-gate";

export default function StoreLayout({ children }: LayoutProps<"/s/[storeId]">) {
  return (
    <Suspense fallback={<FullPageLoading />}>
      <StoreShell>{children}</StoreShell>
    </Suspense>
  );
}
