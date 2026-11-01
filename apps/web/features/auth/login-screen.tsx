"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { CircleAlert, Eye, EyeOff, Info } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState, useSyncExternalStore } from "react";
import { useForm } from "react-hook-form";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { isApiError } from "@/lib/api/errors";
import { useCountdown } from "@/lib/hooks/use-countdown";
import { safeNextPath } from "@/lib/session/navigation";
import { hasSessionHint, useAuthOptions, useDemoLogin, useLogin, useMe } from "@/lib/session/session";

import { AuthLayout } from "./auth-layout";
import { loginSchema, type LoginValues } from "./schema";

const noopSubscribe = () => () => {};

/** False during server rendering and hydration, true afterwards. */
function useHydrated(): boolean {
  return useSyncExternalStore(noopSubscribe, () => true, () => false);
}

function FieldError({ id, message }: { id: string; message?: string }) {
  if (!message) return null;
  return (
    <p id={id} className="flex items-center gap-1 text-xs text-tone-danger-fg">
      <CircleAlert aria-hidden className="size-3.5 shrink-0" />
      {message}
    </p>
  );
}

function signInErrorMessage(error: unknown, secondsLeft: number): string {
  if (!isApiError(error)) return "Sign-in is unavailable right now. Try again in a moment.";
  if (error.status === 401) return "Email or password is incorrect.";
  if (error.status === 429) {
    return secondsLeft > 0
      ? `Too many sign-in attempts. Try again in ${secondsLeft} s.`
      : "You can try signing in again now.";
  }
  if (error.status === 422) return "Check the email address and password, then try again.";
  return "Sign-in is unavailable right now. Try again in a moment.";
}

function demoErrorMessage(error: unknown, secondsLeft: number): string {
  if (isApiError(error) && error.status === 429 && secondsLeft > 0) {
    return `Too many demo sessions were started from your network. Try again in ${secondsLeft} s.`;
  }
  return "The demo is temporarily unavailable. Try again in a few minutes.";
}

/** Sign-in and demo entry (SCREEN_SPECIFICATIONS S-01). */
export function LoginScreen() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const next = safeNextPath(searchParams.get("next"));
  const reason = searchParams.get("reason");

  const hydrated = useHydrated();
  const [probe] = useState(() => typeof document !== "undefined" && hasSessionHint());
  const me = useMe({ probe: true, enabled: probe });

  const login = useLogin();
  const demo = useDemoLogin();
  // No dead control: a customer installation without the demo never shows the demo card.
  const demoAvailable = useAuthOptions().data?.demo_available === true;
  const busy = login.isPending || demo.isPending;
  const [showPassword, setShowPassword] = useState(false);

  const loginRetryAfter = isApiError(login.error) && login.error.status === 429 ? (login.error.retryAfterSeconds ?? 60) : undefined;
  const loginSecondsLeft = useCountdown(loginRetryAfter, login.error);
  const demoRetryAfter = isApiError(demo.error) && demo.error.status === 429 ? (demo.error.retryAfterSeconds ?? 60) : undefined;
  const demoSecondsLeft = useCountdown(demoRetryAfter, demo.error);
  const loginBlocked = loginRetryAfter !== undefined && loginSecondsLeft > 0;

  const form = useForm<LoginValues>({
    resolver: zodResolver(loginSchema),
    mode: "onTouched",
    reValidateMode: "onChange",
    defaultValues: { email: "", password: "" },
  });
  const { errors } = form.formState;

  // An existing session skips the form (S-01 "Initial loading").
  useEffect(() => {
    if (me.isSuccess) router.replace(next);
  }, [me.isSuccess, next, router]);

  const checkingSession = !hydrated || (probe && (me.isPending || me.isSuccess));
  if (checkingSession) return <AuthLayout showForm={false} />;

  const onSubmit = form.handleSubmit((values) => {
    if (loginBlocked) return;
    login.mutate(values, {
      onSuccess: () => router.replace(next),
      onError: () => form.resetField("password"),
    });
  });

  const startDemo = () =>
    demo.mutate(undefined, {
      onSuccess: (result) => {
        const storeId = result.memberships.flatMap((membership) => membership.stores)[0]?.id;
        router.replace(storeId ? `/s/${storeId}/overview` : "/");
      },
    });

  return (
    <AuthLayout>
      {reason === "expired" ? (
        <Alert tone="info">
          <Info aria-hidden />
          <AlertDescription>
            Your session expired. Sign in again to continue. Unsaved changes were not kept.
          </AlertDescription>
        </Alert>
      ) : reason === "signed_out" ? (
        <Alert tone="info">
          <Info aria-hidden />
          <AlertDescription>You&apos;ve signed out.</AlertDescription>
        </Alert>
      ) : null}

      <Card>
        <CardHeader>
          <h1 className="text-title">Sign in</h1>
        </CardHeader>
        <CardContent>
          <form noValidate onSubmit={onSubmit} className="flex flex-col gap-4">
            {login.isError ? (
              <Alert tone="danger" role="alert">
                <CircleAlert aria-hidden />
                <AlertDescription>
                  <p>{signInErrorMessage(login.error, loginSecondsLeft)}</p>
                  {isApiError(login.error) && login.error.status >= 500 && login.error.requestId ? (
                    <p className="text-xs">
                      Request ID <code className="font-mono slashed-zero">{login.error.requestId}</code>
                    </p>
                  ) : null}
                </AlertDescription>
              </Alert>
            ) : null}

            <div className="flex flex-col gap-1.5">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                autoComplete="username"
                aria-invalid={errors.email ? true : undefined}
                aria-describedby={errors.email ? "email-error" : undefined}
                {...form.register("email")}
              />
              <FieldError id="email-error" message={errors.email?.message} />
            </div>

            <div className="flex flex-col gap-1.5">
              <Label htmlFor="password">Password</Label>
              <div className="relative">
                <Input
                  id="password"
                  type={showPassword ? "text" : "password"}
                  autoComplete="current-password"
                  className="pr-10"
                  aria-invalid={errors.password ? true : undefined}
                  aria-describedby={errors.password ? "password-error" : undefined}
                  {...form.register("password")}
                />
                <Button
                  type="button"
                  variant="ghost"
                  size="icon-sm"
                  className="absolute top-1/2 right-1 -translate-y-1/2"
                  aria-label="Show password"
                  aria-pressed={showPassword}
                  onClick={() => setShowPassword((value) => !value)}
                >
                  {showPassword ? <EyeOff aria-hidden /> : <Eye aria-hidden />}
                </Button>
              </div>
              <FieldError id="password-error" message={errors.password?.message} />
            </div>

            <Button
              type="submit"
              size="lg"
              className="w-full sm:h-8"
              disabled={busy}
              pending={login.isPending}
              pendingLabel="Signing in…"
              aria-disabled={loginBlocked || undefined}
            >
              Sign in
            </Button>
          </form>
        </CardContent>
      </Card>

      {demoAvailable ? (
        <>
          <div className="flex items-center gap-3 text-xs text-muted-foreground" aria-hidden>
            <span className="h-px flex-1 bg-border" />
            or
            <span className="h-px flex-1 bg-border" />
          </div>

          <Card>
            <CardHeader>
              <h2 className="text-title-sm">Explore the demo</h2>
              <CardDescription>See a fictional store with generated data. Read-only, no sign-up.</CardDescription>
            </CardHeader>
            <CardContent className="flex flex-col gap-3">
              {demo.isError ? (
                <Alert tone="danger" role="alert">
                  <CircleAlert aria-hidden />
                  <AlertDescription>{demoErrorMessage(demo.error, demoSecondsLeft)}</AlertDescription>
                </Alert>
              ) : null}
              <Button
                type="button"
                variant="secondary"
                size="lg"
                className="w-full sm:h-8"
                disabled={busy}
                pending={demo.isPending}
                pendingLabel="Starting demo…"
                onClick={startDemo}
              >
                Explore the demo
              </Button>
            </CardContent>
          </Card>
        </>
      ) : null}
    </AuthLayout>
  );
}
