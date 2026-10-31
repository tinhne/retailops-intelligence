"use client";

import { Check, Copy } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";

/** Copies a machine identifier such as a `request_id` (COMPONENT_INVENTORY C-07). */
export function CopyButton({ value, label }: { value: string; label: string }) {
  const [copied, setCopied] = useState(false);

  async function copy() {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      // Clipboard access can be refused; the value stays visible and selectable.
    }
  }

  return (
    <Button type="button" variant="ghost" size="icon-sm" aria-label={copied ? "Copied" : label} onClick={copy}>
      {copied ? <Check aria-hidden /> : <Copy aria-hidden />}
    </Button>
  );
}
