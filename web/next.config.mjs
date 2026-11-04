// The browser talks to /api/*; Next proxies it to the Decision Layer API (no CORS, one origin).
import { fileURLToPath } from "node:url";
const api = process.env.DL_API_URL || "http://127.0.0.1:5200";

/** @type {import('next').NextConfig} */
export default {
  // Runtime translations share the Python catalog outside web/.
  turbopack: { root: fileURLToPath(new URL("..", import.meta.url)) },
  allowedDevOrigins: ["127.0.0.1"],
  distDir: process.env.NEXT_DIST_DIR || ".next",
  agentRules: false,
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${api}/:path*` }];
  },
};
