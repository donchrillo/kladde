/**
 * Dialog zum Setzen eines neuen Passworts.
 *
 * Ersetzt `window.prompt`/`window.alert`: ein echtes Formular mit Mindestlänge,
 * Wiederholung und — wenn der Benutzer sein eigenes Passwort ändert — Abfrage
 * des alten Passworts. Overlay nach dem Muster von `MovePicker.tsx`.
 */

import { KeyRound, Loader2, X } from "lucide-react";
import { useState, type FormEvent } from "react";

interface Props {
  titel: string;
  /** Ob zusätzlich das alte Passwort abgefragt wird (Selbstbedienung). */
  altesPasswortNoetig: boolean;
  onSpeichern: (neu: string, alt?: string) => Promise<void>;
  onAbbruch: () => void;
}

const MINDESTLAENGE = 8;

export function PasswortDialog({ titel, altesPasswortNoetig, onSpeichern, onAbbruch }: Props) {
  const [altesPasswort, setAltesPasswort] = useState("");
  const [neuesPasswort, setNeuesPasswort] = useState("");
  const [wiederholung, setWiederholung] = useState("");
  const [fehler, setFehler] = useState<string | null>(null);
  const [laeuft, setLaeuft] = useState(false);

  const stimmtUeberein = neuesPasswort === wiederholung;
  const gueltig =
    neuesPasswort.length >= MINDESTLAENGE &&
    stimmtUeberein &&
    (!altesPasswortNoetig || altesPasswort.length > 0);

  const absenden = async (e: FormEvent) => {
    e.preventDefault();
    if (!gueltig) return;
    setLaeuft(true);
    setFehler(null);
    try {
      await onSpeichern(neuesPasswort, altesPasswortNoetig ? altesPasswort : undefined);
    } catch (err) {
      setFehler(err instanceof Error ? err.message : "Passwort konnte nicht gesetzt werden");
      setLaeuft(false);
    }
  };

  const feld =
    "w-full rounded-lg border border-border bg-background px-3 py-2 text-sm focus:border-primary focus:outline-none";

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center bg-black/50 p-4 pt-16">
      <button className="fixed inset-0" onClick={onAbbruch} aria-label="Abbrechen" />
      <form
        onSubmit={(e) => void absenden(e)}
        onKeyDown={(e) => e.key === "Escape" && onAbbruch()}
        className="relative flex w-full max-w-sm flex-col rounded-lg border border-border bg-card p-4 shadow-card"
      >
        <div className="mb-3 flex items-start justify-between gap-2">
          <p className="text-sm font-medium text-text">{titel}</p>
          <button
            type="button"
            onClick={onAbbruch}
            title="Abbrechen"
            aria-label="Abbrechen"
            className="-mt-1 shrink-0 rounded p-1 text-text-secondary transition hover:bg-background hover:text-text"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {fehler !== null && (
          <p className="mb-3 rounded-lg border border-danger/40 bg-danger/10 px-3 py-2 text-sm text-danger">
            {fehler}
          </p>
        )}

        <div className="space-y-3">
          {altesPasswortNoetig && (
            <input
              className={feld}
              type="password"
              placeholder="Aktuelles Passwort"
              autoComplete="current-password"
              value={altesPasswort}
              onChange={(e) => setAltesPasswort(e.target.value)}
            />
          )}
          <input
            className={feld}
            type="password"
            placeholder={`Neues Passwort (mind. ${MINDESTLAENGE} Zeichen)`}
            autoComplete="new-password"
            value={neuesPasswort}
            onChange={(e) => setNeuesPasswort(e.target.value)}
          />
          <input
            className={feld}
            type="password"
            placeholder="Neues Passwort wiederholen"
            autoComplete="new-password"
            value={wiederholung}
            onChange={(e) => setWiederholung(e.target.value)}
          />
          {wiederholung.length > 0 && !stimmtUeberein && (
            <p className="text-xs text-danger">Die Wiederholung stimmt nicht überein.</p>
          )}
        </div>

        <div className="mt-4 flex justify-end gap-2">
          <button
            type="button"
            onClick={onAbbruch}
            className="rounded-lg border border-border px-3 py-2 text-sm transition hover:bg-background"
          >
            Abbrechen
          </button>
          <button
            type="submit"
            disabled={!gueltig || laeuft}
            className="flex items-center gap-2 rounded-lg bg-primary px-3 py-2 text-sm font-medium text-white transition hover:bg-primary-hover disabled:opacity-50"
          >
            {laeuft ? <Loader2 className="h-4 w-4 animate-spin" /> : <KeyRound className="h-4 w-4" />}
            Speichern
          </button>
        </div>
      </form>
    </div>
  );
}
