import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// В dev-режиме запросы /v1/* проксируются на бэкенд (BACKEND_URL).
// Это исключает CORS-проблемы при локальной разработке.
// По умолчанию бэкенд доступен на http://localhost (Nginx → Docker).
const BACKEND = process.env.BACKEND_URL ?? "http://localhost";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/v1": {
        target: BACKEND,
        changeOrigin: true,
      },
    },
  },
});
