import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import path from "node:path";

// The built app is served by the Python server (homunculus/server.py) from homunculus/static/ui/.
// `npm run dev` serves it with hot reload and forwards the API and run files to the Python server on :8765.
const backend = "http://127.0.0.1:8765";
const BUILD_ID = String(Date.now());

// version.json lets an open app notice a new build and reload itself (src/lib/version.ts)
const versionFile = { name: "homunculus-version", generateBundle(this: any) { this.emitFile({ type: "asset", fileName: "version.json", source: JSON.stringify({ build: BUILD_ID }) }); } };

export default defineConfig({
  base: "/static/ui/",
  define: { __BUILD_ID__: JSON.stringify(BUILD_ID) },
  plugins: [react(), tailwindcss(), versionFile],
  resolve: { alias: { "@": path.resolve(__dirname, "src") } },
  build: {
    outDir: path.resolve(__dirname, "../homunculus/static/ui"),
    emptyOutDir: true,
    chunkSizeWarningLimit: 1500,
    rollupOptions: {
      output: {
        manualChunks: (id) => {
          if (id.includes("node_modules/three") || id.includes("@react-three")) return "three";
          if (id.includes("node_modules")) return "vendor";
        },
      },
    },
  },
  server: {
    port: 5173,
    proxy: { "/api": backend, "/runs": backend, "/static/presets": backend, "/static/vendor": backend },
  },
});
