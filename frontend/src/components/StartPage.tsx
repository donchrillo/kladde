/**
 * Startseite: zuletzt geänderte Seiten und die Schlagwortwolke.
 *
 * Der übliche Einstieg in ein Wiki — man will sehen, was sich getan hat, und
 * über Themen einsteigen, nicht über die Baumstruktur.
 */

import { Clock, Tag } from "lucide-react";
import { useEffect, useState } from "react";

import {
  listLabels,
  pagesByLabel,
  recentPages,
  type LabelCount,
  type PageSummary,
} from "../lib/api-client";
import { navigiere, pfadZuSchlagwort, pfadZuSeite } from "../lib/route";

function relativ(iso: string): string {
  const minuten = Math.round((Date.now() - new Date(iso).getTime()) / 60000);
  if (minuten < 1) return "gerade eben";
  if (minuten < 60) return `vor ${minuten} Min`;
  const stunden = Math.round(minuten / 60);
  if (stunden < 24) return `vor ${stunden} Std`;
  const tage = Math.round(stunden / 24);
  return tage === 1 ? "gestern" : `vor ${tage} Tagen`;
}

export function StartPage() {
  const [seiten, setSeiten] = useState<PageSummary[]>([]);
  const [schlagwoerter, setSchlagwoerter] = useState<LabelCount[]>([]);

  useEffect(() => {
    void recentPages(10).then(setSeiten).catch(() => setSeiten([]));
    void listLabels().then(setSchlagwoerter).catch(() => setSchlagwoerter([]));
  }, []);

  return (
    <div className="flex flex-col gap-6">
      <section className="rounded-lg border border-border bg-card p-5 shadow-card">
        <h2 className="flex items-center gap-2 text-lg font-semibold">
          <Clock className="h-5 w-5 text-text-secondary" />
          Zuletzt geändert
        </h2>
        {seiten.length === 0 ? (
          <p className="mt-3 text-sm text-text-secondary">
            Noch keine Seiten. Links über das Plus eine anlegen.
          </p>
        ) : (
          <ul className="mt-3 flex flex-col">
            {seiten.map((seite) => (
              <li key={seite.id} className="border-b border-border last:border-b-0">
                <button
                  type="button"
                  onClick={() => navigiere(pfadZuSeite(seite.space_key, seite.slug))}
                  className="flex w-full items-baseline gap-3 py-2 text-left hover:bg-background"
                >
                  <span className="min-w-0 flex-1 truncate text-sm font-medium">
                    {seite.title}
                  </span>
                  <span className="shrink-0 text-xs text-text-secondary">{seite.space_name}</span>
                  <span className="shrink-0 text-xs text-text-secondary">
                    {relativ(seite.updated_at)}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>

      {schlagwoerter.length > 0 && (
        <section className="rounded-lg border border-border bg-card p-5 shadow-card">
          <h2 className="flex items-center gap-2 text-lg font-semibold">
            <Tag className="h-5 w-5 text-text-secondary" />
            Schlagwörter
          </h2>
          <div className="mt-3 flex flex-wrap gap-2">
            {schlagwoerter.map((eintrag) => (
              <button
                key={eintrag.name}
                type="button"
                onClick={() => navigiere(pfadZuSchlagwort(eintrag.name))}
                className="flex items-center gap-1.5 rounded-full bg-primary-light px-3 py-1 text-sm transition hover:bg-primary hover:text-white"
              >
                {eintrag.name}
                <span className="text-xs opacity-70">{eintrag.anzahl}</span>
              </button>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

/** Alle Seiten zu einem Schlagwort. */
export function LabelPage({ name }: { name: string }) {
  const [seiten, setSeiten] = useState<PageSummary[]>([]);
  const [geladen, setGeladen] = useState(false);

  useEffect(() => {
    setGeladen(false);
    let abgebrochen = false;
    void pagesByLabel(name)
      .then((liste) => {
        if (abgebrochen) return;
        setSeiten(liste);
        setGeladen(true);
      })
      .catch(() => !abgebrochen && setGeladen(true));
    return () => {
      abgebrochen = true;
    };
  }, [name]);

  return (
    <section className="rounded-lg border border-border bg-card p-5 shadow-card">
      <h2 className="flex items-center gap-2 text-lg font-semibold">
        <Tag className="h-5 w-5 text-text-secondary" />
        {name}
      </h2>
      {!geladen ? (
        <p className="mt-3 text-sm text-text-secondary">Lade …</p>
      ) : seiten.length === 0 ? (
        <p className="mt-3 text-sm text-text-secondary">Keine Seiten mit diesem Schlagwort.</p>
      ) : (
        <ul className="mt-3 flex flex-col">
          {seiten.map((seite) => (
            <li key={seite.id} className="border-b border-border last:border-b-0">
              <button
                type="button"
                onClick={() => navigiere(pfadZuSeite(seite.space_key, seite.slug))}
                className="flex w-full items-baseline gap-3 py-2 text-left hover:bg-background"
              >
                <span className="min-w-0 flex-1 truncate text-sm font-medium">{seite.title}</span>
                <span className="shrink-0 text-xs text-text-secondary">{seite.space_name}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
