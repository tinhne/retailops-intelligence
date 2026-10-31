import type { Metadata } from "next";
import { Suspense } from "react";

import { AuthLayout } from "@/features/auth/auth-layout";
import { LoginScreen } from "@/features/auth/login-screen";

export const metadata: Metadata = { title: "Sign in" };

export default function LoginPage() {
  return (
    <Suspense fallback={<AuthLayout showForm={false} />}>
      <LoginScreen />
    </Suspense>
  );
}
