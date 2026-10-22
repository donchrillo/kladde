import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

import type { Recht, Space } from "./api-client";

/** Klassen zusammenführen, spätere Tailwind-Klassen gewinnen. */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/** Rangfolge der Rechte — muss zur Reihenfolge im Backend passen. */
export const RANG: Record<Recht, number> = {
  lesen: 1,
  schreiben: 2,
  loeschen: 3,
  verwalten: 4,
};

/**
 * Hat der Benutzer im gegebenen Bereich mindestens das nötige Recht?
 *
 * Reine Oberflächen-Hilfe — blendet Bedienelemente ein/aus, die serverseitige
 * Prüfung bleibt davon unberührt. `space === null` (noch nichts geladen) gilt
 * als kein Recht.
 */
export function hatRecht(space: Space | null, noetig: Recht): boolean {
  if (space === null || space.mein_recht === null) return false;
  return RANG[space.mein_recht] >= RANG[noetig];
}
