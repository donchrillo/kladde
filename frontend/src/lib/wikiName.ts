/**
 * Anzeigename des Wikis. Wird beim Bauen aus `VITE_WIKI_NAME` (frontend/.env)
 * gesetzt, damit dieselbe Codebasis unter anderem Namen laufen kann.
 * Dieselbe Vorgabe steht in vite.config.ts für Seitentitel und PWA-Manifest.
 */
export const WIKI_NAME: string = import.meta.env.VITE_WIKI_NAME || "Kladde";
