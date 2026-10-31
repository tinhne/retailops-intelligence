"use client";

import { useId } from "react";

import { Button, type ButtonProps } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import type { Gate } from "@/lib/permissions";

type ActionButtonProps = ButtonProps & { gate: Gate };

/**
 * A button with permission and state gating (COMPONENT_INVENTORY C-27/C-28). When not allowed it
 * stays focusable with `aria-disabled`, ignores clicks, and exposes the reason both as a tooltip
 * and through `aria-describedby`, so keyboard and screen-reader users get it too.
 */
export function ActionButton({ gate, ...props }: ActionButtonProps) {
  const reasonId = useId();
  if (gate.allowed) return <Button {...props} />;

  return (
    <>
      <Tooltip>
        <TooltipTrigger asChild>
          <Button {...props} aria-disabled="true" aria-describedby={reasonId} />
        </TooltipTrigger>
        <TooltipContent>{gate.reason}</TooltipContent>
      </Tooltip>
      <span id={reasonId} className="sr-only">
        {gate.reason}
      </span>
    </>
  );
}
