/// <reference types="vite/client" />

// Injected by vite.config.ts (define)
declare const __APP_VERSION__: string;
declare const __APP_COMMIT__: string;

interface ImportMetaEnv {
  // Public documentation URL; the footer shows a "coming soon" label while it is unset.
  readonly VITE_DOCS_URL?: string;
}
