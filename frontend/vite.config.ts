import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The backend runs on :8000; /api is proxied so the browser never needs CORS or the API key.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { "/api": { target: "http://127.0.0.1:8000", changeOrigin: true } },
  },
});
