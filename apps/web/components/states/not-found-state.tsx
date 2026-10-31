import { SearchX } from "lucide-react";
import Link from "next/link";

import { Button } from "@/components/ui/button";

type Entity = "exception" | "order" | "product" | "import" | "conversation";

type NotFoundStateProps =
  | { entity: Entity; backHref: string; backLabel: string }
  | { entity: "store"; backHref?: string; backLabel?: string };

/**
 * Record or store not found (SCREEN_SPECIFICATIONS §0.2, C-37). The copy never reveals whether
 * the record exists in another tenant, mirroring the API's 404-not-403 rule.
 */
export function NotFoundState(props: NotFoundStateProps) {
  const isStore = props.entity === "store";

  return (
    <div role="status" className="mx-auto flex max-w-md flex-col items-center gap-3 py-16 text-center">
      <span className="flex size-10 items-center justify-center rounded-full bg-muted text-muted-foreground">
        <SearchX aria-hidden className="size-6" />
      </span>
      <h1 tabIndex={-1} className="text-title outline-none">
        {isStore
          ? "This store doesn't exist or you don't have access to it."
          : `This ${props.entity} doesn't exist or belongs to another store.`}
      </h1>
      <Button asChild variant="secondary">
        <Link href={props.backHref ?? "/"}>{props.backLabel ?? "Go to my stores"}</Link>
      </Button>
    </div>
  );
}
