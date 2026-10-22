/**
 * Auswahl einer Wiki-Seite zum Verlinken.
 *
 * Sucht standardmäßig im aktuellen Bereich (dorthin verlinkt man am häufigsten),
 * auf Wunsch im ganzen Wiki.
 */

import { Loader2, Search } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { searchIn, type SearchHit } from "../lib/api-client";
import { markdownLink } from "../lib/route";

export interface LinkWahl {
  titel: string;
  href: string;
}

interface Props {
  spaceId: number;
  spaceName: string;
  onWahl: (wahl: LinkWahl) => void;
  onAbbruch: () => void;
}

export function LinkPicker({ spaceId, spaceName, onWahl, onAbbruch }: Props) {
  const [begriff, setBegriff] = useState("");
  const [nurBereich, setNurBereich] = useState(true);
  const [treffer, setTreffer] = useState<SearchHit[]>([]);
  const [laeuft, setLaeuft] = useState(false);
  const eingabeRef = useRef<HTMLInputElement>(null);

  useEffect(() => eingabeRef.current?.focus(), []);

  useEffect(() => {
    const frage = begriff.trim();
    if (frage === "") {
      setTreffer([]);
      return;
    }
    let abgebrochen = false;
    setLaeuft(true);
    const zeitgeber = window.setTimeout(() => {
      void searchIn(frage, nurBereich ? spaceId : undefined)
        .then((gefunden) => !abgebrochen && setTreffer(gefunden))
        .catch(() => !abgebrochen && setTreffer([]))
        .finally(() => !abgebrochen && setLaeuft(false));
    }, 200);
    return () => {
      abgebrochen = true;
      window.clearTimeout(zeitgeber);
    };
  }, [begriff, nurBereich, spaceId]);

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center bg-black/50 p-4 pt-24">
      <button className="fixed inset-0" onClick={onAbbruch} aria-label="Abbrechen" />
      <div className="relative w-full max-w-lg rounded-lg border border-border bg-card shadow-card">
        <div className="border-b border-border p-3">
          <div className="relative">
            <Search className="pointer-events-none absolute top-1/2 left-3 h-4 w-4 -translate-y-1/2 text-text-secondary" />
            <input
              ref={eingabeRef}
              value={begriff}
              onChange={(e) => setBegriff(e.target.value)}
              onKeyDown={(e) => e.key === "Escape" && onAbbruch()}
              placeholder="Seite suchen …"
              aria-label="Seite zum Verlinken suchen"
              className="w-full rounded-lg border border-border bg-background py-2 pr-3 pl-9 text-sm focus:border-primary focus:outline-none"
            />
          </div>
          <label className="mt-2 flex items-center gap-2 text-xs text-text-secondary">
            <input
              type="checkbox"
              checked={nurBereich}
              onChange={(e) => setNurBereich(e.target.checked)}
            />
            Nur im Bereich „{spaceName}"
          </label>
        </div>

        <div className="max-h-72 overflow-y-auto">
          {laeuft && (
            <p className="flex items-center gap-2 px-3 py-3 text-sm text-text-secondary">
              <Loader2 className="h-4 w-4 animate-spin" /> Suche …
            </p>
          )}
          {!laeuft && begriff.trim() !== "" && treffer.length === 0 && (
            <p className="px-3 py-3 text-sm text-text-secondary">Keine Treffer.</p>
          )}
          {treffer.map((hit) => (
            <button
              key={hit.page_id}
              type="button"
              onClick={() =>
                onWahl({ titel: hit.title, href: markdownLink(hit.space_key, hit.slug) })
              }
              className="block w-full border-b border-border px-3 py-2 text-left last:border-b-0 hover:bg-background"
            >
              <span className="block text-sm font-medium">{hit.title}</span>
              <span className="block text-xs text-text-secondary">{hit.space_name}</span>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
