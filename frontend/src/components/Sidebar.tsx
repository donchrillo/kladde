/**
 * Linkes Menü: Bereichsauswahl oben, Seitenbaum darunter.
 *
 * Auf kleinen Bildschirmen als Overlay.
 */

import {
  BookOpen,
  FolderPlus,
  Home,
  Lock,
  LogOut,
  Moon,
  Plus,
  Search,
  Settings,
  Sun,
  Trash2,
  X,
} from "lucide-react";
import { useMemo, useState } from "react";

import type { PageNode, Space } from "../lib/api-client";
import { useAuth } from "../lib/auth";
import { navigiere, pfadZuKonto, pfadZuVerwaltung } from "../lib/route";
import { useTheme } from "../lib/theme";
import { cn, hatRecht } from "../lib/utils";
import { WIKI_NAME } from "../lib/wikiName";
import type { LoadState } from "../hooks/useWiki";
import { PageTree, filtereBaum } from "./PageTree";

interface Props {
  spaces: Space[];
  aktiverKey: string | null;
  onSpaceWaehlen: (key: string) => void;
  onBereichAnlegen: () => void;
  onBereichLoeschen: (key: string) => void;
  onStartseite: () => void;
  baum: PageNode[];
  baumState: LoadState;
  aktiveSeiteId: number | null;
  onSeiteWaehlen: (id: number) => void;
  /** `null` als Elternteil heißt: neue Seite auf oberster Ebene. */
  onSeiteAnlegen: (parentId: number | null) => void;
  /** Seite an eine neue Stelle (ab 0) unter ihren Geschwistern setzen. */
  onSeiteUmsortieren: (id: number, stelle: number) => void;
  /** Ebenen, unter denen keine Unterseite mehr erlaubt ist. */
  maxTiefe: number;
  /** Aufgeklappte Äste — liegt in `App`, weil es die Sidebar zweimal gibt. */
  offen: Set<number>;
  onUmschalten: (id: number) => void;
}

export function Sidebar({
  spaces,
  aktiverKey,
  onSpaceWaehlen,
  onBereichAnlegen,
  onBereichLoeschen,
  onStartseite,
  baum,
  baumState,
  aktiveSeiteId,
  onSeiteWaehlen,
  onSeiteAnlegen,
  onSeiteUmsortieren,
  maxTiefe,
  offen,
  onUmschalten,
}: Props) {
  const { theme, toggleTheme } = useTheme();
  const { ich } = useAuth();
  const darfBereicheAnlegen = ich === null || ich.ist_offener_betrieb || ich.is_admin || ich.darf_bereiche_anlegen;
  const aktiverSpace = spaces.find((s) => s.key === aktiverKey) ?? null;
  const darfSeitenAnlegen = hatRecht(aktiverSpace, "schreiben");
  // Filtert nur den Baum des aktuellen Bereichs — die Volltextsuche über das
  // ganze Wiki sitzt in der Kopfzeile.
  const [filter, setFilter] = useState("");
  const gefiltert = useMemo(() => filtereBaum(baum, filter), [baum, filter]);
  const filtertGerade = filter.trim() !== "";

  return (
    <aside className="flex h-full w-72 flex-col border-r border-border bg-card">
      <div className="flex items-center justify-between border-b border-border px-4 py-3">
        <h1 className="font-semibold">{WIKI_NAME}</h1>
        <button
          type="button"
          onClick={toggleTheme}
          title={theme === "dark" ? "Helles Design" : "Dunkles Design"}
          aria-label="Design umschalten"
          className="rounded-md p-1.5 text-text-secondary transition hover:bg-background hover:text-text"
        >
          {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
        </button>
      </div>

      <div className="px-2 pt-2">
        <button
          type="button"
          onClick={onStartseite}
          className="flex w-full items-center gap-2 rounded-lg px-2 py-2 text-left text-sm text-text-secondary transition hover:bg-background"
        >
          <Home className="h-4 w-4 shrink-0" />
          Startseite
        </button>
      </div>

      {/* Bereiche */}
      <nav className="border-b border-border px-2 py-2">
        <div className="flex items-center justify-between px-2 pb-1">
          <p className="text-xs font-medium tracking-wide text-text-secondary uppercase">
            Bereiche
          </p>
          {darfBereicheAnlegen && (
            <button
              type="button"
              onClick={onBereichAnlegen}
              title="Neuen Bereich anlegen"
              aria-label="Neuen Bereich anlegen"
              className="rounded p-1 text-text-secondary transition hover:bg-background hover:text-text"
            >
              <FolderPlus className="h-4 w-4" />
            </button>
          )}
        </div>
        {spaces.length === 0 ? (
          <p className="px-2 py-1 text-sm text-text-secondary">Noch keiner angelegt.</p>
        ) : (
          spaces.map((space) => (
            <div
              key={space.id}
              className={cn(
                "group mb-0.5 flex items-center rounded-lg transition",
                space.key === aktiverKey ? "bg-primary-light" : "hover:bg-background",
              )}
            >
              <button
                type="button"
                onClick={() => onSpaceWaehlen(space.key)}
                className={cn(
                  "flex min-w-0 flex-1 items-center gap-2 px-2 py-2 text-left text-sm",
                  space.key === aktiverKey ? "font-medium text-text" : "text-text-secondary",
                )}
              >
                <BookOpen className="h-4 w-4 shrink-0" />
                <span className="min-w-0 truncate">{space.name}</span>
                {space.is_private && (
                  <Lock
                    className="h-3 w-3 shrink-0 text-text-secondary"
                    aria-label="Privater Bereich"
                  />
                )}
              </button>
              <button
                type="button"
                onClick={() => onBereichLoeschen(space.key)}
                title={`Bereich „${space.name}" löschen`}
                aria-label={`Bereich ${space.name} löschen`}
                className="mr-1 shrink-0 rounded p-1 text-text-secondary opacity-0 transition group-hover:opacity-100 hover:text-danger focus:opacity-100"
              >
                <Trash2 className="h-3.5 w-3.5" />
              </button>
            </div>
          ))
        )}
      </nav>

      {/* Seitenbaum des gewählten Bereichs */}
      <div className="flex-1 overflow-y-auto px-2 py-2">
        <div className="flex items-center justify-between px-2 pb-1">
          <p className="text-xs font-medium tracking-wide text-text-secondary uppercase">Seiten</p>
          {aktiverKey !== null && darfSeitenAnlegen && (
            <button
              type="button"
              onClick={() => onSeiteAnlegen(null)}
              title="Neue Seite auf oberster Ebene"
              aria-label="Neue Seite auf oberster Ebene"
              className="rounded p-1 text-text-secondary transition hover:bg-background hover:text-text"
            >
              <Plus className="h-4 w-4" />
            </button>
          )}
        </div>

        {aktiverKey !== null && baumState === "ready" && baum.length > 0 && (
          <div className="relative mb-1 px-1">
            <Search className="pointer-events-none absolute top-1/2 left-3 h-3.5 w-3.5 -translate-y-1/2 text-text-secondary" />
            <input
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              onKeyDown={(e) => e.key === "Escape" && setFilter("")}
              placeholder="Nach Titel suchen"
              aria-label="Seitenbaum nach Titel filtern"
              className="w-full rounded-lg border border-border bg-background py-1 pr-7 pl-8 text-sm focus:border-primary focus:outline-none"
            />
            {filtertGerade && (
              <button
                type="button"
                onClick={() => setFilter("")}
                title="Filter zurücksetzen"
                aria-label="Filter zurücksetzen"
                className="absolute top-1/2 right-2 -translate-y-1/2 rounded p-0.5 text-text-secondary transition hover:text-text"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            )}
          </div>
        )}

        {baumState === "loading" && (
          <p className="px-2 py-1 text-sm text-text-secondary">Lade Baum …</p>
        )}
        {baumState === "error" && (
          <p className="px-2 py-1 text-sm text-danger">Seitenbaum nicht ladbar.</p>
        )}
        {baumState === "ready" &&
          (baum.length === 0 ? (
            <p className="px-2 py-1 text-sm text-text-secondary">
              Dieser Bereich hat noch keine Seiten.
            </p>
          ) : gefiltert.length === 0 ? (
            <p className="px-2 py-1 text-sm text-text-secondary">Kein Titel passt dazu.</p>
          ) : (
            <PageTree
              knoten={gefiltert}
              aktiveId={aktiveSeiteId}
              onAuswahl={onSeiteWaehlen}
              onUnterseite={darfSeitenAnlegen ? onSeiteAnlegen : undefined}
              onUmsortieren={
                darfSeitenAnlegen && !filtertGerade ? onSeiteUmsortieren : undefined
              }
              maxTiefe={maxTiefe}
              offen={offen}
              onUmschalten={onUmschalten}
              allesOffen={filtertGerade}
            />
          ))}
      </div>

      <Fusszeile />
    </aside>
  );
}

/**
 * Fußzeile: wer angemeldet ist, Verwaltung und Abmelden.
 *
 * Im offenen Betrieb (`AUTH_ENABLED=false`) gibt es niemanden zum Abmelden —
 * dann steht dort nur der bisherige Hinweis.
 */
function Fusszeile() {
  const { ich, abmelden } = useAuth();

  if (ich === null || ich.ist_offener_betrieb) {
    return (
      <p className="border-t border-border px-4 py-2 text-xs text-text-secondary">
        Internes Wiki · ohne Anmeldung im LAN
      </p>
    );
  }

  return (
    <div className="flex items-center gap-1 border-t border-border px-3 py-2">
      <button
        type="button"
        onClick={() => navigiere(pfadZuKonto())}
        title={`Konto: ${ich.username}`}
        aria-label="Eigenes Konto"
        className="min-w-0 flex-1 truncate rounded-lg px-1.5 py-1 text-left text-xs text-text-secondary transition hover:bg-background hover:text-text"
      >
        {ich.display_name}
      </button>
      {ich.is_admin && (
        <button
          type="button"
          onClick={() => navigiere(pfadZuVerwaltung())}
          title="Benutzer und Freigaben"
          aria-label="Verwaltung"
          className="rounded-lg p-1.5 text-text-secondary transition hover:bg-background hover:text-text"
        >
          <Settings className="h-4 w-4" />
        </button>
      )}
      <button
        type="button"
        onClick={() => void abmelden()}
        title="Abmelden"
        aria-label="Abmelden"
        className="rounded-lg p-1.5 text-text-secondary transition hover:bg-background hover:text-text"
      >
        <LogOut className="h-4 w-4" />
      </button>
    </div>
  );
}
