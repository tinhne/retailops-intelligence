"use client";

import { CircleAlert } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { useAuthOptions, useDemoLogin } from "@/lib/session/session";

import { AuthLayout } from "./auth-layout";

// Facts about the generated dataset (apps/api/app/demo): 8 suppliers, about 114 products and
// about 1,540 orders over a 60-day window. "Reset periodically" is added once the reset job exists (T-094).
const FACTS: Array<[string, string]> = [
  ["Store", "Kestrel Home & Kitchen (fictional)"],
  ["Data", "About 120 products, about 1,500 orders over the last 60 days, 8 suppliers, every exception type"],
  ["Access", "Read-only viewer: you can explore everything, but not change data"],
  ["Freshness", "Generated relative to the day the demo was set up"],
];

/**
 * Shareable demo entry (SCREEN_SPECIFICATIONS S-01, `/demo`). A GET never creates a session;
 * only the button posts to `/auth/demo`, which avoids login CSRF (IA §4.2).
 */
export function DemoScreen() {
  const router = useRouter();
  const demo = useDemoLogin();
  const unavailable = useAuthOptions().data?.demo_available === false;

  const start = () =>
    demo.mutate(undefined, {
      onSuccess: (result) => {
        const storeId = result.memberships.flatMap((membership) => membership.stores)[0]?.id;
        router.replace(storeId ? `/s/${storeId}/overview` : "/");
      },
    });

  return (
    <AuthLayout>
      <Card>
        <CardHeader>
          <h1 className="text-title">Explore the RetailOps Intelligence demo</h1>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <dl className="grid grid-cols-1 gap-3 text-body">
            {FACTS.map(([term, description]) => (
              <div key={term} className="flex flex-col gap-0.5">
                <dt className="text-xs text-muted-foreground">{term}</dt>
                <dd>{description}</dd>
              </div>
            ))}
          </dl>
          {unavailable ? (
            <Alert tone="info" role="status">
              <CircleAlert aria-hidden />
              <AlertDescription>This installation does not offer the public demo. Sign in with your workspace account.</AlertDescription>
            </Alert>
          ) : null}
          {demo.isError ? (
            <Alert tone="danger" role="alert">
              <CircleAlert aria-hidden />
              <AlertDescription>The demo is temporarily unavailable. Try again in a few minutes.</AlertDescription>
            </Alert>
          ) : null}
          {unavailable ? null : (
            <Button
              type="button"
              size="lg"
              className="w-full sm:h-8"
              pending={demo.isPending}
              pendingLabel="Starting demo…"
              onClick={start}
            >
              Start the demo
            </Button>
          )}
          <Link href="/login" className="text-center text-body text-link hover:underline">
            Sign in with a workspace account
          </Link>
        </CardContent>
      </Card>
    </AuthLayout>
  );
}
