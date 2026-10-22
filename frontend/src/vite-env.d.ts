/// <reference types="vite/client" />
/// <reference types="vite-plugin-pwa/client" />

interface ImportMetaEnv {
  /** Anzeigename des Wikis, siehe src/lib/wikiName.ts. */
  readonly VITE_WIKI_NAME?: string;
}

/**
 * `tiptap-markdown` hängt seinen Storage zur Laufzeit an den Editor, ergänzt den
 * Storage-Typ von TipTap aber nicht. TipTap hält `Storage` als leeres Interface
 * genau dafür offen — hier wird es zusammengeführt, damit
 * `editor.storage.markdown` überall typsicher ist statt per Cast.
 */
import type { MarkdownStorage } from "tiptap-markdown";

declare module "@tiptap/core" {
  interface Storage {
    markdown: MarkdownStorage;
  }
}
