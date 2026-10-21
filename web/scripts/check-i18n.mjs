// UI messages use English msgids and the shared locale catalog (ADR-031).
import { readdirSync, readFileSync } from "node:fs";
import { join, relative } from "node:path";
import { fileURLToPath } from "node:url";
import ts from "typescript";

const root = fileURLToPath(new URL("..", import.meta.url));
const catalogFile = join(root, "lib/i18n.tsx");
const files = (dir) => readdirSync(dir, { withFileTypes: true }).flatMap((entry) =>
  entry.isDirectory() ? files(join(dir, entry.name)) : /\.tsx?$/.test(entry.name) ? [join(dir, entry.name)] : []);
const sources = ["app", "components", "features", "lib", "console"].flatMap((dir) => files(join(root, dir))).filter((file) => file !== catalogFile);
const parse = (file) => ts.createSourceFile(file, readFileSync(file, "utf8"), ts.ScriptTarget.Latest, true);
const visit = (node, fn) => { fn(node); ts.forEachChild(node, child => visit(child, fn)); };
const catalogSource = parse(catalogFile);
const ko = new Map();
const problems = [];
visit(catalogSource, node => {
  if (!ts.isVariableDeclaration(node) || node.name.getText(catalogSource) !== "ko") return;
  if (!node.initializer || !ts.isObjectLiteralExpression(node.initializer)) throw new Error("ko must be a literal catalog");
  for (const entry of node.initializer.properties) {
    if (!ts.isPropertyAssignment(entry) || !ts.isStringLiteral(entry.name) || !ts.isStringLiteral(entry.initializer)) throw new Error("Catalog entries must be literal messages");
    if (ko.has(entry.name.text)) problems.push(`ko: duplicate msgid ${JSON.stringify(entry.name.text)}`);
    ko.set(entry.name.text, entry.initializer.text);
  }
});
if (!ko.size) throw new Error("No Korean catalog entries found");
const fields = (msg) => [...msg.matchAll(/\{(\w+)\}/g)].map((m) => m[1]).sort().join(",");
const messages = (node) => ts.isStringLiteralLike(node) ? [node]
  : ts.isConditionalExpression(node) ? [...messages(node.whenTrue), ...messages(node.whenFalse)]
    : ts.isParenthesizedExpression(node) ? messages(node.expression) : [];
for (const file of sources) {
  const source = parse(file);
  source.text.split("\n").forEach((line, i) => {
    if (/[가-힣]/.test(line)) problems.push(`${relative(root, file)}:${i + 1}: Hangul in code; add an English msgid and a catalog entry`);
  });
  visit(source, node => {
    if (!ts.isCallExpression(node) || !ts.isIdentifier(node.expression) || node.expression.text !== "t" || !node.arguments[0]) return;
    for (const message of messages(node.arguments[0])) {
      if (!ko.has(message.text)) {
        const line = source.getLineAndCharacterOfPosition(message.getStart(source)).line + 1;
        problems.push(`${relative(root, file)}:${line}: missing ko translation for ${JSON.stringify(message.text)}`);
      }
    }
  });
}
for (const [msg, value] of ko) if (fields(msg) !== fields(value)) problems.push(`ko: placeholders differ for ${JSON.stringify(msg)}`);
if (problems.length) {
  console.error(problems.join("\n"));
  process.exit(1);
}
console.log(`i18n: ${sources.length} files, ${ko.size} ko entries OK`);
