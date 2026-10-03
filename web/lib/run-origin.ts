import type { Run } from "./api";

export function runOriginLabel(origin: Run["origin"]): string {
  return {
    mcp: "MCP 탐색",
    web: "웹 실행",
    api: "API 실행",
    python: "Python 실행",
    unknown: "출처 미기록",
  }[origin ?? "unknown"];
}
