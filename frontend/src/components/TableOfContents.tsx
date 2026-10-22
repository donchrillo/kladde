/**
 * Inhaltsverzeichnis aus den Überschriften der Seite.
 *
 * Die Überschriften kommen aus dem Markdown statt aus dem gerenderten DOM: so
 * steht das Verzeichnis sofort beim ersten Malen und muss nicht auf den
 * eingehängten HTML-Baum warten.
 */

import { useEffect, useMemo, useState } from "react";

import { ueberschriftId } from "../lib/markdown";
import { cn } from "../lib/utils";

interface Eintrag {
  stufe: number;
  text: string;
  id: string;
}

/** Überschriften aus dem Markdown lesen — Codeblöcke bleiben außen vor. */
function ueberschriften(markdown: string): Eintrag[] {
  const gefunden: Eintrag[] = [];
  let inCodeblock = false;

  for (const zeile of markdown.split("\n")) {
    if (zeile.trimStart().startsWith("```")) {
      inCodeblock = !inCodeblock;
      continue;
    }
    if (inCodeblock) continue;

    const treffer = /^(#{1,3})\s+(.+?)\s*$/.exec(zeile);
    if (treffer !== null) {
      const text = treffer[2];
      gefunden.push({ stufe: treffer[1].length, text, id: ueberschriftId(text) });
    }
  }
  return gefunden;
}

interface Props {
  markdown: string;
  /**
   * `oben` steht über dem Text (schmale Fenster), `seitlich` in der rechten
   * Spalte und bleibt beim Scrollen stehen.
   */
  variante?: "oben" | "seitlich";
}

export function TableOfContents({ markdown, variante = "oben" }: Props) {
  const eintraege = useMemo(() => ueberschriften(markdown), [markdown]);
  const [aktiv, setAktiv] = useState<string | null>(null);

  /**
   * Welcher Abschnitt gerade gelesen wird: der letzte, dessen Überschrift noch
   * im oberen Bereich des Fensters steht.
   *
   * Bewusst über das Scroll-Ereignis statt über einen `IntersectionObserver`:
   * der meldet sich nur beim Über- und Unterschreiten seiner Schwellen, wodurch
   * die Hervorhebung zwischendrin auf einem alten Stand stehenbleibt. Der
   * Inhalt scrollt in einem eigenen Container, deshalb wird in der
   * Einfangphase am Dokument gelauscht — Scroll-Ereignisse steigen nicht auf.
   */
  useEffect(() => {
    const ziele = eintraege
      .map((eintrag) => document.getElementById(eintrag.id))
      .filter((el): el is HTMLElement => el !== null);
    if (ziele.length === 0) return;

    let angefordert = 0;
    const messen = () => {
      angefordert = 0;
      let aktuell = ziele[0].id;
      for (const ziel of ziele) {
        if (ziel.getBoundingClientRect().top <= 120) aktuell = ziel.id;
      }
      setAktiv(aktuell);
    };
    // Pro Bild höchstens einmal messen, sonst rechnet jedes Scroll-Ereignis mit.
    const anstossen = () => {
      if (angefordert === 0) angefordert = window.requestAnimationFrame(messen);
    };

    messen();
    document.addEventListener("scroll", anstossen, { capture: true, passive: true });
    window.addEventListener("resize", anstossen);
    return () => {
      if (angefordert !== 0) window.cancelAnimationFrame(angefordert);
      document.removeEventListener("scroll", anstossen, { capture: true });
      window.removeEventListener("resize", anstossen);
    };
  }, [eintraege]);

  // Unter drei Überschriften lohnt sich ein Verzeichnis nicht.
  if (eintraege.length < 3) return null;

  const seitlich = variante === "seitlich";

  return (
    <nav
      aria-label="Inhaltsverzeichnis"
      className={cn(
        // Das Kleben übernimmt der umgebende `<aside>` in PageView.
        seitlich
          ? "border-l border-border pl-3"
          : "mb-6 rounded-lg border border-border bg-background px-4 py-3",
      )}
    >
      <p className="mb-1 text-xs font-medium tracking-wide text-text-secondary uppercase">
        Auf dieser Seite
      </p>
      <ul className="flex flex-col gap-0.5 text-sm">
        {eintraege.map((eintrag, i) => (
          <li key={`${eintrag.id}-${i}`}>
            <a
              href={`#${eintrag.id}`}
              onClick={(e) => {
                // Kein echter Sprung: der Hash trägt hier die Route, nicht das Ziel.
                e.preventDefault();
                document
                  .getElementById(eintrag.id)
                  ?.scrollIntoView({ behavior: "smooth", block: "start" });
              }}
              className={cn(
                "block truncate transition hover:text-primary",
                eintrag.id === aktiv ? "font-medium text-primary" : "text-text-secondary",
                eintrag.stufe === 2 && "pl-3",
                eintrag.stufe === 3 && "pl-6",
              )}
            >
              {eintrag.text}
            </a>
          </li>
        ))}
      </ul>
    </nav>
  );
}
