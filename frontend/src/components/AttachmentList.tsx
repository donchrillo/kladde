/**
 * Anhänge einer Seite: Liste, Hochladen, Löschen.
 *
 * Bilder werden im Editor direkt eingebettet; hier landen die Dateien, die als
 * Download an der Seite hängen sollen (PDF, Tabellen, Formulare).
 */

import { Download, Loader2, Paperclip, Trash2, Upload } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

import {
  attachmentUrl,
  deleteAttachment,
  listAttachments,
  uploadAttachment,
  type Attachment,
} from "../lib/api-client";

interface Props {
  pageId: number;
  /** Im Ansichtsmodus nur anzeigen, im Bearbeitungsmodus auch ändern. */
  bearbeitbar: boolean;
}

function groesse(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

export function AttachmentList({ pageId, bearbeitbar }: Props) {
  const [anhaenge, setAnhaenge] = useState<Attachment[]>([]);
  const [laeuft, setLaeuft] = useState(false);
  const [fehler, setFehler] = useState<string | null>(null);
  const dateiRef = useRef<HTMLInputElement>(null);

  const laden = useCallback(async () => {
    try {
      setAnhaenge(await listAttachments(pageId));
    } catch {
      /* Anhänge sind Beiwerk — ein Fehler hier darf die Seite nicht blockieren */
    }
  }, [pageId]);

  useEffect(() => {
    void laden();
  }, [laden]);

  const hochladen = async (dateien: FileList | null) => {
    if (!dateien || dateien.length === 0) return;
    setLaeuft(true);
    setFehler(null);
    try {
      for (const datei of Array.from(dateien)) {
        await uploadAttachment(pageId, datei);
      }
      await laden();
    } catch (e) {
      setFehler(e instanceof Error ? e.message : "Hochladen fehlgeschlagen");
    } finally {
      setLaeuft(false);
      if (dateiRef.current) dateiRef.current.value = "";
    }
  };

  const loeschen = async (anhang: Attachment) => {
    if (!window.confirm(`„${anhang.filename}" wirklich löschen?`)) return;
    try {
      await deleteAttachment(anhang.id);
      await laden();
    } catch (e) {
      setFehler(e instanceof Error ? e.message : "Löschen fehlgeschlagen");
    }
  };

  if (anhaenge.length === 0 && !bearbeitbar) return null;

  return (
    <section className="mt-8 border-t border-border pt-4">
      <h3 className="flex items-center gap-2 text-sm font-semibold text-text-secondary">
        <Paperclip className="h-4 w-4" />
        Anhänge
      </h3>

      {anhaenge.length === 0 ? (
        <p className="mt-2 text-sm text-text-secondary">Noch keine Dateien.</p>
      ) : (
        <ul className="mt-2 flex flex-col gap-1">
          {anhaenge.map((anhang) => (
            <li
              key={anhang.id}
              className="group flex items-center gap-2 rounded-lg px-2 py-1.5 hover:bg-background"
            >
              <a
                href={attachmentUrl(anhang.id)}
                download={anhang.filename}
                className="flex min-w-0 flex-1 items-center gap-2 text-sm"
              >
                <Download className="h-4 w-4 shrink-0 text-text-secondary" />
                <span className="truncate">{anhang.filename}</span>
                <span className="shrink-0 text-xs text-text-secondary">
                  {groesse(anhang.size_bytes)}
                </span>
              </a>
              {bearbeitbar && (
                <button
                  type="button"
                  onClick={() => void loeschen(anhang)}
                  title="Anhang löschen"
                  aria-label={`${anhang.filename} löschen`}
                  className="shrink-0 rounded p-1 text-text-secondary opacity-0 transition group-hover:opacity-100 hover:text-danger focus:opacity-100"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              )}
            </li>
          ))}
        </ul>
      )}

      {bearbeitbar && (
        <>
          <input
            ref={dateiRef}
            type="file"
            multiple
            hidden
            onChange={(e) => void hochladen(e.target.files)}
          />
          <button
            type="button"
            onClick={() => dateiRef.current?.click()}
            disabled={laeuft}
            className="mt-3 flex items-center gap-2 rounded-lg border border-border px-3 py-1.5 text-sm transition hover:bg-background disabled:opacity-50"
          >
            {laeuft ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Upload className="h-4 w-4" />
            )}
            Datei anhängen
          </button>
        </>
      )}

      {fehler !== null && <p className="mt-2 text-sm text-danger">{fehler}</p>}
    </section>
  );
}
