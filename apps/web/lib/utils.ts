import { clsx, type ClassValue } from "clsx";
import { extendTailwindMerge } from "tailwind-merge";

// The design system adds named text sizes (DESIGN_SYSTEM §4.2). Without registering them,
// tailwind-merge reads `text-title-lg` as a text colour and drops it next to `text-foreground`.
const twMerge = extendTailwindMerge({
  extend: {
    classGroups: {
      "font-size": [
        {
          text: [
            "display",
            "title-lg",
            "title",
            "title-sm",
            "body",
            "body-strong",
            "overline",
            "prose",
            "mono",
          ],
        },
      ],
    },
  },
});

export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}
