/**
 * Zentraler Client fürs Backend.
 *
 * Same-origin: in Produktion liefert das Backend die PWA aus, im Dev proxyt
 * Vite `/api` ans Backend. Daher überall relative Pfade.
 */

const API = "/api";

export interface Space {
  id: number;
  key: string;
  name: string;
  description: string | null;
  created_at: string;
  owner_id: number | null;
  is_private: boolean;
  /**
   * Eigenes Recht in diesem Bereich — bestimmt, welche Bedienelemente greifen.
   *
   * `null` heißt "kein Recht" und kommt nur in der Verwaltungsliste vor: ein
   * Administrator sieht dort auch fremde Privatbereiche, in die er nicht hinein
   * darf. In `GET /api/spaces` steht immer mindestens `lesen`.
   */
  mein_recht: Recht | null;
}

/** Bereichsliste für die Verwaltung — mit Eigentümername und Seitenzahl. */
export interface SpaceAdmin extends Space {
  owner_name: string | null;
  seiten: number;
}

/** Knoten im Seitenbaum — ohne Inhalt, der wird pro Seite nachgeladen. */
export interface PageNode {
  id: number;
  parent_id: number | null;
  title: string;
  slug: string;
  position: number;
  children: PageNode[];
}

export interface Page {
  id: number;
  space_id: number;
  parent_id: number | null;
  title: string;
  slug: string;
  body: string;
  position: number;
  created_at: string;
  updated_at: string;
  labels: string[];
}

export interface PageVersionInfo {
  revision: number;
  title: string;
  author: string | null;
  created_at: string;
}

export interface Attachment {
  id: number;
  page_id: number;
  filename: string;
  content_type: string;
  size_bytes: number;
  uploaded_by: string | null;
  created_at: string;
}

export interface PageSummary {
  id: number;
  title: string;
  slug: string;
  space_id: number;
  space_key: string;
  space_name: string;
  updated_at: string;
}

export interface LabelCount {
  name: string;
  anzahl: number;
}

export interface DiffZeile {
  art: "gleich" | "plus" | "minus";
  text: string;
}

export interface VersionDiff {
  von_revision: number;
  nach_revision: number;
  zeilen: DiffZeile[];
}

export interface SearchHit {
  page_id: number;
  title: string;
  slug: string;
  space_id: number;
  space_key: string;
  space_name: string;
  excerpt: string;
}

/**
 * Fehlermeldung aus der Antwort ziehen.
 *
 * Das Backend liefert seine Meldungen auf Deutsch in `detail` — die sind für
 * den Benutzer brauchbarer als ein generisches "Fehler 400".
 */
async function fehlermeldung(res: Response, standard: string): Promise<string> {
  try {
    const daten = (await res.json()) as { detail?: unknown };
    if (typeof daten.detail === "string") return daten.detail;
  } catch {
    /* keine JSON-Antwort — dann bleibt es beim Standardtext */
  }
  return standard;
}

/** Fehler mit HTTP-Status, damit Aufrufer 401 von allem anderen trennen können. */
export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

/**
 * Wird bei jedem 401 gerufen — der Auth-Context hängt sich hier ein und zeigt
 * daraufhin die Anmeldemaske. So muss nicht jeder Aufrufer daran denken.
 */
let beiAbgemeldet: (() => void) | null = null;

export function setzeAbmeldeMelder(melder: (() => void) | null): void {
  beiAbgemeldet = melder;
}

async function scheitern(res: Response, standard: string): Promise<never> {
  const text = await fehlermeldung(res, standard);
  if (res.status === 401) beiAbgemeldet?.();
  throw new ApiError(text, res.status);
}

async function hole<T>(pfad: string, fehler: string): Promise<T> {
  const res = await fetch(`${API}${pfad}`, { credentials: "same-origin" });
  if (!res.ok) await scheitern(res, fehler);
  return res.json() as Promise<T>;
}

async function sende<T>(
  pfad: string,
  methode: "POST" | "PATCH" | "PUT" | "DELETE",
  koerper: unknown,
  fehler: string,
): Promise<T> {
  const res = await fetch(`${API}${pfad}`, {
    method: methode,
    credentials: "same-origin",
    headers: koerper === undefined ? {} : { "Content-Type": "application/json" },
    body: koerper === undefined ? undefined : JSON.stringify(koerper),
  });
  if (!res.ok) await scheitern(res, fehler);
  return (res.status === 204 ? undefined : await res.json()) as T;
}

export function listSpaces(): Promise<Space[]> {
  return hole<Space[]>("/spaces", "Bereiche konnten nicht geladen werden");
}

/** Alle Bereiche mit Eigentümer und Seitenzahl — nur für Administratoren. */
export function listSpacesVerwaltung(): Promise<SpaceAdmin[]> {
  return hole<SpaceAdmin[]>("/spaces/verwaltung", "Bereiche konnten nicht geladen werden");
}

export function updateSpace(
  key: string,
  daten: { name: string; description?: string | null },
): Promise<Space> {
  return sende<Space>(`/spaces/${key}`, "PATCH", daten, "Bereich konnte nicht gespeichert werden");
}

export function getSpaceTree(key: string): Promise<PageNode[]> {
  return hole<PageNode[]>(`/spaces/${key}/pages`, "Seitenbaum konnte nicht geladen werden");
}

export function getPage(id: number): Promise<Page> {
  return hole<Page>(`/pages/${id}`, "Seite konnte nicht geladen werden");
}

export function listVersions(id: number): Promise<PageVersionInfo[]> {
  return hole<PageVersionInfo[]>(`/pages/${id}/versions`, "Versionen konnten nicht geladen werden");
}

// ── Schreibende Aufrufe ─────────────────────────────────────────────────────

export function createSpace(daten: {
  name: string;
  description?: string | null;
}): Promise<Space> {
  return sende<Space>("/spaces", "POST", daten, "Bereich konnte nicht angelegt werden");
}

/** Bereich löschen. Das Backend lehnt ab, solange noch Seiten darin liegen. */
export function deleteSpace(key: string): Promise<void> {
  return sende<void>(`/spaces/${key}`, "DELETE", undefined, "Bereich konnte nicht gelöscht werden");
}

export function createPage(daten: {
  space_id: number;
  title: string;
  parent_id?: number | null;
  body?: string;
  author?: string | null;
}): Promise<Page> {
  return sende<Page>("/pages", "POST", daten, "Seite konnte nicht angelegt werden");
}

export function updatePage(
  id: number,
  daten: {
    title?: string;
    body?: string;
    parent_id?: number | null;
    /** Bereichswechsel; nimmt Unterseiten mit und schreibt Verweise um. */
    space_id?: number;
    /** Stelle unter den Geschwistern (ab 0); das Backend nummeriert neu. */
    position?: number;
    author?: string | null;
  },
): Promise<Page> {
  return sende<Page>(`/pages/${id}`, "PATCH", daten, "Seite konnte nicht gespeichert werden");
}

export function deletePage(id: number): Promise<void> {
  return sende<void>(`/pages/${id}`, "DELETE", undefined, "Seite konnte nicht gelöscht werden");
}

// ── Anhänge ─────────────────────────────────────────────────────────────────

export function listAttachments(pageId: number): Promise<Attachment[]> {
  return hole<Attachment[]>(`/pages/${pageId}/attachments`, "Anhänge konnten nicht geladen werden");
}

export async function uploadAttachment(
  pageId: number,
  datei: File,
  autor?: string | null,
): Promise<Attachment> {
  const formular = new FormData();
  formular.append("file", datei);
  if (autor) formular.append("uploaded_by", autor);

  const res = await fetch(`${API}/pages/${pageId}/attachments`, {
    method: "POST",
    credentials: "same-origin",
    body: formular,
  });
  if (!res.ok) await scheitern(res, "Datei konnte nicht hochgeladen werden");
  return (await res.json()) as Attachment;
}

export function deleteAttachment(id: number): Promise<void> {
  return sende<void>(`/attachments/${id}`, "DELETE", undefined, "Anhang konnte nicht gelöscht werden");
}

/** URL zum Herunterladen bzw. Einbetten eines Anhangs. */
export function attachmentUrl(id: number): string {
  return `${API}/attachments/${id}`;
}

// ── Suche ───────────────────────────────────────────────────────────────────

export function search(q: string): Promise<SearchHit[]> {
  return hole<SearchHit[]>(`/search?q=${encodeURIComponent(q)}`, "Suche fehlgeschlagen");
}

// ── Schlagwörter, Verweise, Versionen, Übersicht ────────────────────────────

export function setLabels(pageId: number, names: string[]): Promise<Page> {
  return sende<Page>(
    `/pages/${pageId}/labels`,
    "PUT",
    { names },
    "Schlagwörter konnten nicht gespeichert werden",
  );
}

export function listLabels(): Promise<LabelCount[]> {
  return hole<LabelCount[]>("/labels", "Schlagwörter konnten nicht geladen werden");
}

export function pagesByLabel(name: string): Promise<PageSummary[]> {
  return hole<PageSummary[]>(
    `/labels/${encodeURIComponent(name)}/pages`,
    "Seiten zum Schlagwort konnten nicht geladen werden",
  );
}

export function listBacklinks(pageId: number): Promise<PageSummary[]> {
  return hole<PageSummary[]>(
    `/pages/${pageId}/backlinks`,
    "Rückverweise konnten nicht geladen werden",
  );
}

export function recentPages(limit = 10): Promise<PageSummary[]> {
  return hole<PageSummary[]>(`/recent?limit=${limit}`, "Übersicht konnte nicht geladen werden");
}

export function getVersion(pageId: number, revision: number): Promise<PageVersionInfo & { body: string }> {
  return hole(`/pages/${pageId}/versions/${revision}`, "Revision konnte nicht geladen werden");
}

export function diffVersions(
  pageId: number,
  revision: number,
  gegen: number,
): Promise<VersionDiff> {
  return hole<VersionDiff>(
    `/pages/${pageId}/versions/${revision}/diff?gegen=${gegen}`,
    "Vergleich konnte nicht geladen werden",
  );
}

export function restoreVersion(pageId: number, revision: number): Promise<Page> {
  return sende<Page>(
    `/pages/${pageId}/versions/${revision}/restore`,
    "POST",
    undefined,
    "Revision konnte nicht zurückgeholt werden",
  );
}

/** Suche, optional auf einen Bereich eingeschränkt (für die Link-Auswahl). */
export function searchIn(q: string, spaceId?: number): Promise<SearchHit[]> {
  const bereich = spaceId === undefined ? "" : `&space_id=${spaceId}`;
  return hole<SearchHit[]>(`/search?q=${encodeURIComponent(q)}${bereich}`, "Suche fehlgeschlagen");
}

// ── Anmeldung, Benutzer und Freigaben ───────────────────────────────────────

/** Wer gerade angemeldet ist. `id === null` heißt: offener Betrieb ohne Anmeldung. */
export interface Ich {
  id: number | null;
  username: string;
  display_name: string;
  is_admin: boolean;
  ist_offener_betrieb: boolean;
  darf_bereiche_anlegen: boolean;
}

export interface User {
  id: number;
  username: string;
  display_name: string;
  is_admin: boolean;
  is_active: boolean;
  created_at: string;
  darf_bereiche_anlegen: boolean;
}

export type Recht = "lesen" | "schreiben" | "loeschen" | "verwalten";

export interface Permission {
  id: number;
  space_id: number;
  user_id: number;
  level: Recht;
}

export function login(username: string, password: string): Promise<Ich> {
  return sende<Ich>("/auth/login", "POST", { username, password }, "Anmeldung fehlgeschlagen");
}

export function logout(): Promise<void> {
  return sende<void>("/auth/logout", "POST", undefined, "Abmelden fehlgeschlagen");
}

export function getIch(): Promise<Ich> {
  return hole<Ich>("/auth/me", "Anmeldestatus konnte nicht geladen werden");
}

export function listUsers(): Promise<User[]> {
  return hole<User[]>("/users", "Benutzer konnten nicht geladen werden");
}

export function createUser(daten: {
  username: string;
  display_name: string;
  password: string;
  is_admin: boolean;
  darf_bereiche_anlegen?: boolean;
}): Promise<User> {
  return sende<User>("/users", "POST", daten, "Benutzer konnte nicht angelegt werden");
}

export function updateUser(
  id: number,
  daten: {
    display_name?: string;
    is_admin?: boolean;
    is_active?: boolean;
    darf_bereiche_anlegen?: boolean;
  },
): Promise<User> {
  return sende<User>(`/users/${id}`, "PATCH", daten, "Benutzer konnte nicht gespeichert werden");
}

export function deleteUser(id: number): Promise<void> {
  return sende<void>(`/users/${id}`, "DELETE", undefined, "Benutzer konnte nicht gelöscht werden");
}

export function setPassword(
  id: number,
  neues_passwort: string,
  altes_passwort?: string,
): Promise<void> {
  return sende<void>(
    `/users/${id}/password`,
    "PUT",
    { neues_passwort, altes_passwort: altes_passwort ?? null },
    "Passwort konnte nicht gesetzt werden",
  );
}

export function listPermissions(spaceId: number): Promise<Permission[]> {
  return hole<Permission[]>(`/users/permissions/${spaceId}`, "Freigaben konnten nicht geladen werden");
}

export function setPermission(spaceId: number, userId: number, level: Recht): Promise<Permission> {
  return sende<Permission>(
    `/users/permissions/${spaceId}`,
    "PUT",
    { user_id: userId, level },
    "Freigabe konnte nicht gesetzt werden",
  );
}

export function revokePermission(spaceId: number, userId: number): Promise<void> {
  return sende<void>(
    `/users/permissions/${spaceId}/${userId}`,
    "DELETE",
    undefined,
    "Freigabe konnte nicht entzogen werden",
  );
}
