// Firebase App Hosting deployment target for the TanStack Start SSR app.
// Keep vite.config.ts on the Lovable/Cloudflare target used by the editor.
import { defineConfig } from "@lovable.dev/vite-tanstack-config";

export default defineConfig({
  nitro: { preset: "firebase-app-hosting" },
  tanstackStart: {
    server: { entry: "server" },
  },
});
