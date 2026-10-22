/**
 * Eine CSS-Medienabfrage als React-Wert.
 *
 * Gebraucht, wo eine Entscheidung nicht per CSS zu treffen ist: das
 * Inhaltsverzeichnis soll je nach Breite an einer anderen Stelle stehen — und
 * nur einmal im Dokument, sonst laufen zwei Beobachter und Sprungmarken doppelt.
 */

import { useMemo, useSyncExternalStore } from "react";

export function useMedienAbfrage(abfrage: string): boolean {
  const liste = useMemo(() => window.matchMedia(abfrage), [abfrage]);

  return useSyncExternalStore(
    (benachrichtigen) => {
      liste.addEventListener("change", benachrichtigen);
      return () => liste.removeEventListener("change", benachrichtigen);
    },
    () => liste.matches,
  );
}
