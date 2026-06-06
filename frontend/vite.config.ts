import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Proxy API calls to the FastAPI backend during dev. Pin to 127.0.0.1 (not "localhost")
// so Node doesn't resolve to IPv6 (::1) while the backend listens on IPv4 — that mismatch
// resets long requests ("Failed to fetch"). Generous timeouts: optimize edits take ~30s+.
const API = process.env.VITE_API_BASE || "http://127.0.0.1:8000";
const opt = { target: API, changeOrigin: true, timeout: 600000, proxyTimeout: 600000 };

export default defineConfig({
  plugins: [react()],
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
});
