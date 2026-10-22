import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig, loadEnv } from "vite";
import { VitePWA } from "vite-plugin-pwa";

// Ports. Die Belegung ist projektübergreifend vergeben (8401–8407 sind belegt),
// siehe WORKFLOW.md.
const FRONTEND_PORT = 8418;
const BACKEND_PORT = 8408;

export default defineConfig(({ mode }) => {
  // Anzeigename des Wikis aus frontend/.env (VITE_WIKI_NAME), siehe src/lib/wikiName.ts.
  const wikiName = loadEnv(mode, process.cwd()).VITE_WIKI_NAME || "Kladde";

  return {
    plugins: [
      react(),
      tailwindcss(),
      {
        // Setzt den Namen in den <title> von index.html (Platzhalter %WIKI_NAME%).
        name: "wiki-name",
        transformIndexHtml: (html: string) => html.replaceAll("%WIKI_NAME%", wikiName),
      },
      VitePWA({
        registerType: "autoUpdate",
        manifest: {
          name: wikiName,
          short_name: wikiName,
          description: "Internes Wiki: hierarchische Bereiche und Seiten, Markdown-Editor, Versionierung, Volltextsuche.",
          lang: "de",
          theme_color: "#007aff",
          background_color: "#f2f2f7",
          display: "standalone",
          orientation: "portrait",
          start_url: "/",
          icons: [
            { src: "/icon-192.png", sizes: "192x192", type: "image/png" },
            { src: "/icon-512.png", sizes: "512x512", type: "image/png" },
            {
              src: "/icon-maskable-512.png",
              sizes: "512x512",
              type: "image/png",
              purpose: "maskable",
            },
          ],
        },
      }),
    ],
    server: {
      port: FRONTEND_PORT,
      host: true,
      // Zugriff über Caddy/Handy unter dem .lan-Host erlauben.
      allowedHosts: ["pn40.local", "localhost"],
      // API-Aufrufe im Dev an das Backend weiterreichen.
      proxy: {
        "/api": `http://127.0.0.1:${BACKEND_PORT}`,
      },
    },
  };
});
