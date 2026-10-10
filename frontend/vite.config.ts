import { createReadStream, readFileSync, statSync } from "node:fs";
import { execSync } from "node:child_process";
import { fileURLToPath, URL } from "node:url";
import { defineConfig, type Plugin } from "vite";
import react from "@vitejs/plugin-react";
import basicSsl from "@vitejs/plugin-basic-ssl";

// Shown in the footer of the public pages. The commit comes from the APP_COMMIT env variable (the
// Docker build has no .git directory, so frontend.Dockerfile passes it as a build arg) and falls
// back to git for local builds.
const appVersion: string = JSON.parse(readFileSync(new URL("./package.json", import.meta.url), "utf-8")).version;
function gitCommit(): string {
  if (process.env.APP_COMMIT) return process.env.APP_COMMIT.slice(0, 7);
  try {
    return execSync("git rev-parse --short HEAD", { stdio: ["ignore", "pipe", "ignore"] }).toString().trim();
  } catch {
    return "";
  }
}

// Serves the on-device speech recognition model from <repo>/models at /models/ in development —
// Caddy does the same in production (see docker/Caddyfile). The files are hundreds of MB, so they
// live outside public/ (which would copy them into every `npm run build` output). Download them
// with scripts/fetch-stt-model.sh.
function serveSttModels(): Plugin {
  const modelsDir = fileURLToPath(new URL("../models", import.meta.url));
  return {
    name: "serve-stt-models",
    configureServer(server) {
      server.middlewares.use("/models", (req, res, next) => {
        const path = decodeURIComponent((req.url ?? "/").split("?")[0]);
        if (path.includes("..")) return next();
        const file = modelsDir + path;
        try {
          if (!statSync(file).isFile()) return next();
        } catch {
          res.statusCode = 404;
          res.end("Model file not found — run scripts/fetch-stt-model.sh");
          return;
        }
        res.setHeader("Content-Type", file.endsWith(".json") ? "application/json" : "application/octet-stream");
        createReadStream(file).pipe(res);
      });
    },
  };
}

export default defineConfig({
  define: {
    __APP_VERSION__: JSON.stringify(appVersion),
    __APP_COMMIT__: JSON.stringify(gitCommit()),
  },
  // getUserMedia (voice input) and WebGPU (on-device speech recognition, see lib/parakeetStt.ts)
  // are both only available in a "secure context" — HTTPS, or the special-cased "localhost".
  // Testing either from another device over the LAN (e.g. `vite --host`) therefore needs real
  // HTTPS, even in dev — this plugin self-signs a certificate for that, at the cost of a one-time
  // click-through browser warning per device ("connection is not private").
  plugins: [react(), basicSsl(), serveSttModels()],
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  worker: {
    // The speech recognition worker imports onnxruntime-web, which uses dynamic import() — not
    // supported by the default "iife" worker format.
    format: "es",
  },
  optimizeDeps: {
    // talkinghead.mjs loads its lipsync language modules via its own dynamic import(), which
    // Vite's dep optimizer can't follow (the file is then missing from the .vite/deps cache).
    // We set lipsyncModules: [] in TalkingHeadAvatar.tsx anyway, so this is only a safeguard.
    //
    // onnxruntime-web has the same problem: it loads its WASM backend via its own dynamic
    // import()/new URL() at runtime, inside workers/parakeetWorker.ts — invisible to Vite's
    // cold-start dependency scan. Without excluding it, the dev server only discovers that
    // dependency once the worker reaches that code (partway through the model download) and
    // force-reloads the whole page to re-optimize. @soprotts/onnx-web (workers/soproWorker.ts)
    // loads its runtime the same way.
    exclude: ["@met4citizen/talkinghead", "onnxruntime-web", "@soprotts/onnx-web"],
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
