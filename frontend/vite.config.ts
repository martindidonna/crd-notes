import { svelte } from "@sveltejs/vite-plugin-svelte";
import { resolve } from "node:path";
import { defineConfig } from "vite";

export default defineConfig({
  root: "frontend",
  plugins: [svelte()],
  resolve: {
    alias: {
      $lib: resolve("frontend/src/lib")
    }
  },
  build: {
    outDir: "../crd_notes/web",
    assetsDir: "static",
    emptyOutDir: true,
    sourcemap: false
  },
  server: {
    port: 5173,
    proxy: {
      "/api": "http://127.0.0.1:8184"
    }
  }
});
