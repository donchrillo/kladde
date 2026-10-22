/**
 * Merkt sich, welche Äste des Seitenbaums aufgeklappt sind.
 *
 * Voreinstellung ist zugeklappt — bei vielen Seiten wird der Baum sonst
 * unübersichtlich. Offen ist immer mindestens der Ast bis zur aktuellen Seite,
 * damit ein Deep-Link nicht in einem scheinbar leeren Baum landet.
 */

import { useCallback, useEffect, useState } from "react";

import type { PageNode } from "../lib/api-client";

/** Ein Eintrag je Bereich: `{ "it": [3, 7] }`. */
const SCHLUESSEL = "kladde-baum-offen";

function alleGemerkt(): Record<string, number[]> {
  try {
    const roh = window.localStorage.getItem(SCHLUESSEL);
    return roh === null ? {} : (JSON.parse(roh) as Record<string, number[]>);
  } catch {
    // Kaputter oder gesperrter Speicher darf den Baum nicht lahmlegen.
    return {};
  }
}

function gemerkt(spaceKey: string | null): Set<number> {
  if (spaceKey === null) return new Set();
  return new Set(alleGemerkt()[spaceKey] ?? []);
}

function merken(spaceKey: string, offen: Set<number>) {
  try {
    window.localStorage.setItem(
      SCHLUESSEL,
      JSON.stringify({ ...alleGemerkt(), [spaceKey]: [...offen] }),
    );
  } catch {
    // Ohne Speicher funktioniert alles weiter, nur ohne Gedächtnis.
  }
}

/** Ids aller Seiten von der Wurzel bis einschließlich `id`. */
export function pfadIds(baum: PageNode[], id: number): number[] {
  const kette: number[] = [];

  const suche = (knoten: PageNode[]): boolean => {
    for (const eintrag of knoten) {
      kette.push(eintrag.id);
      if (eintrag.id === id || suche(eintrag.children)) return true;
      kette.pop();
    }
    return false;
  };

  suche(baum);
  return kette;
}

export function useBaumOffen(
  spaceKey: string | null,
  baum: PageNode[],
  aktiveSeiteId: number | null,
) {
  // Der Bereichsschlüssel wird mitgeführt, damit der gemerkte Zustand beim
  // Wechsel noch im selben Rendern nachgezogen wird — ein Effekt würde erst
  // einen Frame lang den Baum des alten Bereichs zeigen.
  const [zustand, setZustand] = useState(() => ({ key: spaceKey, offen: gemerkt(spaceKey) }));
  if (zustand.key !== spaceKey) {
    setZustand({ key: spaceKey, offen: gemerkt(spaceKey) });
  }

  // Den Ast bis zur aktuellen Seite aufklappen.
  useEffect(() => {
    if (aktiveSeiteId === null) return;
    const vorfahren = pfadIds(baum, aktiveSeiteId);
    if (vorfahren.length === 0) return;
    setZustand((bisher) => {
      if (vorfahren.every((id) => bisher.offen.has(id))) return bisher;
      return { ...bisher, offen: new Set([...bisher.offen, ...vorfahren]) };
    });
  }, [baum, aktiveSeiteId]);

  // Zustand sichern. Beim Bereichswechsel ist `zustand` schon der frisch
  // geladene Stand, hier wird also nie der gemerkte Stand überschrieben.
  useEffect(() => {
    if (zustand.key !== null) merken(zustand.key, zustand.offen);
  }, [zustand]);

  const umschalten = useCallback((id: number) => {
    setZustand((bisher) => {
      const offen = new Set(bisher.offen);
      if (!offen.delete(id)) offen.add(id);
      return { ...bisher, offen };
    });
  }, []);

  return { offen: zustand.offen, umschalten };
}
