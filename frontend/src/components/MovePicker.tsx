/**
 * Auswahl eines neuen Elternteils für eine Seite.
 *
 * Bewusst eine Liste zum Anklicken statt Drag-and-drop: bei knapp hundert
 * Seiten je Bereich trifft man mit der Maus schlecht, und ein Ziel, das gegen
 * die Ebenengrenze verstößt, lässt sich hier vorher erklären statt den Zug
 * hinterher abzulehnen.
 */

import { CornerLeftUp, FileText, Loader2, Search, X } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import { getSpaceTree, type PageNode, type Space } from "../lib/api-client";
import { cn, hatRecht } from "../lib/utils";
import { filtereBaum } from "./PageTree";

interface Props {
  /** Die Seite, die verschoben wird. */
  seiteId: number;
  titel: string;
  /** Aktueller Elternteil, um ihn als solchen zu kennzeichnen. */
  aktuellerElternteil: number | null;
  /** Bereich, in dem die Seite gerade liegt. */
  aktuellerSpaceId: number;
  /** Seitenbaum des aktuellen Bereichs; andere werden bei Bedarf geholt. */
  baum: PageNode[];
  spaces: Space[];
  maxTiefe: number;
  onWahl: (spaceId: number, parentId: number | null) => void;
  onAbbruch: () => void;
}

interface Ziel {
  id: number | null;
  titel: string;
  /** Ebene, auf der das Ziel selbst liegt (oberste Ebene = 0). */
  ebene: number;
  /** Grund, warum das Ziel nicht in Frage kommt — sonst `null`. */
  gesperrt: string | null;
  aktuell: boolean;
}

/** Höhe eines Astes: ein Blatt ist 1, eine Seite mit Kindern entsprechend mehr. */
function hoehe(knoten: PageNode): number {
  return 1 + Math.max(0, ...knoten.children.map(hoehe));
}

function finde(baum: PageNode[], id: number): PageNode | null {
  for (const knoten of baum) {
    if (knoten.id === id) return knoten;
    const treffer = finde(knoten.children, id);
    if (treffer !== null) return treffer;
  }
  return null;
}

export function MovePicker({
  seiteId,
  titel,
  aktuellerElternteil,
  aktuellerSpaceId,
  baum,
  spaces,
  maxTiefe,
  onWahl,
  onAbbruch,
}: Props) {
  const [filter, setFilter] = useState("");
  const [zielSpaceId, setZielSpaceId] = useState(aktuellerSpaceId);
  const [fremderBaum, setFremderBaum] = useState<PageNode[] | null>(null);
  const [laedt, setLaedt] = useState(false);
  const eingabeRef = useRef<HTMLInputElement>(null);

  useEffect(() => eingabeRef.current?.focus(), []);

  // Als Ziel taugt nur ein Bereich, in den auch geschrieben werden darf — der
  // aktuelle zählt immer mit, sonst verschwände er selbst aus der Auswahl.
  //
  // In einen *anderen* Bereich zu verschieben heißt, die Seite aus dem
  // bisherigen wegzuschaffen; das Backend verlangt dafür `loeschen` im
  // Quellbereich. Wer nur schreiben darf, hängt seine Seite also innerhalb des
  // eigenen Bereichs um — und bekommt gar nicht erst eine Auswahl gezeigt.
  const darfWegschaffen = hatRecht(
    spaces.find((s) => s.id === aktuellerSpaceId) ?? null,
    "loeschen",
  );
  const zielBereiche = spaces.filter(
    (s) => s.id === aktuellerSpaceId || (darfWegschaffen && hatRecht(s, "schreiben")),
  );

  const imEigenenBereich = zielSpaceId === aktuellerSpaceId;

  // Den Baum eines anderen Bereichs kennt der Aufrufer nicht — er lädt immer
  // nur den gerade geöffneten.
  useEffect(() => {
    if (imEigenenBereich) {
      setFremderBaum(null);
      return;
    }
    const key = spaces.find((s) => s.id === zielSpaceId)?.key;
    if (key === undefined) return;
    let abgebrochen = false;
    setLaedt(true);
    void getSpaceTree(key)
      .then((geholt) => !abgebrochen && setFremderBaum(geholt))
      .catch(() => !abgebrochen && setFremderBaum([]))
      .finally(() => !abgebrochen && setLaedt(false));
    return () => {
      abgebrochen = true;
    };
  }, [zielSpaceId, imEigenenBereich, spaces]);

  const ziele = useMemo(() => {
    const zielBaum = imEigenenBereich ? baum : (fremderBaum ?? []);
    // Die Höhe des Astes steht im eigenen Bereich, egal wohin er soll.
    const eigen = finde(baum, seiteId);
    const astHoehe = eigen === null ? 1 : hoehe(eigen);
    const gefiltert = filtereBaum(zielBaum, filter);
    const liste: Ziel[] = [];

    // Die oberste Ebene taucht beim Filtern nicht auf — sie hat keinen Titel.
    if (filter.trim() === "") {
      liste.push({
        id: null,
        titel: "Oberste Ebene",
        ebene: 0,
        gesperrt: astHoehe > maxTiefe ? `Der Ast ist ${astHoehe} Ebenen hoch` : null,
        aktuell: imEigenenBereich && aktuellerElternteil === null,
      });
    }

    const gehe = (knoten: PageNode[], ebene: number, inEigenemAst: boolean) => {
      for (const eintrag of knoten) {
        // Im fremden Bereich kann die Seite selbst gar nicht vorkommen.
        const selbst = imEigenenBereich && eintrag.id === seiteId;
        const gesperrtImAst = inEigenemAst || selbst;
        // Das Ziel liegt auf `ebene`, die Seite käme eine darunter.
        const zuTief = ebene + 1 + astHoehe - 1 > maxTiefe;
        liste.push({
          id: eintrag.id,
          titel: eintrag.title,
          ebene,
          gesperrt: selbst
            ? "Das ist die Seite selbst"
            : gesperrtImAst
              ? "Liegt unterhalb dieser Seite"
              : zuTief
                ? `Zu tief — höchstens ${maxTiefe} Ebenen`
                : null,
          aktuell: imEigenenBereich && eintrag.id === aktuellerElternteil,
        });
        gehe(eintrag.children, ebene + 1, gesperrtImAst);
      }
    };
    gehe(gefiltert, 1, false);
    return liste;
  }, [baum, fremderBaum, imEigenenBereich, filter, seiteId, aktuellerElternteil, maxTiefe]);

  const waehlbar = ziele.filter((z) => z.gesperrt === null && !z.aktuell).length;

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center bg-black/50 p-4 pt-16">
      <button className="fixed inset-0" onClick={onAbbruch} aria-label="Abbrechen" />
      <div className="relative flex max-h-[80vh] w-full max-w-lg flex-col rounded-lg border border-border bg-card shadow-card">
        <div className="border-b border-border p-3">
          <div className="flex items-start justify-between gap-2">
            <p className="text-sm">
              „<span className="font-medium">{titel}</span>" verschieben — mit allen Unterseiten
            </p>
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
          <label className="mt-2 flex items-center gap-2 text-xs text-text-secondary">
            Bereich
            <select
              value={zielSpaceId}
              onChange={(e) => {
                setZielSpaceId(Number(e.target.value));
                setFilter("");
              }}
              className="min-w-0 flex-1 rounded-lg border border-border bg-background px-2 py-1 text-sm text-text focus:border-primary focus:outline-none"
            >
              {zielBereiche.map((bereich) => (
                <option key={bereich.id} value={bereich.id}>
                  {bereich.name}
                  {bereich.id === aktuellerSpaceId ? " (aktuell)" : ""}
                </option>
              ))}
            </select>
          </label>

          <div className="relative mt-2">
            <Search className="pointer-events-none absolute top-1/2 left-3 h-4 w-4 -translate-y-1/2 text-text-secondary" />
            <input
              ref={eingabeRef}
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              onKeyDown={(e) => e.key === "Escape" && onAbbruch()}
              placeholder="Zielseite suchen …"
              aria-label="Zielseite suchen"
              className="w-full rounded-lg border border-border bg-background py-2 pr-3 pl-9 text-sm focus:border-primary focus:outline-none"
            />
          </div>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto py-1">
          {laedt && (
            <p className="flex items-center gap-2 px-3 py-3 text-sm text-text-secondary">
              <Loader2 className="h-4 w-4 animate-spin" /> Lade Bereich …
            </p>
          )}
          {!laedt && ziele.length === 0 && (
            <p className="px-3 py-3 text-sm text-text-secondary">
              {filter.trim() === ""
                ? "Dieser Bereich hat noch keine Seiten."
                : "Kein Titel passt dazu."}
            </p>
          )}
          {ziele.map((ziel) => (
            <button
              key={ziel.id ?? "wurzel"}
              type="button"
              disabled={ziel.gesperrt !== null || ziel.aktuell}
              onClick={() => onWahl(zielSpaceId, ziel.id)}
              style={{ paddingLeft: `${0.75 + ziel.ebene * 0.85}rem` }}
              className={cn(
                "flex w-full items-center gap-2 py-1.5 pr-3 text-left text-sm transition",
                ziel.gesperrt !== null || ziel.aktuell
                  ? "cursor-not-allowed text-text-secondary opacity-50"
                  : "hover:bg-background",
              )}
            >
              {ziel.id === null ? (
                <CornerLeftUp className="h-3.5 w-3.5 shrink-0" />
              ) : (
                <FileText className="h-3.5 w-3.5 shrink-0" />
              )}
              <span className="min-w-0 truncate">{ziel.titel}</span>
              {(ziel.aktuell || ziel.gesperrt !== null) && (
                <span className="ml-auto shrink-0 pl-2 text-xs">
                  {ziel.aktuell ? "aktuell" : ziel.gesperrt}
                </span>
              )}
            </button>
          ))}
        </div>

        {!laedt && waehlbar === 0 && ziele.length > 0 && (
          <p className="border-t border-border px-3 py-2 text-xs text-text-secondary">
            Kein Ziel wählbar — der Ast ist zu hoch oder es gibt nur diese eine Stelle.
          </p>
        )}
      </div>
    </div>
  );
}
