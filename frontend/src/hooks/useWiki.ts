import { useCallback, useEffect, useRef, useState } from "react";

import {
  ApiError,
  getPage,
  getSpaceTree,
  listSpaces,
  type Page,
  type PageNode,
  type Space,
} from "../lib/api-client";

export type LoadState = "loading" | "ready" | "error";

/**
 * Ist der Fehler ein "bitte anmelden"?
 *
 * Ein 401 ist kein Ladefehler: der Auth-Context zeigt daraufhin die
 * Anmeldemaske. Würde der Ladezustand hier auf "error" fallen, stünde nach
 * der Anmeldung „Backend nicht erreichbar" auf dem Schirm, obwohl nur die
 * Sitzung fehlte.
 */
function istAnmeldefehler(e: unknown): boolean {
  return e instanceof ApiError && e.status === 401;
}

/**
 * Lädt die Bereichsliste und hält den gewählten Bereich.
 *
 * `aktiv` ist der Anmeldezustand: solange niemand angemeldet ist, wird gar
 * nicht erst geladen. Springt es auf `true` (nach der Anmeldung), lädt der
 * Hook von selbst nach — ohne Neuladen der Seite.
 */
export function useSpaces(aktiv = true) {
  const [spaces, setSpaces] = useState<Space[]>([]);
  const [aktiverKey, setAktiverKey] = useState<string | null>(null);
  const [state, setState] = useState<LoadState>("loading");
  // Läuft bei jedem `refresh` hoch — schützt davor, dass eine veraltete, spät
  // eintreffende Antwort eine neuere überschreibt (siehe SearchBox.tsx).
  const lauf = useRef(0);

  const refresh = useCallback(async () => {
    const meiner = ++lauf.current;
    if (!aktiv) {
      setSpaces([]);
      setState("loading");
      return;
    }
    try {
      const geladen = await listSpaces();
      if (meiner !== lauf.current) return;
      setSpaces(geladen);
      // Ohne Auswahl — oder wenn der gewählte Bereich weg ist — den ersten zeigen.
      setAktiverKey((bisher) =>
        bisher !== null && geladen.some((s) => s.key === bisher)
          ? bisher
          : (geladen[0]?.key ?? null),
      );
      setState("ready");
    } catch (e) {
      if (meiner !== lauf.current) return;
      setState(istAnmeldefehler(e) ? "loading" : "error");
    }
  }, [aktiv]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return { spaces, aktiverKey, setAktiverKey, state, refresh };
}

/** Lädt den Seitenbaum des Bereichs; `null` als Key heißt: nichts zu laden. */
export function useSeitenbaum(spaceKey: string | null) {
  const [baum, setBaum] = useState<PageNode[]>([]);
  const [state, setState] = useState<LoadState>("loading");
  const lauf = useRef(0);

  const refresh = useCallback(async () => {
    const meiner = ++lauf.current;
    if (spaceKey === null) {
      setBaum([]);
      setState("ready");
      return;
    }
    try {
      const geladen = await getSpaceTree(spaceKey);
      if (meiner !== lauf.current) return;
      setBaum(geladen);
      setState("ready");
    } catch (e) {
      if (meiner !== lauf.current) return;
      setState(istAnmeldefehler(e) ? "loading" : "error");
    }
  }, [spaceKey]);

  useEffect(() => {
    setState("loading");
    void refresh();
  }, [refresh]);

  return { baum, state, refresh };
}

/** Lädt den vollen Inhalt der gewählten Seite. */
export function useSeite(pageId: number | null) {
  const [seite, setSeite] = useState<Page | null>(null);
  const [state, setState] = useState<LoadState>("ready");
  const lauf = useRef(0);

  const refresh = useCallback(async () => {
    const meiner = ++lauf.current;
    if (pageId === null) {
      setSeite(null);
      setState("ready");
      return;
    }
    try {
      const geladen = await getPage(pageId);
      if (meiner !== lauf.current) return;
      setSeite(geladen);
      setState("ready");
    } catch (e) {
      if (meiner !== lauf.current) return;
      setState(istAnmeldefehler(e) ? "loading" : "error");
    }
  }, [pageId]);

  useEffect(() => {
    if (pageId !== null) setState("loading");
    void refresh();
  }, [pageId, refresh]);

  return { seite, state, refresh };
}
