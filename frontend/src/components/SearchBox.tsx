/**
 * Suchfeld in der Kopfzeile.
 *
 * Sucht über alle lesbaren Bereiche und zeigt die Treffer als Auswahlliste
 * darunter. Die Anfrage ist entprellt, damit nicht jeder Tastenanschlag eine
 * Abfrage auslöst.
 */

import { Loader2, Search, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { search, type SearchHit } from "../lib/api-client";
import { navigiere, pfadZuSeite } from "../lib/route";

/** Hebt die Fundstellen hervor, die das Backend mit [[ ]] markiert hat. */
function Ausschnitt({ text }: { text: string }) {
  return (
    <>
      {text.split(/(\[\[.*?\]\])/g).map((stueck, i) =>
        stueck.startsWith("[[") && stueck.endsWith("]]") ? (
          <mark key={i} className="rounded bg-warning/30 px-0.5 text-text">
            {stueck.slice(2, -2)}
          </mark>
        ) : (
          <span key={i}>{stueck}</span>
        ),
      )}
    </>
  );
}

export function SearchBox() {
  const [begriff, setBegriff] = useState("");
  const [treffer, setTreffer] = useState<SearchHit[]>([]);
  const [laeuft, setLaeuft] = useState(false);
  const [offen, setOffen] = useState(false);
  const huelleRef = useRef<HTMLDivElement>(null);

  // Entprellt: erst 250 ms nach der letzten Eingabe wird gesucht.
  useEffect(() => {
    const frage = begriff.trim();
    if (frage === "") {
      setTreffer([]);
      setLaeuft(false);
      return;
    }
    setLaeuft(true);
    // Das Flag gehört auf Effekt-Ebene: sonst könnte eine langsame Antwort zu
    // einem alten Suchbegriff eine neuere Trefferliste überschreiben.
    let abgebrochen = false;
    const zeitgeber = window.setTimeout(() => {
      void search(frage)
        .then((gefunden) => {
          if (abgebrochen) return;
          setTreffer(gefunden);
          setOffen(true);
        })
        .catch(() => {
          if (!abgebrochen) setTreffer([]);
        })
        .finally(() => {
          if (!abgebrochen) setLaeuft(false);
        });
    }, 250);
    return () => {
      abgebrochen = true;
      window.clearTimeout(zeitgeber);
    };
  }, [begriff]);

  // Klick außerhalb schließt die Trefferliste.
  useEffect(() => {
    const beiKlick = (e: MouseEvent) => {
      if (!huelleRef.current?.contains(e.target as Node)) setOffen(false);
    };
    document.addEventListener("mousedown", beiKlick);
    return () => document.removeEventListener("mousedown", beiKlick);
  }, []);

  const oeffnen = (hit: SearchHit) => {
    navigiere(pfadZuSeite(hit.space_key, hit.slug));
    setOffen(false);
    setBegriff("");
  };

  return (
    <div ref={huelleRef} className="relative w-full max-w-md">
      <div className="relative">
        <Search className="pointer-events-none absolute top-1/2 left-3 h-4 w-4 -translate-y-1/2 text-text-secondary" />
        <input
          value={begriff}
          onChange={(e) => setBegriff(e.target.value)}
          onFocus={() => treffer.length > 0 && setOffen(true)}
          onKeyDown={(e) => {
            if (e.key === "Escape") setOffen(false);
            if (e.key === "Enter" && treffer.length > 0) oeffnen(treffer[0]);
          }}
          placeholder="Im ganzen Wiki suchen …"
          aria-label="Suche"
          className="w-full rounded-lg border border-border bg-background py-2 pr-9 pl-9 text-sm text-text placeholder:text-text-secondary focus:border-primary focus:outline-none"
        />
        {laeuft ? (
          <Loader2 className="absolute top-1/2 right-3 h-4 w-4 -translate-y-1/2 animate-spin text-text-secondary" />
        ) : (
          begriff !== "" && (
            <button
              type="button"
              onClick={() => {
                setBegriff("");
                setOffen(false);
              }}
              aria-label="Suche leeren"
              className="absolute top-1/2 right-2 -translate-y-1/2 rounded p-1 text-text-secondary hover:text-text"
            >
              <X className="h-4 w-4" />
            </button>
          )
        )}
      </div>

      {offen && begriff.trim() !== "" && (
        <div className="absolute top-full right-0 left-0 z-30 mt-1 max-h-96 overflow-y-auto rounded-lg border border-border bg-card shadow-card">
          {treffer.length === 0 ? (
            <p className="px-3 py-3 text-sm text-text-secondary">
              {laeuft ? "Suche läuft …" : "Keine Treffer."}
            </p>
          ) : (
            treffer.map((hit) => (
              <button
                key={hit.page_id}
                type="button"
                onClick={() => oeffnen(hit)}
                className="block w-full border-b border-border px-3 py-2 text-left last:border-b-0 hover:bg-background"
              >
                <span className="block text-sm font-medium">{hit.title}</span>
                <span className="block text-xs text-text-secondary">{hit.space_name}</span>
                {hit.excerpt !== "" && (
                  <span className="mt-0.5 block text-xs text-text-secondary">
                    <Ausschnitt text={hit.excerpt} />
                  </span>
                )}
              </button>
            ))
          )}
        </div>
      )}
    </div>
  );
}
