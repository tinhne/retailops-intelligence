import Link from "next/link";

import { Button } from "@/components/ui/button";

export default function NotFound() {
  return (
    <main id="content" className="mx-auto flex min-h-dvh max-w-md flex-col items-center justify-center gap-3 px-4 text-center">
      <h1 className="text-title-lg">Page not found</h1>
      <p className="text-body text-muted-foreground">
        This page doesn&apos;t exist, or the link is out of date.
      </p>
      <Button asChild variant="secondary">
        <Link href="/">Go to my stores</Link>
      </Button>
    </main>
  );
}
