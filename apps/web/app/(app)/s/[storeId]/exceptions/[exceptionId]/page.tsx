import type { Metadata } from "next";

import { ExceptionScreen } from "@/features/exceptions/detail/exception-screen";

export const metadata: Metadata = { title: "Exception" };

export default function ExceptionPage() {
  return <ExceptionScreen />;
}
