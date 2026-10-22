/**
 * Versionshistorie einer Seite: Liste, Vergleich, Zurückholen.
 *
 * Der Vergleich kommt fertig vom Backend (`difflib`), das Frontend malt ihn nur
 * aus — so bleibt hier keine Diff-Bibliothek nötig.
 */

import { History, Loader2, RotateCcw } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import {
  diffVersions,
  listVersions,
  restoreVersion,
  type PageVersionInfo,
  type VersionDiff,
} from "../lib/api-client";
import { cn } from "../lib/utils";

interface Props {
  pageId: number;
  onZurueckgeholt: () => void;
}

export function VersionHistory({ pageId, onZurueckgeholt }: Props) {
  const [offen, setOffen] = useState(false);
  const [versionen, setVersionen] = useState<PageVersionInfo[]>([]);
  const [vergleich, setVergleich] = useState<VersionDiff | null>(null);
  const [laeuft, setLaeuft] = useState(false);
  const [fehler, setFehler] = useState<string | null>(null);

  const laden = useCallback(async () => {
    try {
      setVersionen(await listVersions(pageId));
    } catch (e) {
      setFehler(e instanceof Error ? e.message : "Historie nicht ladbar");
    }
  }, [pageId]);

  useEffect(() => {
    setOffen(false);
    setVergleich(null);
    setFehler(null);
  }, [pageId]);

  useEffect(() => {
    if (offen) void laden();
  }, [offen, laden]);

  const vergleichen = async (revision: number) => {
    // Immer gegen die unmittelbar ältere Revision — das ist die Frage, die man
    // an eine Historie fast immer stellt: was hat dieser Schritt geändert?
    if (revision <= 1) return;
    setLaeuft(true);
    setFehler(null);
    try {
      setVergleich(await diffVersions(pageId, revision - 1, revision));
    } catch (e) {
      setFehler(e instanceof Error ? e.message : "Vergleich fehlgeschlagen");
    } finally {
      setLaeuft(false);
    }
  };

  const zurueckholen = async (revision: number) => {
    if (!window.confirm(`Stand aus Revision ${revision} zurückholen?`)) return;
    setLaeuft(true);
    try {
      await restoreVersion(pageId, revision);
      setVergleich(null);
      await laden();
      onZurueckgeholt();
    } catch (e) {
      setFehler(e instanceof Error ? e.message : "Zurückholen fehlgeschlagen");
    } finally {
      setLaeuft(false);
    }
  };

  return (
    <section className="mt-6 border-t border-border pt-4">
      <button
        type="button"
        onClick={() => setOffen((o) => !o)}
        className="flex items-center gap-2 text-sm font-semibold text-text-secondary transition hover:text-text"
      >
        <History className="h-4 w-4" />
        Versionen
        <span className="text-xs font-normal">{offen ? "ausblenden" : "anzeigen"}</span>
      </button>

      {offen && (
        <div className="mt-3">
          {fehler !== null && <p className="mb-2 text-sm text-danger">{fehler}</p>}

          <ul className="flex flex-col gap-1">
            {versionen.map((version) => (
              <li
                key={version.revision}
                className="flex items-center gap-2 rounded-lg px-2 py-1.5 text-sm hover:bg-background"
              >
                <span className="w-12 shrink-0 text-text-secondary">
                  #{version.revision}
                </span>
                <span className="min-w-0 flex-1 truncate">
                  {version.title}
                  {version.author !== null && (
                    <span className="text-text-secondary"> · {version.author}</span>
                  )}
                </span>
                <span className="shrink-0 text-xs text-text-secondary">
                  {new Date(version.created_at).toLocaleString("de-DE")}
                </span>
                {version.revision > 1 && (
                  <button
                    type="button"
                    onClick={() => void vergleichen(version.revision)}
                    className="shrink-0 rounded border border-border px-2 py-0.5 text-xs transition hover:bg-card"
                  >
                    Änderung
                  </button>
                )}
                <button
                  type="button"
                  onClick={() => void zurueckholen(version.revision)}
                  title={`Revision ${version.revision} zurückholen`}
                  aria-label={`Revision ${version.revision} zurückholen`}
                  className="shrink-0 rounded p-1 text-text-secondary transition hover:text-primary"
                >
                  <RotateCcw className="h-3.5 w-3.5" />
                </button>
              </li>
            ))}
          </ul>

          {laeuft && (
            <p className="mt-2 flex items-center gap-2 text-sm text-text-secondary">
              <Loader2 className="h-4 w-4 animate-spin" /> Einen Moment …
            </p>
          )}

          {vergleich !== null && (
            <div className="mt-3">
              <p className="mb-1 text-xs text-text-secondary">
                Änderungen von #{vergleich.von_revision} zu #{vergleich.nach_revision}
              </p>
              <pre className="max-h-80 overflow-auto rounded-lg border border-border bg-background p-3 text-xs leading-relaxed">
                {vergleich.zeilen.map((zeile, i) => (
                  <div
                    key={i}
                    className={cn(
                      "px-1",
                      zeile.art === "plus" && "bg-success/15 text-success",
                      zeile.art === "minus" && "bg-danger/15 text-danger",
                      zeile.art === "gleich" && "text-text-secondary",
                    )}
                  >
                    {zeile.art === "plus" ? "+ " : zeile.art === "minus" ? "− " : "  "}
                    {zeile.text === "" ? " " : zeile.text}
                  </div>
                ))}
              </pre>
            </div>
          )}
        </div>
      )}
    </section>
  );
}
