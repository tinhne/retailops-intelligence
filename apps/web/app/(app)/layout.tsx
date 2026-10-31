import { SessionGate } from "@/features/session/session-gate";

export default function AuthenticatedLayout({ children }: LayoutProps<"/">) {
  return <SessionGate>{children}</SessionGate>;
}
