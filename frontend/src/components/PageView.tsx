/**
 * Eine Seite ansehen oder bearbeiten.
 *
 * Beide Zustände liegen bewusst in einer Komponente: der Wechsel soll sich wie
 * in Confluence anfühlen — dieselbe Seite, nur mit Werkzeugleiste.
 */

import { FolderInput, Link as LinkIcon, Loader2, Pencil, Trash2, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import {
  attachmentUrl,
  deletePage,
  listBacklinks,
  listVersions,
  updatePage,
  uploadAttachment,
  type Page,
  type PageNode,
  type PageSummary,
  type Space,
} from "../lib/api-client";
import { useMedienAbfrage } from "../hooks/useMedienAbfrage";
import { renderMarkdown } from "../lib/markdown";
import { navigiere, pfadZuSeite, wikiLinkZuHash } from "../lib/route";
import { hatRecht } from "../lib/utils";
import { AttachmentList } from "./AttachmentList";
import { Editor } from "./Editor";
import { LabelBar } from "./LabelBar";
import { LinkPicker, type LinkWahl } from "./LinkPicker";
import { MovePicker } from "./MovePicker";
import { TableOfContents } from "./TableOfContents";
import { VersionHistory } from "./VersionHistory";

interface Props {
  seite: Page;
  /** Bereich, in dem die Seite liegt — bestimmt über `mein_recht` die Bedienelemente. */
  space: Space | null;
  spaceName: string;
  /** Pfad von der Wurzel bis zu dieser Seite, für die Brotkrumen. */
  pfad: string[];
  /** Seitenbaum des Bereichs — nur für die Auswahl beim Verschieben. */
  baum: PageNode[];
  /** Alle Bereiche, damit sich eine Seite auch in einen anderen bewegen lässt. */
  spaces: Space[];
  maxTiefe: number;
  onGespeichert: () => void;
  /** Nach dem Verschieben: die Seite hat womöglich Bereich und Slug gewechselt. */
  onVerschoben: (seite: Page) => void;
  onGeloescht: () => void;
}

/**
 * Kurze Rückmeldung am Kopier-Knopf.
 *
 * Der Knopf gehört zum eingefügten HTML und nicht zum React-Baum, deshalb wird
 * seine Beschriftung direkt gesetzt statt über State.
 */
function rueckmeldung(knopf: HTMLButtonElement, text: string) {
  const vorher = knopf.textContent;
  knopf.textContent = text;
  window.setTimeout(() => {
    knopf.textContent = vorher;
  }, 1500);
}

export function PageView({
  seite,
  space,
  spaceName,
  pfad,
  baum,
  spaces,
  maxTiefe,
  onGespeichert,
  onVerschoben,
  onGeloescht,
}: Props) {
  const [bearbeiten, setBearbeiten] = useState(false);
  const [titel, setTitel] = useState(seite.title);
  const [laeuft, setLaeuft] = useState(false);
  const [fehler, setFehler] = useState<string | null>(null);
  // Zählt bei jedem Abbruch hoch und erzwingt zusammen mit der Seiten-ID eine
  // frische Editor-Instanz — siehe `initialWert` in Editor.tsx.
  const [editorLauf, setEditorLauf] = useState(0);
  // Zugriff auf den aktuellen Editor-Inhalt beim Speichern.
  const holeMarkdown = useRef<(() => string) | null>(null);
  const [linkAuswahl, setLinkAuswahl] = useState<((wahl: LinkWahl | null) => void) | null>(null);
  const [rueckverweise, setRueckverweise] = useState<PageSummary[]>([]);
  // Autor der jüngsten Revision — Altbestand aus dem Import hat keinen.
  const [autor, setAutor] = useState<string | null>(null);
  const [verschieben, setVerschieben] = useState(false);
  // Ab `xl` (Tailwind: 80rem) steht das Inhaltsverzeichnis rechts statt oben.
  const breit = useMedienAbfrage("(min-width: 80rem)");
  const darfSchreiben = hatRecht(space, "schreiben");
  const darfLoeschen = hatRecht(space, "loeschen");

  // Bei Seitenwechsel den Entwurf verwerfen und zurück in die Ansicht.
  useEffect(() => {
    setBearbeiten(false);
    setTitel(seite.title);
    setFehler(null);
  }, [seite.id, seite.title, seite.body]);

  const abbrechen = () => {
    setBearbeiten(false);
    setTitel(seite.title);
    setEditorLauf((n) => n + 1);
  };

  const speichern = async () => {
    setLaeuft(true);
    setFehler(null);
    try {
      const inhalt = holeMarkdown.current?.() ?? seite.body;
      await updatePage(seite.id, { title: titel.trim() || seite.title, body: inhalt });
      setBearbeiten(false);
      onGespeichert();
    } catch (e) {
      setFehler(e instanceof Error ? e.message : "Speichern fehlgeschlagen");
    } finally {
      setLaeuft(false);
    }
  };

  const verschiebenNach = async (spaceId: number, parentId: number | null) => {
    setVerschieben(false);
    try {
      // `space_id` immer mitschicken: das Backend erkennt daran, ob es ein
      // Bereichswechsel ist, und lässt es sonst schlicht unbeachtet.
      onVerschoben(await updatePage(seite.id, { space_id: spaceId, parent_id: parentId }));
    } catch (e) {
      setFehler(e instanceof Error ? e.message : "Verschieben fehlgeschlagen");
    }
  };

  const loeschen = async () => {
    if (!window.confirm(`Seite „${seite.title}" wirklich löschen?`)) return;
    try {
      await deletePage(seite.id);
      onGeloescht();
    } catch (e) {
      setFehler(e instanceof Error ? e.message : "Löschen fehlgeschlagen");
    }
  };

  useEffect(() => {
    let abgebrochen = false;
    void listBacklinks(seite.id)
      .then((liste) => !abgebrochen && setRueckverweise(liste))
      .catch(() => !abgebrochen && setRueckverweise([]));
    // Autor der jüngsten Revision für die Zeile unter dem Titel. Seiten aus
    // dem Confluence-Import haben oft keinen — dann bleibt es beim Datum.
    void listVersions(seite.id)
      .then((liste) => !abgebrochen && setAutor(liste[0]?.author ?? null))
      .catch(() => !abgebrochen && setAutor(null));
    return () => {
      abgebrochen = true;
    };
  }, [seite.id, seite.updated_at]);

  /**
   * Klicks auf interne Wiki-Links abfangen und intern navigieren, statt den
   * Browser die Adresse `/wiki/...` laden zu lassen (die es serverseitig nicht
   * gibt). Externe Links bleiben unberührt.
   */
  const beiKlickImInhalt = (e: React.MouseEvent<HTMLDivElement>) => {
    // Kopier-Knopf an Codeblöcken. Der gerenderte HTML-Code darf kein eigenes
    // JavaScript mitbringen — DOMPurify würde es entfernen —, deshalb hängt der
    // Klick hier am selben Delegaten wie die Links.
    const knopf = (e.target as HTMLElement).closest<HTMLButtonElement>("button[data-kopieren]");
    if (knopf !== null) {
      e.preventDefault();
      const code = knopf.parentElement?.querySelector("code")?.textContent ?? "";
      void navigator.clipboard.writeText(code).then(
        () => rueckmeldung(knopf, "Kopiert"),
        () => rueckmeldung(knopf, "Fehlgeschlagen"),
      );
      return;
    }

    const ziel = (e.target as HTMLElement).closest("a");
    const href = ziel?.getAttribute("href");
    if (!href) return;
    const hash = wikiLinkZuHash(href);
    if (hash !== null) {
      e.preventDefault();
      navigiere(hash);
    }
  };

  /** Öffnet die Seitenauswahl und liefert die Wahl an den Editor zurück. */
  const wikiLinkWaehlen = (): Promise<LinkWahl | null> =>
    new Promise((aufloesen) => setLinkAuswahl(() => aufloesen));

  /** Bild im Editor: als Anhang hochladen und die Download-URL einbetten. */
  const bildHochladen = async (datei: File): Promise<string> => {
    const anhang = await uploadAttachment(seite.id, datei);
    return attachmentUrl(anhang.id);
  };

  const inhaltsverzeichnis = !bearbeiten && seite.body.trim() !== "" && (
    <TableOfContents markdown={seite.body} variante={breit ? "seitlich" : "oben"} />
  );

  return (
    <div className="flex items-start gap-6">
      <article className="min-w-0 flex-1 rounded-lg border border-border bg-card p-5 shadow-card sm:p-8">
        {pfad.length > 1 && (
          <nav className="mb-2 text-xs text-text-secondary">{pfad.join(" › ")}</nav>
        )}

        <div className="flex items-start gap-3">
          {bearbeiten ? (
            <input
              value={titel}
              onChange={(e) => setTitel(e.target.value)}
              aria-label="Seitentitel"
              className="min-w-0 flex-1 rounded-lg border border-border bg-background px-3 py-2 text-2xl font-semibold tracking-tight focus:border-primary focus:outline-none"
            />
          ) : (
            <h2 className="min-w-0 flex-1 text-2xl font-semibold tracking-tight">{seite.title}</h2>
          )}

          <div className="flex shrink-0 items-center gap-1">
            {bearbeiten ? (
              <>
                <button
                  type="button"
                  onClick={() => void speichern()}
                  disabled={laeuft}
                  className="flex items-center gap-2 rounded-lg bg-primary px-3 py-2 text-sm font-medium text-white transition hover:bg-primary-hover disabled:opacity-50"
                >
                  {laeuft && <Loader2 className="h-4 w-4 animate-spin" />}
                  Speichern
                </button>
                <button
                  type="button"
                  onClick={abbrechen}
                  title="Abbrechen"
                  aria-label="Abbrechen"
                  className="rounded-lg p-2 text-text-secondary transition hover:bg-background"
                >
                  <X className="h-5 w-5" />
                </button>
              </>
            ) : (
              <>
                {darfSchreiben && (
                  <button
                    type="button"
                    onClick={() => setBearbeiten(true)}
                    className="flex items-center gap-2 rounded-lg border border-border px-3 py-2 text-sm transition hover:bg-background"
                  >
                    <Pencil className="h-4 w-4" />
                    Bearbeiten
                  </button>
                )}
                {darfSchreiben && (
                  <button
                    type="button"
                    onClick={() => setVerschieben(true)}
                    title="Seite verschieben"
                    aria-label="Seite verschieben"
                    className="rounded-lg p-2 text-text-secondary transition hover:bg-background hover:text-text"
                  >
                    <FolderInput className="h-5 w-5" />
                  </button>
                )}
                {darfLoeschen && (
                  <button
                    type="button"
                    onClick={() => void loeschen()}
                    title="Seite löschen"
                    aria-label="Seite löschen"
                    className="rounded-lg p-2 text-text-secondary transition hover:bg-background hover:text-danger"
                  >
                    <Trash2 className="h-5 w-5" />
                  </button>
                )}
              </>
            )}
          </div>
        </div>

        <p className="mt-1 text-xs text-text-secondary">
          {autor !== null && `Von ${autor} · `}
          Aktualisiert am {new Date(seite.updated_at).toLocaleString("de-DE")}
        </p>

        {fehler !== null && (
          <p className="mt-3 rounded-lg border border-danger/40 bg-danger/10 px-3 py-2 text-sm text-danger">
            {fehler}
          </p>
        )}

        <div className="mt-6">
          {bearbeiten ? (
            <Editor
              key={`${seite.id}-${editorLauf}`}
              initialWert={seite.body}
              holeMarkdown={holeMarkdown}
              onBildEinfuegen={bildHochladen}
              onWikiLink={wikiLinkWaehlen}
            />
          ) : seite.body.trim() === "" ? (
            <p className="text-sm text-text-secondary">
              {darfSchreiben
                ? 'Diese Seite ist noch leer. Über „Bearbeiten" Inhalt anlegen.'
                : "Diese Seite ist noch leer."}
            </p>
          ) : (
            <>
              {!breit && inhaltsverzeichnis}
              <div
                className="wiki-inhalt"
                onClick={beiKlickImInhalt}
                // Inhalt ist in renderMarkdown bereits durch DOMPurify gelaufen.
                dangerouslySetInnerHTML={{ __html: renderMarkdown(seite.body) }}
              />
            </>
          )}
        </div>

        <LabelBar
          pageId={seite.id}
          labels={seite.labels}
          bearbeitbar={bearbeiten}
          onGeaendert={onGespeichert}
        />

        <AttachmentList pageId={seite.id} bearbeitbar={bearbeiten && darfSchreiben} />

        {!bearbeiten && rueckverweise.length > 0 && (
          <section className="mt-6 border-t border-border pt-4">
            <h3 className="flex items-center gap-2 text-sm font-semibold text-text-secondary">
              <LinkIcon className="h-4 w-4" />
              Verlinkt von
            </h3>
            <ul className="mt-2 flex flex-col gap-1">
              {rueckverweise.map((verweis) => (
                <li key={verweis.id}>
                  <button
                    type="button"
                    onClick={() => navigiere(pfadZuSeite(verweis.space_key, verweis.slug))}
                    className="text-sm text-primary hover:underline"
                  >
                    {verweis.title}
                  </button>
                  <span className="ml-2 text-xs text-text-secondary">{verweis.space_name}</span>
                </li>
              ))}
            </ul>
          </section>
        )}

        {!bearbeiten && <VersionHistory pageId={seite.id} onZurueckgeholt={onGespeichert} />}

        {verschieben && (
          <MovePicker
            seiteId={seite.id}
            titel={seite.title}
            aktuellerElternteil={seite.parent_id}
            aktuellerSpaceId={seite.space_id}
            baum={baum}
            spaces={spaces}
            maxTiefe={maxTiefe}
            onWahl={(spaceId, parentId) => void verschiebenNach(spaceId, parentId)}
            onAbbruch={() => setVerschieben(false)}
          />
        )}

        {linkAuswahl !== null && (
          <LinkPicker
            spaceId={seite.space_id}
            spaceName={spaceName}
            onWahl={(wahl) => {
              linkAuswahl(wahl);
              setLinkAuswahl(null);
            }}
            onAbbruch={() => {
              linkAuswahl(null);
              setLinkAuswahl(null);
            }}
          />
        )}
      </article>

      {breit && inhaltsverzeichnis && (
        <aside className="sticky top-8 hidden w-56 shrink-0 xl:block">{inhaltsverzeichnis}</aside>
      )}
    </div>
  );
}
