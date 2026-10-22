/**
 * Anmeldemaske — das Einzige, was ein nicht angemeldeter Besucher sieht.
 *
 * Ein echtes <form>, damit Enter funktioniert und der Passwortmanager des
 * Browsers die Felder erkennt (dafür die autoComplete-Angaben).
 */

import { useState, type FormEvent } from "react";
import { Loader2, LogIn } from "lucide-react";

import { useAuth } from "../lib/auth";
import { WIKI_NAME } from "../lib/wikiName";

export function LoginMaske() {
  const { anmelden } = useAuth();
  const [username, setUsername] = useState("");
  const [passwort, setPasswort] = useState("");
  const [fehler, setFehler] = useState<string | null>(null);
  const [laeuft, setLaeuft] = useState(false);

  async function absenden(e: FormEvent) {
    e.preventDefault();
    setFehler(null);
    setLaeuft(true);
    try {
      await anmelden(username.trim(), passwort);
    } catch (e) {
      setFehler(e instanceof Error ? e.message : "Anmeldung fehlgeschlagen");
      setPasswort("");
    } finally {
      setLaeuft(false);
    }
  }

  return (
    <div className="flex h-full items-center justify-center bg-background p-4">
      <form
        onSubmit={(e) => void absenden(e)}
        className="w-full max-w-sm rounded-lg border border-border bg-card p-6 shadow-card"
      >
        <h1 className="text-lg font-semibold text-text">{WIKI_NAME}</h1>
        <p className="mt-1 text-sm text-text-secondary">Bitte anmelden.</p>

        <label className="mt-5 block text-sm text-text-secondary" htmlFor="benutzername">
          Benutzername
        </label>
        <input
          id="benutzername"
          name="username"
          autoComplete="username"
          autoFocus
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          className="mt-1 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm focus:border-primary focus:outline-none"
        />

        <label className="mt-4 block text-sm text-text-secondary" htmlFor="passwort">
          Passwort
        </label>
        <input
          id="passwort"
          name="password"
          type="password"
          autoComplete="current-password"
          value={passwort}
          onChange={(e) => setPasswort(e.target.value)}
          className="mt-1 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm focus:border-primary focus:outline-none"
        />

        {fehler !== null && (
          <p className="mt-3 rounded-lg border border-danger/40 bg-danger/10 px-3 py-2 text-sm text-danger">
            {fehler}
          </p>
        )}

        <button
          type="submit"
          disabled={laeuft || username.trim() === "" || passwort === ""}
          className="mt-5 flex w-full items-center justify-center gap-2 rounded-lg bg-primary px-3 py-2 text-sm font-medium text-white transition hover:bg-primary-hover disabled:opacity-50"
        >
          {laeuft ? <Loader2 className="h-4 w-4 animate-spin" /> : <LogIn className="h-4 w-4" />}
          Anmelden
        </button>
      </form>
    </div>
  );
}
