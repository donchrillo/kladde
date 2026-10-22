/**
 * Adressierbare Seiten über den URL-Hash.
 *
 * Bewusst ohne Router-Bibliothek: das Wiki kennt genau drei Adressformen, und
 * der Hash braucht keine Server-Konfiguration (jede Adresse liefert dieselbe
 * `index.html`, was hinter Caddy und im Service-Worker der PWA das Leben
 * einfach hält).
 *
 *   #/                        Startseite (zuletzt geändert)
 *   #/<bereich>               Bereich ohne ausgewählte Seite
 *   #/<bereich>/<slug>        Eine Seite
 *   #/schlagwort/<name>       Seiten zu einem Schlagwort
 *   #/verwaltung              Benutzer und Freigaben (nur Administratoren)
 *   #/konto                   Eigenes Konto (jeder angemeldete Benutzer)
 */

import { useEffect, useState } from "react";

export type Route =
  | { art: "start" }
  | { art: "bereich"; spaceKey: string }
  | { art: "seite"; spaceKey: string; slug: string }
  | { art: "schlagwort"; name: string }
  | { art: "verwaltung" }
  | { art: "konto" };

/** Reserviert, damit kein Bereich versehentlich diesen Schlüssel belegt. */
const SCHLAGWORT = "schlagwort";
const VERWALTUNG = "verwaltung";
const KONTO = "konto";

export function parseHash(hash: string): Route {
  const teile = hash
    .replace(/^#\/?/, "")
    .split("/")
    .filter((t) => t !== "")
    .map(decodeURIComponent);

  if (teile.length === 0) return { art: "start" };
  if (teile[0] === SCHLAGWORT && teile.length >= 2) {
    return { art: "schlagwort", name: teile[1] };
  }
  // Vor dem Bereichs-Zweig: sonst würde "#/verwaltung" als Bereich gelesen.
  if (teile[0] === VERWALTUNG) return { art: "verwaltung" };
  if (teile[0] === KONTO) return { art: "konto" };
  if (teile.length === 1) return { art: "bereich", spaceKey: teile[0] };
  return { art: "seite", spaceKey: teile[0], slug: teile[1] };
}

export function pfadZuSeite(spaceKey: string, slug: string): string {
  return `#/${encodeURIComponent(spaceKey)}/${encodeURIComponent(slug)}`;
}

export function pfadZuBereich(spaceKey: string): string {
  return `#/${encodeURIComponent(spaceKey)}`;
}

export function pfadZuSchlagwort(name: string): string {
  return `#/${SCHLAGWORT}/${encodeURIComponent(name)}`;
}

export function pfadZuVerwaltung(): string {
  return `#/${VERWALTUNG}`;
}

export function pfadZuKonto(): string {
  return `#/${KONTO}`;
}

/**
 * Interner Wiki-Link, wie er im Markdown gespeichert wird.
 *
 * Absolut (`/wiki/...`) statt als Hash, damit das Backend die Verweise mit
 * einem einfachen Muster erkennen kann — siehe backend/src/links.py.
 */
export function markdownLink(spaceKey: string, slug: string): string {
  return `/wiki/${spaceKey}/${slug}`;
}

/** Wandelt einen gespeicherten `/wiki/...`-Link in die Hash-Adresse um. */
export function wikiLinkZuHash(href: string): string | null {
  const treffer = /^\/wiki\/([A-Za-z0-9_-]+)\/([A-Za-z0-9_-]+)$/.exec(href);
  return treffer ? pfadZuSeite(treffer[1], treffer[2]) : null;
}

export function navigiere(pfad: string): void {
  if (window.location.hash !== pfad) window.location.hash = pfad;
}

/** Aktuelle Route; aktualisiert sich bei Vor/Zurück und bei jeder Navigation. */
export function useRoute(): Route {
  const [route, setRoute] = useState<Route>(() => parseHash(window.location.hash));

  useEffect(() => {
    const beiWechsel = () => setRoute(parseHash(window.location.hash));
    window.addEventListener("hashchange", beiWechsel);
    return () => window.removeEventListener("hashchange", beiWechsel);
  }, []);

  return route;
}
