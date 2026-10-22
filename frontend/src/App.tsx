import { Home, Menu, X } from "lucide-react";
import { useEffect, useState } from "react";

import { KontoPage } from "./components/KontoPage";
import { LoginMaske } from "./components/LoginMaske";
import { PageView } from "./components/PageView";
import { SearchBox } from "./components/SearchBox";
import { Sidebar } from "./components/Sidebar";
import { LabelPage, StartPage } from "./components/StartPage";
import { VerwaltungPage } from "./components/VerwaltungPage";
import { useBaumOffen } from "./hooks/useBaumOffen";
import { useSeite, useSeitenbaum, useSpaces } from "./hooks/useWiki";
import {
  createPage,
  createSpace,
  deleteSpace,
  getSpaceTree,
  updatePage,
  type Page,
  type PageNode,
} from "./lib/api-client";
import { useAuth } from "./lib/auth";
import { navigiere, pfadZuBereich, pfadZuSeite, useRoute } from "./lib/route";
import { cn } from "./lib/utils";
import { WIKI_NAME } from "./lib/wikiName";

/** Muss zu MAX_TIEFE in backend/src/routers/pages.py passen. */
const MAX_TIEFE = 5;

/**
 * Anmelde-Schleuse vor dem eigentlichen Wiki.
 *
 * Bewusst eine eigene Komponente: früher stand die Fallunterscheidung als
 * vorgezogenes `return` mitten in `Wiki`. Die Hooks darüber liefen dann beim
 * Abmelden weiter, und ihr Inhalt — Bereichsliste, Seitenbaum, offene Seite —
 * überlebte den Benutzerwechsel. Wer sich abmeldete und als jemand anders
 * anmeldete, sah bis zum nächsten F5 die Bereiche des Vorgängers.
 *
 * So wird `Wiki` beim Abmelden ausgehängt und startet leer. Das `key` deckt
 * den Rest ab: wechselt die Kennung ohne Zwischenschritt über die Maske (etwa
 * weil ein 401 die Sitzung beendet und gleich die nächste beginnt), baut React
 * den Teilbaum trotzdem neu auf.
 */
export default function App() {
  const { ich, state: authState } = useAuth();

  // Solange der Anmeldezustand unklar ist, lieber nichts zeigen als kurz den
  // falschen Zustand — sonst blitzt bei jedem Laden die Maske auf.
  if (authState === "laedt") return <div className="h-full bg-background" />;
  if (authState === "anonym") return <LoginMaske />;
  return <Wiki key={ich?.id ?? "offen"} />;
}

function Wiki() {
  const route = useRoute();
  const { ich, state: authState } = useAuth();
  // Erst laden, wenn der Anmeldezustand geklärt ist. Sonst läuft der Aufruf
  // auf einem frischen Rechner in einen 401 und der Ladezustand bliebe auf
  // "error" stehen — nach der Anmeldung stünde dann „Backend nicht erreichbar".
  const { spaces, state: spacesState, refresh: spacesNeuLaden } = useSpaces(
    authState === "angemeldet",
  );
  const [menuOffen, setMenuOffen] = useState(false);
  const [fehler, setFehler] = useState<string | null>(null);

  // Der Bereich ergibt sich aus der Adresse; ohne Angabe der erste vorhandene.
  const routeKey =
    route.art === "bereich" || route.art === "seite" ? route.spaceKey : null;
  const aktiverSpace =
    spaces.find((s) => s.key === routeKey) ??
    (route.art === "start" ||
    route.art === "schlagwort" ||
    route.art === "verwaltung" ||
    route.art === "konto"
      ? null
      : (spaces[0] ?? null));

  const { baum, state: baumState, refresh: baumNeuLaden } = useSeitenbaum(
    aktiverSpace?.key ?? null,
  );

  // Aus dem Slug in der Adresse die Seiten-Id im geladenen Baum auflösen.
  const aktiveSeiteId =
    route.art === "seite" ? (findeSlug(baum, route.slug)?.id ?? null) : null;
  const { seite, state: seiteState, refresh: seiteNeuLaden } = useSeite(aktiveSeiteId);
  const { offen, umschalten } = useBaumOffen(aktiverSpace?.key ?? null, baum, aktiveSeiteId);

  // Adresse zeigt auf einen Bereich, den es nicht gibt → zurück zur Startseite.
  useEffect(() => {
    if (spacesState !== "ready" || routeKey === null) return;
    if (!spaces.some((s) => s.key === routeKey)) navigiere("#/");
  }, [spacesState, spaces, routeKey]);

  const bereichAnlegen = async () => {
    const name = window.prompt("Name des neuen Bereichs")?.trim();
    if (!name) return;
    try {
      const neu = await createSpace({ name });
      await spacesNeuLaden();
      navigiere(pfadZuBereich(neu.key));
      setFehler(null);
    } catch (e) {
      setFehler(e instanceof Error ? e.message : "Bereich konnte nicht angelegt werden");
    }
  };

  /**
   * Bereich löschen — nur wenn er leer ist.
   *
   * Enthält er noch Seiten, wird gar nicht erst gefragt, sondern erklärt, was
   * zu tun ist. Dieselbe Regel gilt für eine Seite mit Unterseiten: gelöscht
   * wird immer nur, was nichts mehr unter sich hat.
   */
  const bereichLoeschen = async (key: string) => {
    const space = spaces.find((s) => s.key === key);
    if (space === undefined) return;

    // Den Baum eigens holen: `baum` gehört zum gerade geöffneten Bereich,
    // gelöscht wird aber oft ein anderer.
    let anzahl = 0;
    try {
      anzahl = zaehleSeiten(await getSpaceTree(key));
    } catch (e) {
      setFehler(e instanceof Error ? e.message : "Bereich nicht lesbar");
      return;
    }

    if (anzahl > 0) {
      setFehler(
        `Bereich „${space.name}" enthält noch ${anzahl} Seite${anzahl === 1 ? "" : "n"} — ` +
          "diese bitte erst löschen. Gelöscht wird von unten nach oben: eine Seite " +
          "mit Unterseiten bleibt geschützt, bis diese weg sind.",
      );
      return;
    }
    if (!window.confirm(`Bereich „${space.name}" löschen?`)) return;

    try {
      await deleteSpace(key);
      await spacesNeuLaden();
      navigiere("#/");
      setFehler(null);
    } catch (e) {
      setFehler(e instanceof Error ? e.message : "Bereich konnte nicht gelöscht werden");
    }
  };

  const seiteAnlegen = async (parentId: number | null) => {
    if (aktiverSpace === null) return;
    const titel = window
      .prompt(parentId === null ? "Titel der neuen Seite" : "Titel der neuen Unterseite")
      ?.trim();
    if (!titel) return;
    try {
      const neu = await createPage({
        space_id: aktiverSpace.id,
        title: titel,
        parent_id: parentId,
      });
      await baumNeuLaden();
      navigiere(pfadZuSeite(aktiverSpace.key, neu.slug));
      setMenuOffen(false);
      setFehler(null);
    } catch (e) {
      setFehler(e instanceof Error ? e.message : "Seite konnte nicht angelegt werden");
    }
  };

  const seiteUmsortieren = async (id: number, stelle: number) => {
    try {
      // Das Backend nummeriert die Geschwister dabei lückenlos neu.
      await updatePage(id, { position: stelle });
      await baumNeuLaden();
      setFehler(null);
    } catch (e) {
      setFehler(e instanceof Error ? e.message : "Reihenfolge konnte nicht geändert werden");
    }
  };

  const nachDemLoeschen = async () => {
    await baumNeuLaden();
    if (aktiverSpace !== null) navigiere(pfadZuBereich(aktiverSpace.key));
  };

  const nachDemSpeichern = async () => {
    await Promise.all([seiteNeuLaden(), baumNeuLaden()]);
  };

  /**
   * Nach dem Verschieben zur Seite an ihrem neuen Platz gehen.
   *
   * Bei einem Bereichswechsel ändern sich Bereich und womöglich der Slug — die
   * bisherige Adresse zeigt dann ins Leere.
   */
  const nachDemVerschieben = async (neu: Page) => {
    await nachDemSpeichern();
    const key = spaces.find((s) => s.id === neu.space_id)?.key;
    if (key !== undefined) navigiere(pfadZuSeite(key, neu.slug));
  };

  if (spacesState === "error") {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-4 bg-background p-6 text-text">
        <p className="text-center text-danger">
          Das Wiki ist gerade nicht erreichbar. Besteht die Netzverbindung?
        </p>
        <button
          type="button"
          onClick={() => void spacesNeuLaden()}
          className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-white transition hover:bg-primary-hover"
        >
          Erneut versuchen
        </button>
      </div>
    );
  }

  const menue = (
    <Sidebar
      spaces={spaces}
      aktiverKey={aktiverSpace?.key ?? null}
      onSpaceWaehlen={(key) => {
        navigiere(pfadZuBereich(key));
        setMenuOffen(false);
      }}
      onBereichAnlegen={() => void bereichAnlegen()}
      onBereichLoeschen={(key) => void bereichLoeschen(key)}
      onStartseite={() => {
        navigiere("#/");
        setMenuOffen(false);
      }}
      baum={baum}
      baumState={baumState}
      aktiveSeiteId={aktiveSeiteId}
      onSeiteWaehlen={(id) => {
        const knoten = findeId(baum, id);
        if (knoten !== null && aktiverSpace !== null) {
          navigiere(pfadZuSeite(aktiverSpace.key, knoten.slug));
        }
        setMenuOffen(false);
      }}
      onSeiteAnlegen={(parentId) => void seiteAnlegen(parentId)}
      onSeiteUmsortieren={(id, stelle) => void seiteUmsortieren(id, stelle)}
      maxTiefe={MAX_TIEFE}
      offen={offen}
      onUmschalten={umschalten}
    />
  );

  return (
    <div className="flex h-full overflow-hidden bg-background text-text">
      <div className="hidden lg:block">{menue}</div>

      {menuOffen && (
        <>
          <button
            className="fixed inset-0 z-40 bg-black/50 lg:hidden"
            onClick={() => setMenuOffen(false)}
            aria-label="Menü schließen"
          />
          <div className="fixed inset-y-0 left-0 z-50 lg:hidden">{menue}</div>
          <button
            onClick={() => setMenuOffen(false)}
            className="fixed top-3 right-3 z-50 rounded-full border border-border bg-card p-2 lg:hidden"
            aria-label="Menü schließen"
          >
            <X className="h-5 w-5" />
          </button>
        </>
      )}

      <main className="flex min-w-0 flex-1 flex-col">
        {/* Kopfzeile mit Suche — auf jeder Breite sichtbar. */}
        <div className="flex h-14 shrink-0 items-center gap-3 border-b border-border bg-card px-4">
          <button
            onClick={() => setMenuOffen(true)}
            className="rounded p-1.5 hover:bg-background lg:hidden"
            aria-label="Menü öffnen"
          >
            <Menu className="h-5 w-5" />
          </button>
          <button
            onClick={() => navigiere("#/")}
            title="Zur Startseite"
            aria-label="Zur Startseite"
            className="rounded p-1.5 text-text-secondary transition hover:bg-background hover:text-text"
          >
            <Home className="h-5 w-5" />
          </button>
          <SearchBox />
        </div>

        <div className="flex-1 overflow-y-auto">
          {/* Nur die Seitenansicht wird ab xl breiter — dort steht rechts das
              Inhaltsverzeichnis. Start- und Schlagwortseite bleiben schmal. */}
          <div
            className={cn(
              "mx-auto max-w-3xl px-4 py-6 sm:px-6 sm:py-8",
              route.art === "seite" && "xl:max-w-6xl",
            )}
          >
            {fehler !== null && (
              <p className="mb-4 rounded-lg border border-danger/40 bg-danger/10 px-3 py-2 text-sm text-danger">
                {fehler}
              </p>
            )}

            {route.art === "verwaltung" ? (
              <VerwaltungPage istAdmin={ich?.is_admin ?? false} />
            ) : route.art === "konto" ? (
              <KontoPage />
            ) : route.art === "schlagwort" ? (
              <LabelPage name={route.name} />
            ) : spacesState === "ready" && spaces.length === 0 ? (
              <LeererZustand onAnlegen={() => void bereichAnlegen()} />
            ) : route.art === "start" ? (
              <StartPage />
            ) : (
              <>
                {seiteState === "loading" && <p className="text-text-secondary">Lade Seite …</p>}
                {seiteState === "error" && <p className="text-danger">Seite nicht ladbar.</p>}
                {seiteState === "ready" && seite === null && (
                  <p className="text-text-secondary">
                    {route.art === "seite"
                      ? "Diese Seite gibt es nicht (mehr)."
                      : "Links eine Seite auswählen — oder über das Plus eine neue anlegen."}
                  </p>
                )}
                {seiteState === "ready" && seite !== null && (
                  <PageView
                    seite={seite}
                    space={aktiverSpace}
                    spaceName={aktiverSpace?.name ?? ""}
                    baum={baum}
                    spaces={spaces}
                    maxTiefe={MAX_TIEFE}
                    pfad={pfadZu(baum, seite.id, aktiverSpace?.name ?? "")}
                    onGespeichert={() => void nachDemSpeichern()}
                    onVerschoben={(neu) => void nachDemVerschieben(neu)}
                    onGeloescht={() => void nachDemLoeschen()}
                  />
                )}
              </>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}

/** Seiten im Baum zählen — für die Rückfrage vor dem Löschen eines Bereichs. */
function zaehleSeiten(baum: PageNode[]): number {
  return baum.reduce((summe, knoten) => summe + 1 + zaehleSeiten(knoten.children), 0);
}

function findeSlug(baum: PageNode[], slug: string): PageNode | null {
  for (const knoten of baum) {
    if (knoten.slug === slug) return knoten;
    const treffer = findeSlug(knoten.children, slug);
    if (treffer !== null) return treffer;
  }
  return null;
}

function findeId(baum: PageNode[], id: number): PageNode | null {
  for (const knoten of baum) {
    if (knoten.id === id) return knoten;
    const treffer = findeId(knoten.children, id);
    if (treffer !== null) return treffer;
  }
  return null;
}

/** Brotkrumen: Bereichsname, dann die Titel von der Wurzel bis zur Seite. */
function pfadZu(baum: PageNode[], id: number, bereichsname: string): string[] {
  const kette: string[] = [];

  const suche = (knoten: PageNode[]): boolean => {
    for (const eintrag of knoten) {
      kette.push(eintrag.title);
      if (eintrag.id === id || suche(eintrag.children)) return true;
      kette.pop();
    }
    return false;
  };

  suche(baum);
  return [bereichsname, ...kette];
}

/** Einstieg, solange noch kein Bereich existiert. */
function LeererZustand({ onAnlegen }: { onAnlegen: () => void }) {
  return (
    <div className="rounded-lg border border-border bg-card p-6 text-center shadow-card">
      <h2 className="text-lg font-semibold">Willkommen im {WIKI_NAME}</h2>
      <p className="mx-auto mt-2 max-w-md text-sm text-text-secondary">
        Bereiche sind die oberste Gliederung — zum Beispiel Versand, Büro, IT oder
        Programmieren. Innerhalb eines Bereichs entstehen Seiten und Unterseiten.
      </p>
      <button
        type="button"
        onClick={onAnlegen}
        className="mt-4 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-white transition hover:bg-primary-hover"
      >
        Ersten Bereich anlegen
      </button>
    </div>
  );
}
