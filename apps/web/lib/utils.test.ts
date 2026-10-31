import { describe, expect, it } from "vitest";

import { zoneGenericName } from "./format/datetime";
import { cn } from "./utils";

describe("cn", () => {
  it("keeps design-system text sizes next to text colours", () => {
    expect(cn("text-title-lg", "text-muted-foreground")).toBe("text-title-lg text-muted-foreground");
    expect(cn("text-body", "text-tone-danger-fg")).toBe("text-body text-tone-danger-fg");
  });

  it("still resolves real conflicts", () => {
    expect(cn("text-body", "text-title")).toBe("text-title");
    expect(cn("px-2", "px-4")).toBe("px-4");
  });
});

describe("zoneGenericName", () => {
  it("returns the generic zone for the store time zone, not the browser's", () => {
    expect(zoneGenericName("America/New_York")).toBe("ET");
  });

  it("falls back to the identifier for an unknown zone", () => {
    expect(zoneGenericName("Not/AZone")).toBe("Not/AZone");
  });
});
