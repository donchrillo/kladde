import { ArrowDown, ArrowUp, ChevronDown, ChevronRight, FileText, Plus } from "lucide-react";

import type { PageNode } from "../lib/api-client";
import { cn } from "../lib/utils";

interface Props {
  knoten: PageNode[];
  aktiveId: number | null;
  onAuswahl: (id: number) => void;
  /** `undefined`, wenn im aktuellen Bereich niemand Unterseiten anlegen darf. */
  onUnterseite: ((parentId: number) => void) | undefined;
  /**
   * Setzt eine Seite an eine neue Stelle (ab 0) unter ihren Geschwistern.
   * `undefined`, wenn niemand umsortieren darf — oder beim Filtern: dann fehlen
   * Geschwister, und die Stelle in der sichtbaren Liste stimmt nicht.
   */
  onUmsortieren: ((id: number, stelle: number) => void) | undefined;
  /** Ab dieser Ebene gibt es keinen Knopf für Unterseiten mehr. */
  maxTiefe: number;
  /** Ids der aufgeklappten Knoten. */
  offen: Set<number>;
  onUmschalten: (id: number) => void;
  /**
   * Beim Filtern ist alles aufgeklappt — sonst verschwänden Treffer hinter
   * zugeklappten Eltern.
   */
  allesOffen?: boolean;
  /** Einrückungstiefe; wird beim Rekursionsschritt hochgezählt. */
  tiefe?: number;
}

/** Erscheint erst beim Überfahren der Zeile, wie der Knopf für Unterseiten. */
const knopfKlasse =
  "shrink-0 rounded p-1 text-text-secondary opacity-0 transition group-hover:opacity-100 hover:text-text focus:opacity-100 disabled:invisible";

/** Rekursiver Seitenbaum. Die Verschachtelung kommt fertig vom Backend. */
export function PageTree({
  knoten,
  aktiveId,
  onAuswahl,
  onUnterseite,
  onUmsortieren,
  maxTiefe,
  offen,
  onUmschalten,
  allesOffen = false,
  tiefe = 1,
}: Props) {
  return (
    <ul className="flex flex-col gap-0.5">
      {knoten.map((seite, stelle) => {
        const hatKinder = seite.children.length > 0;
        const aufgeklappt = hatKinder && (allesOffen || offen.has(seite.id));

        return (
          <li key={seite.id}>
            <div
              style={{ paddingLeft: `${(tiefe - 1) * 0.75}rem` }}
              className={cn(
                "group flex items-center rounded-lg transition",
                seite.id === aktiveId ? "bg-primary-light" : "hover:bg-background",
              )}
            >
              {hatKinder ? (
                <button
                  type="button"
                  onClick={() => onUmschalten(seite.id)}
                  title={aufgeklappt ? "Zuklappen" : "Aufklappen"}
                  aria-label={`${seite.title} ${aufgeklappt ? "zuklappen" : "aufklappen"}`}
                  aria-expanded={aufgeklappt}
                  className="shrink-0 rounded p-1 text-text-secondary transition hover:text-text"
                >
                  {aufgeklappt ? (
                    <ChevronDown className="h-3.5 w-3.5" />
                  ) : (
                    <ChevronRight className="h-3.5 w-3.5" />
                  )}
                </button>
              ) : (
                // Gleich breiter Platzhalter, damit Blätter nicht ausscheren.
                <span className="w-[1.375rem] shrink-0" />
              )}

              <button
                type="button"
                onClick={() => onAuswahl(seite.id)}
                className={cn(
                  "flex min-w-0 flex-1 items-center gap-2 py-1.5 text-left text-sm",
                  seite.id === aktiveId ? "font-medium text-text" : "text-text-secondary",
                )}
              >
                <FileText className="h-3.5 w-3.5 shrink-0" />
                <span className="min-w-0 truncate">{seite.title}</span>
              </button>

              {onUmsortieren !== undefined && knoten.length > 1 && (
                <>
                  <button
                    type="button"
                    onClick={() => onUmsortieren(seite.id, stelle - 1)}
                    disabled={stelle === 0}
                    title="Nach oben"
                    aria-label={`${seite.title} nach oben`}
                    className={knopfKlasse}
                  >
                    <ArrowUp className="h-3.5 w-3.5" />
                  </button>
                  <button
                    type="button"
                    onClick={() => onUmsortieren(seite.id, stelle + 1)}
                    disabled={stelle === knoten.length - 1}
                    title="Nach unten"
                    aria-label={`${seite.title} nach unten`}
                    className={knopfKlasse}
                  >
                    <ArrowDown className="h-3.5 w-3.5" />
                  </button>
                </>
              )}

              {tiefe < maxTiefe && onUnterseite !== undefined && (
                <button
                  type="button"
                  onClick={() => onUnterseite(seite.id)}
                  title={`Unterseite zu „${seite.title}" anlegen`}
                  aria-label={`Unterseite zu ${seite.title} anlegen`}
                  className="mr-1 shrink-0 rounded p-1 text-text-secondary opacity-0 transition group-hover:opacity-100 hover:text-text focus:opacity-100"
                >
                  <Plus className="h-3.5 w-3.5" />
                </button>
              )}
            </div>

            {aufgeklappt && (
              <PageTree
                knoten={seite.children}
                aktiveId={aktiveId}
                onAuswahl={onAuswahl}
                onUnterseite={onUnterseite}
                onUmsortieren={onUmsortieren}
                maxTiefe={maxTiefe}
                offen={offen}
                onUmschalten={onUmschalten}
                allesOffen={allesOffen}
                tiefe={tiefe + 1}
              />
            )}
          </li>
        );
      })}
    </ul>
  );
}

/**
 * Baum auf einen Suchbegriff eindampfen.
 *
 * Ein Knoten bleibt, wenn sein Titel passt **oder** ein Nachkomme passt — sonst
 * verlöre ein Treffer seinen Elternpfad und stünde ohne Zusammenhang da.
 */
export function filtereBaum(knoten: PageNode[], begriff: string): PageNode[] {
  const gesucht = begriff.trim().toLowerCase();
  if (gesucht === "") return knoten;

  const durchgehen = (liste: PageNode[]): PageNode[] =>
    liste.flatMap((seite) => {
      const kinder = durchgehen(seite.children);
      const selbst = seite.title.toLowerCase().includes(gesucht);
      if (!selbst && kinder.length === 0) return [];
      // Passt der Knoten selbst, bleiben seine Kinder vollständig sichtbar.
      return [{ ...seite, children: selbst ? seite.children : kinder }];
    });

  return durchgehen(knoten);
}
