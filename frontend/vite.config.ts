import { fileURLToPath, URL } from "node:url";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import basicSsl from "@vitejs/plugin-basic-ssl";

export default defineConfig({
  // getUserMedia (voice input) and WebGPU (browser-side Whisper, see lib/browserStt.ts) are both
  // only available in a "secure context" — HTTPS, or the special-cased "localhost". Testing
  // either from another device over the LAN (e.g. `vite --host`) therefore needs real HTTPS, even
  // in dev — this plugin self-signs a certificate for that, at the cost of a one-time
  // click-through browser warning per device ("connection is not private").
  plugins: [react(), basicSsl()],
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  optimizeDeps: {
    // talkinghead.mjs läd Lipsync-Sprachmodule per eigenem dynamischem import() nach,
    // das kann Vites Dep-Optimizer nicht mitverfolgen (Datei fehlt dann im .vite/deps-Cache).
    // Wir setzen ohnehin lipsyncModules: [] in TalkingHeadAvatar.tsx, dies ist nur Absicherung.
    //
    // @huggingface/transformers has the identical problem, one layer deeper: onnxruntime-web (its
    // dependency) loads its WASM backend via its own dynamic import()/new URL() at runtime, inside
    // workers/whisperWorker.ts — invisible to Vite's cold-start dependency scan. Without excluding
    // it, the dev server only discovers that dependency once the worker actually reaches that code
    // (partway through the model download), and reacts by re-optimizing and force-reloading the
    // whole page mid-download — which looked like the model load "breaking" at a fixed percentage
    // and the page reloading right after.
    exclude: ["@met4citizen/talkinghead", "@huggingface/transformers"],
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
