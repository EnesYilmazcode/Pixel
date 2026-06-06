import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Proxy API calls to the FastAPI backend (Instance A) during dev.
const API = process.env.VITE_API_BASE || "http://localhost:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/predict": API,
      "/edit": API,
      "/agents": API,
    },
  },
});
