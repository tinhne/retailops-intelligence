export type { components, operations, paths } from "./schema";
import type { components } from "./schema";

/** Shorthand for a named API schema, e.g. `Schema<"MeResponse">`. */
export type Schema<Name extends keyof components["schemas"]> = components["schemas"][Name];
