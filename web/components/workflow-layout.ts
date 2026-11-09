/** Presentation only: numbering and execution/dependency edges stay caller-owned. */
export function workflowLayout(count: number, width: number) {
  const columns = Math.max(1, Math.min(4, Math.floor((width - 48) / 300)));
  const rows = Math.ceil(count / columns);
  const positions = Array.from({ length: count }, (_, index) => {
    const row = Math.floor(index / columns);
    const offset = index % columns;
    const reverse = row % 2 === 1;
    const column = reverse ? columns - offset - 1 : offset;
    const entry = index > 0 && offset === 0 ? "top" : reverse ? "right" : "left";
    const exit = index + 1 < count && offset === columns - 1 ? "bottom" : reverse ? "left" : "right";
    return { x: 24 + column * 300, y: 24 + row * 208, entry, exit };
  });
  return { columns, rows, positions, height: Math.min(600, Math.max(300, rows * 208 + 16)), readableOverview: width >= 760 && rows <= 3 };
}
