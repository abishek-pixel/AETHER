// Vercel-targeted build configuration for TanStack Start v1.168
// Uses the official nitro/vite plugin so Vercel auto-detects the framework
// and deploys the server as Vercel Functions (Fluid compute).
//
// NOTE: @lovable.dev/vite-tanstack-config is NOT used here because it
// hardcodes @cloudflare/vite-plugin at build time, which produces a
// Cloudflare Workers output (dist/client + dist/server with no index.html)
// that Vercel cannot serve — causing the 404: NOT_FOUND error.

import { defineConfig, loadEnv } from "vite";
import { tanstackStart } from "@tanstack/react-start/plugin/vite";
import viteReact from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import tsConfigPaths from "vite-tsconfig-paths";
import { nitro } from "nitro/vite";

export default defineConfig(({ mode }) => {
  // Load VITE_* env vars so they are available as import.meta.env.*
  const env = loadEnv(mode, process.cwd(), "VITE_");

  return {
    define: Object.fromEntries(
      Object.entries(env).map(([key, value]) => [
        `import.meta.env.${key}`,
        JSON.stringify(value),
      ])
    ),

    resolve: {
      alias: {
        "@": `${process.cwd()}/src`,
      },
      dedupe: [
        "react",
        "react-dom",
        "react/jsx-runtime",
        "react/jsx-dev-runtime",
        "@tanstack/react-query",
        "@tanstack/query-core",
      ],
    },

    plugins: [
      tailwindcss(),
      tsConfigPaths({ projects: ["./tsconfig.json"] }),
      tanstackStart({
        server: { entry: "server" },
        importProtection: {
          behavior: "error",
          client: {
            files: ["**/server/**"],
            specifiers: ["server-only"],
          },
        },
      }),
      // nitro/vite is the official Vercel-compatible server plugin.
      // Vercel auto-detects it and deploys the output as Vercel Functions.
      nitro(),
      viteReact(),
    ],
  };
});
