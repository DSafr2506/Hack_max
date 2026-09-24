import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// В разработке API проксируется на локальный бэкенд; в Docker их связывает Caddy.
const backend = "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: { "/api": backend, "/go": backend, "/health": backend },
  },
});
