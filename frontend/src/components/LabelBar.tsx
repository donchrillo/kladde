/**
 * Schlagwörter einer Seite anzeigen und bearbeiten.
 *
 * Im Ansichtsmodus sind sie anklickbar und führen zur Liste aller Seiten mit
 * diesem Schlagwort; im Bearbeitungsmodus kommen Eingabefeld und Entfernen-Knopf
 * dazu.
 */

import { Tag, X } from "lucide-react";
import { useEffect, useState } from "react";

import { setLabels } from "../lib/api-client";
import { navigiere, pfadZuSchlagwort } from "../lib/route";

interface Props {
  pageId: number;
  labels: string[];
  bearbeitbar: boolean;
  onGeaendert: () => void;
}

export function LabelBar({ pageId, labels, bearbeitbar, onGeaendert }: Props) {
  const [entwurf, setEntwurf] = useState("");
  const [aktuell, setAktuell] = useState<string[]>(labels);
  const [fehler, setFehler] = useState<string | null>(null);

  useEffect(() => setAktuell(labels), [labels]);

  const speichern = async (namen: string[]) => {
    const vorher = aktuell;
    setAktuell(namen); // sofort anzeigen, bei Fehler zurückrollen
    try {
      await setLabels(pageId, namen);
      setFehler(null);
      onGeaendert();
    } catch (e) {
      setAktuell(vorher);
      setFehler(e instanceof Error ? e.message : "Schlagwort nicht gespeichert");
    }
  };

  const hinzufuegen = () => {
    const name = entwurf.trim().toLowerCase();
    if (name === "" || aktuell.includes(name)) {
      setEntwurf("");
      return;
    }
    setEntwurf("");
    void speichern([...aktuell, name].sort());
  };

  if (aktuell.length === 0 && !bearbeitbar) return null;

  return (
    <div className="mt-4 flex flex-wrap items-center gap-2">
      <Tag className="h-4 w-4 shrink-0 text-text-secondary" />

      {aktuell.map((name) => (
        <span
          key={name}
          className="flex items-center gap-1 rounded-full bg-primary-light px-2.5 py-0.5 text-xs"
        >
          {bearbeitbar ? (
            <span>{name}</span>
          ) : (
            <button
              type="button"
              onClick={() => navigiere(pfadZuSchlagwort(name))}
              className="hover:underline"
            >
              {name}
            </button>
          )}
          {bearbeitbar && (
            <button
              type="button"
              onClick={() => void speichern(aktuell.filter((n) => n !== name))}
              aria-label={`Schlagwort ${name} entfernen`}
              className="text-text-secondary hover:text-danger"
            >
              <X className="h-3 w-3" />
            </button>
          )}
        </span>
      ))}

      {bearbeitbar && (
        <input
          value={entwurf}
          onChange={(e) => setEntwurf(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              hinzufuegen();
            }
          }}
          onBlur={hinzufuegen}
          placeholder="Schlagwort …"
          aria-label="Schlagwort hinzufügen"
          className="w-32 rounded-full border border-border bg-background px-2.5 py-0.5 text-xs focus:border-primary focus:outline-none"
        />
      )}

      {aktuell.length === 0 && !bearbeitbar && (
        <span className="text-xs text-text-secondary">keine</span>
      )}
      {fehler !== null && <span className="text-xs text-danger">{fehler}</span>}
    </div>
  );
}
