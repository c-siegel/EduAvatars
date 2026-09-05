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
      // Backend-Routen liegen ohne /api-Präfix (z.B. /auth/login, nicht /api/auth/login) —
      // ohne dieses rewrite würde Vite /api/auth/login unverändert weiterleiten und jede
      // echte Frontend-Anfrage liefe ins Leere (404). Dieselbe Umschreibung braucht der
      // Reverse-Proxy im institutionellen Hosting später ebenfalls.
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
});
