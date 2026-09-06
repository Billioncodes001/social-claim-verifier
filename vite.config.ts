import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { fileURLToPath } from "node:url";

export default defineConfig({
  root: "frontend",
  base: "/",
  plugins: [react(), tailwindcss()],
  build: {
    outDir: "../verifier/static/dist",
    emptyOutDir: true,
    assetsDir: "assets",
    sourcemap: false,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (/node_modules\/(react|react-dom|scheduler)\//.test(id))
            return "react";
          if (
            /node_modules\/(motion|motion-dom|motion-utils|framer-motion)\//.test(
              id,
            )
          )
            return "motion";
        },
      },
    },
  },
  resolve: {
    alias: { "@": fileURLToPath(new URL("./frontend/src", import.meta.url)) },
  },
  server: {
    port: 5173,
    proxy: {
      "/api": "http://127.0.0.1:8791",
      "/healthz": "http://127.0.0.1:8791",
      "/readyz": "http://127.0.0.1:8791",
    },
  },
});
