/**
 * Eigenes Konto: Stammdaten und Passwort ändern.
 *
 * Erreichbar unter `#/konto`, für jeden angemeldeten Benutzer — im
 * Unterschied zur Verwaltung, die nur Administratoren offensteht.
 */

import { KeyRound } from "lucide-react";
import { useState } from "react";

import { setPassword } from "../lib/api-client";
import { useAuth } from "../lib/auth";
import { PasswortDialog } from "./PasswortDialog";

export function KontoPage() {
  const { ich } = useAuth();
  const [dialogOffen, setDialogOffen] = useState(false);
  const [meldung, setMeldung] = useState<string | null>(null);

  if (ich === null || ich.ist_offener_betrieb || ich.id === null) {
    return (
      <p className="text-text-secondary">
        Dieses Wiki läuft im offenen Betrieb ohne Anmeldung — es gibt daher kein Konto.
      </p>
    );
  }
  const kontoId = ich.id;

  const passwortAendern = async (neu: string, alt?: string) => {
    await setPassword(kontoId, neu, alt);
    setDialogOffen(false);
    setMeldung("Passwort geändert. Alle anderen Sitzungen dieses Kontos wurden beendet.");
  };

  const zeile = "flex items-center justify-between gap-4 border-b border-border px-4 py-3 last:border-b-0";

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-text">Konto</h1>
        <p className="mt-1 text-sm text-text-secondary">Eigene Stammdaten und Passwort.</p>
      </div>

      {meldung !== null && (
        <p className="rounded-lg border border-primary/40 bg-primary-light px-3 py-2 text-sm text-text">
          {meldung}
        </p>
      )}

      <div className="overflow-hidden rounded-lg border border-border bg-card shadow-card">
        <div className={zeile}>
          <span className="text-sm text-text-secondary">Anzeigename</span>
          <span className="text-sm text-text">{ich.display_name}</span>
        </div>
        <div className={zeile}>
          <span className="text-sm text-text-secondary">Anmeldename</span>
          <span className="text-sm text-text">{ich.username}</span>
        </div>
        <div className={zeile}>
          <span className="text-sm text-text-secondary">Rolle</span>
          <span className="text-sm text-text">{ich.is_admin ? "Administrator" : "Benutzer"}</span>
        </div>
        <div className={zeile}>
          <span className="text-sm text-text-secondary">Bereiche anlegen</span>
          <span className="text-sm text-text">
            {ich.is_admin || ich.darf_bereiche_anlegen ? "erlaubt" : "nicht erlaubt"}
          </span>
        </div>
      </div>

      <button
        type="button"
        onClick={() => setDialogOffen(true)}
        className="flex items-center gap-2 rounded-lg border border-border px-3 py-2 text-sm transition hover:bg-background"
      >
        <KeyRound className="h-4 w-4" />
        Passwort ändern
      </button>

      {dialogOffen && (
        <PasswortDialog
          titel="Passwort ändern"
          altesPasswortNoetig
          onSpeichern={passwortAendern}
          onAbbruch={() => setDialogOffen(false)}
        />
      )}
    </div>
  );
}
