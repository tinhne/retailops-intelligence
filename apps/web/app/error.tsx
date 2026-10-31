"use client";

import { Button } from "@/components/ui/button";

/** Unhandled render error (SCREEN_SPECIFICATIONS §0.2). */
export default function ErrorPage({ error }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <main id="content" className="mx-auto flex min-h-dvh max-w-md flex-col items-center justify-center gap-3 px-4 text-center">
      <h1 className="text-title-lg">Something went wrong displaying this page.</h1>
      {error.digest ? (
        <p className="text-xs text-muted-foreground">
          Error reference <code className="font-mono slashed-zero">{error.digest}</code>
        </p>
      ) : null}
      <Button type="button" variant="secondary" onClick={() => window.location.reload()}>
        Reload page
      </Button>
    </main>
  );
}
