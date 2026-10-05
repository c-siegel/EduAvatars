import { fileURLToPath, URL } from "node:url";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  optimizeDeps: {
    // talkinghead.mjs läd Lipsync-Sprachmodule per eigenem dynamischem import() nach,
    // das kann Vites Dep-Optimizer nicht mitverfolgen (Datei fehlt dann im .vite/deps-Cache).
    // Wir setzen ohnehin lipsyncModules: [] in TalkingHeadAvatar.tsx, dies ist nur Absicherung.
    exclude: ["@met4citizen/talkinghead"],
  },
  server: {
    proxy: {
      // The backend serves every route under /api/v1 itself (see backend/app/core/urls.py), so
      // requests are forwarded unchanged — same as the Caddy reverse proxy in production.
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});
