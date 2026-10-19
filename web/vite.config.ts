import { defineConfig } from "vite";
import { fileURLToPath } from "node:url";
const path = (value: string) => fileURLToPath(new URL(value, import.meta.url));
export default defineConfig({
  root: path("./console"),
  base: "/ui/",
  resolve: { alias: {
    "@": path("./"),
    "next/link": path("./console/navigation.tsx"),
    "next/navigation": path("./console/navigation.tsx"),
    "next/dynamic": path("./console/dynamic.tsx"),
  } },
  build: { outDir: path("../src/decision_layer/static"), emptyOutDir: true, rolldownOptions: { onwarn(warning, warn) { if (warning.code !== "MODULE_LEVEL_DIRECTIVE") warn(warning); } } },
});
