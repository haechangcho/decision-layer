// UI text is English in code and translated through lib/i18n.tsx (ADR-031). Fails on Hangul
// outside the catalog, t("…") literals missing from a catalog, and placeholder mismatches.
import { readdirSync, readFileSync } from "node:fs";
import { join, relative } from "node:path";

const root = new URL("..", import.meta.url).pathname;
const catalogFile = join(root, "lib/i18n.tsx");
const hangul = /[가-힣]/;

const files = (dir) => readdirSync(dir, { withFileTypes: true }).flatMap((entry) =>
  entry.isDirectory() ? files(join(dir, entry.name)) : /\.tsx?$/.test(entry.name) ? [join(dir, entry.name)] : []);
const sources = ["app", "components", "features", "lib"].flatMap((dir) => files(join(root, dir))).filter((file) => file !== catalogFile);

const text = readFileSync(catalogFile, "utf8");
const block = text.slice(text.indexOf("const ko: Record<string, string> = {"), text.indexOf("\n};\n\nconst CATALOGS"));
const ko = new Map([...block.matchAll(/^\s+"((?:[^"\\]|\\.)*)":\s*"((?:[^"\\]|\\.)*)",?\s*$/gm)].map((m) => [JSON.parse(`"${m[1]}"`), JSON.parse(`"${m[2]}"`)]));
const fields = (msg) => [...msg.matchAll(/\{(\w+)\}/g)].map((m) => m[1]).sort().join(",");

const problems = [];
for (const file of sources) {
  const lines = readFileSync(file, "utf8").split("\n");
  lines.forEach((line, i) => {
    const at = `${relative(root, file)}:${i + 1}`;
    if (hangul.test(line)) problems.push(`${at}: Hangul in code; add an English msgid and a catalog entry`);
    for (const m of line.matchAll(/\bt\(\s*"((?:[^"\\]|\\.)*)"/g)) {
      const msg = JSON.parse(`"${m[1]}"`);
      if (!ko.has(msg)) problems.push(`${at}: missing ko translation for ${JSON.stringify(msg)}`);
    }
  });
}
for (const [msg, value] of ko) if (fields(msg) !== fields(value)) problems.push(`ko: placeholders differ for ${JSON.stringify(msg)}`);

if (problems.length) {
  console.error(problems.join("\n"));
  process.exit(1);
}
console.log(`i18n: ${sources.length} files, ${ko.size} ko entries OK`);
