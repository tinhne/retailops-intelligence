// Regenerates src/schema.ts from the API's OpenAPI document (ADR-0013).
// Usage: pnpm contracts:generate   (requires uv and the API's Python environment)
import { execFileSync } from "node:child_process";
import { writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import openapiTS, { astToString } from "openapi-typescript";

const here = dirname(fileURLToPath(import.meta.url));
const apiDir = resolve(here, "../../../apps/api");

const json = execFileSync("uv", ["--directory", apiDir, "run", "python", "-m", "app.openapi_export"], {
  encoding: "utf8",
  env: { ...process.env, LOG_LEVEL: "WARNING" },
});
writeFileSync(resolve(here, "../openapi.json"), json);

const ast = await openapiTS(JSON.parse(json));
const header =
  "// AUTO-GENERATED from apps/api OpenAPI schema by packages/contracts/scripts/generate.mjs.\n" +
  "// Do not edit by hand. Run `pnpm contracts:generate` after changing API schemas.\n\n";
writeFileSync(resolve(here, "../src/schema.ts"), header + astToString(ast));
console.log("contracts: wrote openapi.json and src/schema.ts");
