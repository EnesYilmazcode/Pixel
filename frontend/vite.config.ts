import { rmSync } from "node:fs";
import { resolve } from "node:path";
import { defineConfig, type Plugin } from "vite";
import react from "@vitejs/plugin-react";

// Proxy API calls to the FastAPI backend during dev. Pin to 127.0.0.1 (not "localhost")
// so Node doesn't resolve to IPv6 (::1) while the backend listens on IPv4 — that mismatch
// resets long requests ("Failed to fetch"). Generous timeouts: optimize edits take ~30s+.
const API = process.env.VITE_API_BASE || "http://127.0.0.1:8000";
const opt = { target: API, changeOrigin: true, timeout: 600000, proxyTimeout: 600000 };

// `vite build --mode demo` builds the static replay demo served at pixel-gaze.web.app.
const DEMO_OUT = resolve(__dirname, "../web-dist");

// public/ also holds files the demo never loads: the 9 MB June Nike run, and the full-size
// samples (the demo shows the lighter copies in replay/).
function dropUnusedPublicFiles(): Plugin {
  return {
    name: "drop-unused-public-files",
    apply: "build",
    closeBundle() {
      for (const p of ["precomputed", "README.md", "samples"]) {
        rmSync(resolve(DEMO_OUT, p), { recursive: true, force: true });
      }
    },
  };
}

export default defineConfig(({ mode }) => {
  const demo = mode === "demo";
  return {
    plugins: [react(), demo && dropUnusedPublicFiles()],
    build: demo ? { outDir: DEMO_OUT, emptyOutDir: true } : {},
    server: {
      proxy: {
        "/predict": opt,
        "/edit": opt,
        "/agents": opt,
        "/optimize": opt,
        "/campaigns": opt,
        "/health": opt,
      },
    },
  };
});
