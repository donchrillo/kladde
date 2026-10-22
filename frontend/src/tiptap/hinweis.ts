/**
 * TipTap-Node „Hinweis" — die farbigen Panels aus der Leseansicht, aber im
 * Editor.
 *
 * Im Markdown ist ein Hinweis ein Zitat mit Marker in der ersten Zeile
 * (`> [!INFO]`). Das ist bewusst so: geht beim Rendern etwas schief, bleibt der
 * Text als Zitat lesbar, statt als Rohtext im Inhalt zu stehen.
 *
 * `tiptap-markdown` wandelt Markdown über markdown-it erst in HTML und lässt
 * die Extensions dieses HTML danach anpassen (`parse.updateDOM`). Deshalb reicht
 * es hier, aus dem erzeugten `<blockquote>` ein `<div data-hinweis>` zu machen —
 * `parseHTML` unten greift es dann auf. Ein eigener markdown-it-Regelsatz wäre
 * deutlich mehr Code für dasselbe Ergebnis.
 */

import { Node, mergeAttributes } from "@tiptap/core";
import type { MarkdownNodeSpec } from "tiptap-markdown";

import { HINWEIS_MARKER, hinweisArt, type HinweisArt } from "../lib/markdown";

declare module "@tiptap/core" {
  interface Commands<ReturnType> {
    hinweis: {
      /** Auswahl in ein Hinweis-Panel der gegebenen Art setzen oder es wieder lösen. */
      hinweisUmschalten: (art: HinweisArt) => ReturnType;
    };
  }
}

export const Hinweis = Node.create({
  name: "hinweis",
  group: "block",
  content: "block+",
  defining: true,

  addAttributes() {
    return {
      art: {
        default: "info" as HinweisArt,
        parseHTML: (element) => hinweisArt(element.getAttribute("data-art") ?? "") ?? "info",
        renderHTML: (attributes) => ({ "data-art": attributes.art as string }),
      },
    };
  },

  parseHTML() {
    return [{ tag: "div[data-hinweis]" }];
  },

  renderHTML({ HTMLAttributes }) {
    return [
      "div",
      mergeAttributes(HTMLAttributes, { "data-hinweis": "", class: "wiki-hinweis" }),
      0,
    ];
  },

  addCommands() {
    return {
      hinweisUmschalten:
        (art) =>
        ({ commands }) =>
          commands.toggleWrap(this.name, { art }),
    };
  },

  addStorage(): { markdown: MarkdownNodeSpec } {
    return {
      markdown: {
        /** Zurück in die `> [!INFO]`-Form. */
        serialize(state, node) {
          const art = (node.attrs.art as HinweisArt) ?? "info";
          state.wrapBlock("> ", null, node, () => {
            state.write(`[!${HINWEIS_MARKER[art] ?? HINWEIS_MARKER.info}]`);
            state.ensureNewLine();
            state.renderContent(node);
          });
        },

        parse: {
          updateDOM(element) {
            element.querySelectorAll("blockquote").forEach((zitat) => {
              const art = markerLoesen(zitat);
              if (art === null) return;

              const panel = zitat.ownerDocument.createElement("div");
              panel.setAttribute("data-hinweis", "");
              panel.setAttribute("data-art", art);
              while (zitat.firstChild !== null) panel.appendChild(zitat.firstChild);
              zitat.replaceWith(panel);
            });
          },
        },
      },
    };
  },
});

/**
 * Prüft, ob das Zitat mit `[!TYP]` beginnt, entfernt den Marker und liefert die
 * Art zurück — sonst `null`, dann bleibt es ein gewöhnliches Zitat.
 *
 * markdown-it fasst `> [!INFO]\n> Text` zu einem Absatz mit weichem Umbruch
 * zusammen; der Marker steht dann am Anfang desselben Textknotens. Steht der
 * Text in einem eigenen Block (Liste, Überschrift), bleibt der Marker als
 * alleiniger Absatz übrig und wird ganz entfernt.
 */
function markerLoesen(zitat: Element): HinweisArt | null {
  const ersterAbsatz = zitat.firstElementChild;
  if (ersterAbsatz === null || ersterAbsatz.tagName !== "P") return null;

  // `instanceof Text` statt `nodeType`: `Node` ist hier TipTaps Node, nicht der DOM-Typ.
  const ersterKnoten = ersterAbsatz.firstChild;
  if (!(ersterKnoten instanceof Text)) return null;

  const treffer = /^\s*\[!([A-Za-zÄÖÜäöü]+)\][^\S\n]*\n?/.exec(ersterKnoten.textContent ?? "");
  if (treffer === null) return null;

  const art = hinweisArt(treffer[1]);
  if (art === null) return null;

  ersterKnoten.textContent = (ersterKnoten.textContent ?? "").slice(treffer[0].length);
  if (ersterAbsatz.textContent === "" && ersterAbsatz.childElementCount === 0) {
    ersterAbsatz.remove();
  }
  return art;
}
