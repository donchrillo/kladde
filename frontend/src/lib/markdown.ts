/**
 * Markdown → HTML.
 *
 * Der Inhalt stammt aus der eigenen Datenbank, wird aber trotzdem durch
 * DOMPurify geschickt: Seiten sind von jedem im LAN schreibbar, ein
 * eingeschleustes `<script>` träfe sonst alle Leser.
 */

import DOMPurify from "dompurify";
import { Marked, type Tokens } from "marked";

/**
 * Die vier Hinweis-Panels.
 *
 * Geschrieben wird die deutsche Form (`> [!INFO]`); beim Lesen werden auch die
 * englischen GitHub-Marker akzeptiert, damit von dort kopierter Text nicht
 * stumpf als Zitat landet.
 */
export const HINWEIS_ARTEN = ["info", "erfolg", "warnung", "notiz"] as const;
export type HinweisArt = (typeof HINWEIS_ARTEN)[number];

/** Marker im Markdown je Art — die Schreibweise, die wir selbst erzeugen. */
export const HINWEIS_MARKER: Record<HinweisArt, string> = {
  info: "INFO",
  erfolg: "ERFOLG",
  warnung: "WARNUNG",
  notiz: "NOTIZ",
};

const HINWEIS_ALIASE: Record<string, HinweisArt> = {
  info: "info",
  note: "info",
  hinweis: "info",
  erfolg: "erfolg",
  tip: "erfolg",
  success: "erfolg",
  warnung: "warnung",
  warning: "warnung",
  caution: "warnung",
  achtung: "warnung",
  notiz: "notiz",
  important: "notiz",
};

/** Marker-Text (ohne Klammern) auf eine Art abbilden, oder `null`. */
export function hinweisArt(marker: string): HinweisArt | null {
  return HINWEIS_ALIASE[marker.trim().toLowerCase()] ?? null;
}

/**
 * Erkennt den Kopf eines Hinweis-Blocks: `> [!INFO]` in der ersten Zeile,
 * danach beliebig viele weitere Zitatzeilen.
 */
const HINWEIS_REGEX = /^ {0,3}> ?\[!([A-Za-zÄÖÜäöü]+)\][^\n]*(?:\n|$)((?: {0,3}>[^\n]*(?:\n|$))*)/;

/** Anfang eines Hinweis-Blocks für marked's Vorab-Suche. */
const HINWEIS_START = / {0,3}> ?\[!/;

interface HinweisToken extends Tokens.Generic {
  type: "hinweis";
  art: HinweisArt;
  tokens: Tokens.Generic[];
}

/**
 * Anker-Id einer Überschrift.
 *
 * Muss identisch zur Ableitung im Inhaltsverzeichnis sein, sonst zeigen die
 * Sprungmarken ins Leere — deshalb steht sie hier zentral.
 */
export function ueberschriftId(text: string): string {
  return (
    "abschnitt-" +
    text
      .toLowerCase()
      .replace(/[äöüß]/g, (z) => ({ ä: "ae", ö: "oe", ü: "ue", ß: "ss" })[z] ?? z)
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "")
  );
}

/** Nur das Nötigste — DOMPurify räumt danach ohnehin auf. */
function maskiere(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

/**
 * Eine `Marked`-Instanz für das ganze Modul statt `marked.use(...)`: die
 * globale Instanz würde sonst von jedem Import mitkonfiguriert.
 */
const marked = new Marked({ gfm: true, breaks: false }).use({
  extensions: [
    {
      name: "hinweis",
      level: "block",
      start: (src: string) => src.match(HINWEIS_START)?.index,
      tokenizer(src: string) {
        const treffer = HINWEIS_REGEX.exec(src);
        if (treffer === null) return undefined;
        const art = hinweisArt(treffer[1]);
        if (art === null) return undefined;

        // Zitatzeichen abstreifen, der Rest ist wieder normales Markdown.
        const innen = treffer[2].replace(/^ {0,3}> ?/gm, "");
        return {
          type: "hinweis",
          raw: treffer[0],
          art,
          tokens: this.lexer.blockTokens(innen, []),
        } satisfies HinweisToken;
      },
      renderer(token) {
        const { art, tokens } = token as HinweisToken;
        return `<div class="wiki-hinweis" data-art="${art}">${this.parser.parse(tokens)}</div>`;
      },
    },
  ],
  renderer: {
    // Überschriften bekommen eine Id, damit das Inhaltsverzeichnis sie anspringen kann.
    heading({ text, depth, tokens }) {
      const inhalt = this.parser.parseInline(tokens);
      return `<h${depth} id="${ueberschriftId(text)}">${inhalt}</h${depth}>`;
    },

    /**
     * Codeblock mit Zeilennummern, Sprachangabe und Kopier-Knopf.
     *
     * Jede Zeile bekommt ein eigenes `<span>`, damit die Nummern aus einem
     * CSS-Zähler kommen und beim Kopieren nicht im Text landen. Der Knopf trägt
     * kein eigenes JavaScript — den Klick fängt `PageView` ab, alles andere
     * würde DOMPurify entfernen.
     */
    code({ text, lang }) {
      const sprache = (lang ?? "").trim().split(/\s+/)[0];
      const zeilen = text.replace(/\n$/, "").split("\n");
      const inhalt = zeilen
        .map((zeile) => `<span class="wiki-code-zeile">${maskiere(zeile)}</span>`)
        .join("\n");
      const sprachAttribut = sprache === "" ? "" : ` data-sprache="${maskiere(sprache)}"`;
      return (
        `<div class="wiki-code"${sprachAttribut}>` +
        `<button type="button" class="wiki-code-knopf" data-kopieren ` +
        `title="Code kopieren" aria-label="Code kopieren">Kopieren</button>` +
        `<pre><code>${inhalt}</code></pre>` +
        `</div>`
      );
    },
  },
});

export function renderMarkdown(quelle: string): string {
  const roh = marked.parse(quelle, { async: false });
  // `id` steht nicht in DOMPurifys Standardliste, wird für die Sprungmarken aber
  // gebraucht; `target`/`rel` für externe Links.
  return DOMPurify.sanitize(roh, { ADD_ATTR: ["id", "target", "rel"] });
}
