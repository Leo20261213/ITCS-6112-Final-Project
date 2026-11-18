import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Proxy /api to FastAPI so the browser talks to one origin in development.
// Set API_URL to point at a backend on another address (default http://127.0.0.1:8000).
export default defineConfig({
  plugins: [react()],
  server: {
    port: Number(process.env.PORT) || 5173,
    proxy: { "/api": process.env.API_URL || "http://127.0.0.1:8000" },
  },
});
