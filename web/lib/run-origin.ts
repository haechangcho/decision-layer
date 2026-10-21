import type { Run } from "./api";
import type { Translate } from "./i18n";

export function runOriginLabel(origin: Run["origin"], t: Translate): string {
  return t({
    mcp: "MCP run",
    web: "Web run",
    api: "API run",
    python: "Python run",
    unknown: "Origin not recorded",
  }[origin ?? "unknown"]);
}
