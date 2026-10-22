/**
 * Verwaltung: Benutzer und Bereiche.
 *
 * Erreichbar unter `#/verwaltung`, nur für Administratoren. Rechte hängen am
 * Bereich, nicht an der einzelnen Seite — deshalb je Bereich eine Liste.
 * Private Bereiche bleiben auch hier verschlossen: sichtbar sind nur Name,
 * Eigentümer und Seitenzahl, keine Freigaben und kein Inhalt.
 */

import { KeyRound, Loader2, Lock, Trash2, UserPlus } from "lucide-react";
import { useCallback, useEffect, useState, type FormEvent } from "react";

import {
  createUser,
  deleteSpace,
  deleteUser,
  listPermissions,
  listSpacesVerwaltung,
  listUsers,
  revokePermission,
  setPassword,
  setPermission,
  updateUser,
  type Permission,
  type Recht,
  type SpaceAdmin,
  type User,
} from "../lib/api-client";
import { PasswortDialog } from "./PasswortDialog";

const STUFEN: { wert: Recht; label: string }[] = [
  { wert: "lesen", label: "lesen" },
  { wert: "schreiben", label: "schreiben" },
  { wert: "loeschen", label: "löschen/verschieben" },
  { wert: "verwalten", label: "verwalten" },
];

const select =
  "rounded-lg border border-border bg-background px-2 py-1 text-sm text-text focus:border-primary focus:outline-none";
const feld =
  "w-full rounded-lg border border-border bg-background px-3 py-2 text-sm focus:border-primary focus:outline-none";

export function VerwaltungPage({ istAdmin }: { istAdmin: boolean }) {
  const [benutzer, setBenutzer] = useState<User[]>([]);
  const [spaces, setSpaces] = useState<SpaceAdmin[]>([]);
  const [fehler, setFehler] = useState<string | null>(null);
  const [meldung, setMeldung] = useState<string | null>(null);
  const [laedt, setLaedt] = useState(true);
  const [passwortFuer, setPasswortFuer] = useState<User | null>(null);

  const allesLaden = useCallback(async () => {
    try {
      const [u, s] = await Promise.all([listUsers(), listSpacesVerwaltung()]);
      setBenutzer(u);
      setSpaces(s);
      setFehler(null);
    } catch (e) {
      setFehler(e instanceof Error ? e.message : "Daten konnten nicht geladen werden");
    } finally {
      setLaedt(false);
    }
  }, []);

  useEffect(() => {
    if (istAdmin) void allesLaden();
    else setLaedt(false);
  }, [istAdmin, allesLaden]);

  if (!istAdmin) {
    return <p className="text-text-secondary">Diese Seite steht nur Administratoren offen.</p>;
  }

  const anlegen = async (daten: {
    username: string;
    display_name: string;
    password: string;
    is_admin: boolean;
    darf_bereiche_anlegen: boolean;
  }) => {
    try {
      await createUser(daten);
      await allesLaden();
    } catch (e) {
      setFehler(e instanceof Error ? e.message : "Benutzer konnte nicht angelegt werden");
    }
  };

  const loeschen = async (nutzer: User) => {
    if (!window.confirm(`Benutzer „${nutzer.display_name}" löschen?`)) return;
    try {
      await deleteUser(nutzer.id);
      await allesLaden();
      setFehler(null);
    } catch (e) {
      setFehler(e instanceof Error ? e.message : "Benutzer konnte nicht gelöscht werden");
    }
  };

  const feldAendern = async (nutzer: User, daten: Parameters<typeof updateUser>[1]) => {
    try {
      await updateUser(nutzer.id, daten);
      await allesLaden();
      setFehler(null);
    } catch (e) {
      setFehler(e instanceof Error ? e.message : "Benutzer konnte nicht gespeichert werden");
    }
  };

  const passwortSpeichern = async (neu: string) => {
    if (passwortFuer === null) return;
    const name = passwortFuer.display_name;
    await setPassword(passwortFuer.id, neu);
    setPasswortFuer(null);
    setMeldung(`Passwort für „${name}" gesetzt. Offene Sitzungen dieses Kontos wurden beendet.`);
  };

  const bereichLoeschen = async (space: SpaceAdmin) => {
    if (space.seiten > 0) {
      setFehler(
        `Bereich „${space.name}" enthält noch ${space.seiten} Seite${space.seiten === 1 ? "" : "n"} — ` +
          "diese bitte erst löschen.",
      );
      return;
    }
    if (!window.confirm(`Bereich „${space.name}" löschen?`)) return;
    try {
      await deleteSpace(space.key);
      await allesLaden();
      setFehler(null);
    } catch (e) {
      setFehler(e instanceof Error ? e.message : "Bereich konnte nicht gelöscht werden");
    }
  };

  const oeffentlicheSpaces = spaces.filter((s) => !s.is_private);
  const privateSpaces = spaces.filter((s) => s.is_private);

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-xl font-semibold text-text">Verwaltung</h1>
        <p className="mt-1 text-sm text-text-secondary">
          Benutzer anlegen und Bereiche freigeben. Administratoren sehen und bearbeiten
          alle öffentlichen Bereiche, ohne Einzelfreigabe. Private Bereiche gehören genau
          einem Konto — Administratoren sehen darin nur Name, Eigentümer und Seitenzahl.
          Der Inhalt ist für Administratoren nicht erreichbar, auch nicht auf Umwegen:
          eine Übertragung an ein anderes Konto gibt es nicht. Ein leerer privater
          Bereich lässt sich löschen, wenn sein Konto nicht mehr gebraucht wird.
        </p>
      </div>

      {fehler !== null && (
        <p className="rounded-lg border border-danger/40 bg-danger/10 px-3 py-2 text-sm text-danger">
          {fehler}
        </p>
      )}

      {meldung !== null && (
        <p className="rounded-lg border border-primary/40 bg-primary-light px-3 py-2 text-sm text-text">
          {meldung}
        </p>
      )}

      <section>
        <h2 className="mb-3 text-sm font-semibold text-text">Benutzer</h2>
        {laedt ? (
          <p className="text-sm text-text-secondary">Lade …</p>
        ) : (
          <div className="overflow-hidden rounded-lg border border-border bg-card shadow-card">
            {benutzer.map((nutzer) => (
              <div
                key={nutzer.id}
                className="flex flex-wrap items-center gap-2 border-b border-border px-4 py-2 last:border-b-0"
              >
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm text-text">{nutzer.display_name}</p>
                  <p className="truncate text-xs text-text-secondary">{nutzer.username}</p>
                </div>
                {!nutzer.is_active && (
                  <span className="rounded-lg border border-danger/40 px-2 py-0.5 text-xs text-danger">
                    gesperrt
                  </span>
                )}
                <label className="flex items-center gap-1.5 text-xs text-text-secondary">
                  <input
                    type="checkbox"
                    checked={nutzer.is_admin}
                    onChange={(e) => void feldAendern(nutzer, { is_admin: e.target.checked })}
                  />
                  Administrator
                </label>
                <label className="flex items-center gap-1.5 text-xs text-text-secondary">
                  <input
                    type="checkbox"
                    checked={nutzer.darf_bereiche_anlegen}
                    onChange={(e) =>
                      void feldAendern(nutzer, { darf_bereiche_anlegen: e.target.checked })
                    }
                  />
                  darf Bereiche anlegen
                </label>
                <label className="flex items-center gap-1.5 text-xs text-text-secondary">
                  <input
                    type="checkbox"
                    checked={nutzer.is_active}
                    onChange={(e) => void feldAendern(nutzer, { is_active: e.target.checked })}
                  />
                  aktiv
                </label>
                <button
                  type="button"
                  onClick={() => setPasswortFuer(nutzer)}
                  title="Passwort setzen"
                  aria-label={`Passwort für ${nutzer.display_name} setzen`}
                  className="rounded-lg p-2 text-text-secondary transition hover:bg-background hover:text-text"
                >
                  <KeyRound className="h-4 w-4" />
                </button>
                <button
                  type="button"
                  onClick={() => void loeschen(nutzer)}
                  title="Benutzer löschen"
                  aria-label={`${nutzer.display_name} löschen`}
                  className="rounded-lg p-2 text-text-secondary transition hover:bg-background hover:text-danger"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            ))}
            {benutzer.length === 0 && (
              <p className="px-4 py-3 text-sm text-text-secondary">Noch keine Benutzer.</p>
            )}
          </div>
        )}
        <NeuerBenutzer onAnlegen={anlegen} />
      </section>

      <section>
        <h2 className="mb-3 text-sm font-semibold text-text">Bereiche</h2>
        {laedt ? (
          <p className="text-sm text-text-secondary">Lade …</p>
        ) : (
          <div className="space-y-4">
            {oeffentlicheSpaces.map((space) => (
              <Freigaben
                key={space.id}
                space={space}
                benutzer={benutzer}
                onFehler={setFehler}
                onLoeschen={() => void bereichLoeschen(space)}
              />
            ))}
            {privateSpaces.map((space) => (
              <PrivaterBereich
                key={space.id}
                space={space}
                onLoeschen={() => void bereichLoeschen(space)}
              />
            ))}
            {spaces.length === 0 && (
              <p className="text-sm text-text-secondary">Noch keine Bereiche.</p>
            )}
          </div>
        )}
      </section>

      {passwortFuer !== null && (
        <PasswortDialog
          titel={`Neues Passwort für „${passwortFuer.display_name}"`}
          altesPasswortNoetig={false}
          onSpeichern={passwortSpeichern}
          onAbbruch={() => setPasswortFuer(null)}
        />
      )}
    </div>
  );
}

/** Formular für ein neues Konto samt Startpasswort. */
function NeuerBenutzer({
  onAnlegen,
}: {
  onAnlegen: (daten: {
    username: string;
    display_name: string;
    password: string;
    is_admin: boolean;
    darf_bereiche_anlegen: boolean;
  }) => Promise<void>;
}) {
  const [username, setUsername] = useState("");
  const [anzeigename, setAnzeigename] = useState("");
  const [passwort, setPasswort] = useState("");
  const [admin, setAdmin] = useState(false);
  const [darfBereicheAnlegen, setDarfBereicheAnlegen] = useState(false);
  const [laeuft, setLaeuft] = useState(false);

  const absenden = async (e: FormEvent) => {
    e.preventDefault();
    setLaeuft(true);
    await onAnlegen({
      username: username.trim(),
      display_name: anzeigename.trim() || username.trim(),
      password: passwort,
      is_admin: admin,
      darf_bereiche_anlegen: darfBereicheAnlegen,
    });
    setLaeuft(false);
    setUsername("");
    setAnzeigename("");
    setPasswort("");
    setAdmin(false);
    setDarfBereicheAnlegen(false);
  };

  return (
    <form
      onSubmit={(e) => void absenden(e)}
      className="mt-4 rounded-lg border border-border bg-card p-4 shadow-card"
    >
      <p className="mb-3 text-sm font-medium text-text">Neuer Benutzer</p>
      <div className="grid gap-3 sm:grid-cols-3">
        <input
          className={feld}
          placeholder="Benutzername"
          autoComplete="off"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
        />
        <input
          className={feld}
          placeholder="Anzeigename"
          autoComplete="off"
          value={anzeigename}
          onChange={(e) => setAnzeigename(e.target.value)}
        />
        <input
          className={feld}
          placeholder="Startpasswort (mind. 8)"
          type="password"
          autoComplete="new-password"
          value={passwort}
          onChange={(e) => setPasswort(e.target.value)}
        />
      </div>
      <p className="mt-3 text-xs text-text-secondary">
        Es entsteht automatisch ein privater Bereich mit dem Anzeigenamen des neuen Kontos.
      </p>
      <div className="mt-3 flex flex-wrap items-center gap-4">
        <label className="flex items-center gap-2 text-sm text-text-secondary">
          <input type="checkbox" checked={admin} onChange={(e) => setAdmin(e.target.checked)} />
          Administrator
        </label>
        <label className="flex items-center gap-2 text-sm text-text-secondary">
          <input
            type="checkbox"
            checked={darfBereicheAnlegen}
            onChange={(e) => setDarfBereicheAnlegen(e.target.checked)}
          />
          darf Bereiche anlegen
        </label>
        <button
          type="submit"
          disabled={laeuft || username.trim() === "" || passwort.length < 8}
          className="flex items-center gap-2 rounded-lg bg-primary px-3 py-2 text-sm font-medium text-white transition hover:bg-primary-hover disabled:opacity-50"
        >
          {laeuft ? <Loader2 className="h-4 w-4 animate-spin" /> : <UserPlus className="h-4 w-4" />}
          Anlegen
        </button>
      </div>
    </form>
  );
}

/** Freigaben eines einzelnen öffentlichen Bereichs. */
function Freigaben({
  space,
  benutzer,
  onFehler,
  onLoeschen,
}: {
  space: SpaceAdmin;
  benutzer: User[];
  onFehler: (text: string) => void;
  onLoeschen: () => void;
}) {
  const [freigaben, setFreigaben] = useState<Permission[]>([]);
  const [neuerNutzer, setNeuerNutzer] = useState<string>("");
  const [neueStufe, setNeueStufe] = useState<Recht>("lesen");

  const laden = useCallback(async () => {
    try {
      setFreigaben(await listPermissions(space.id));
    } catch (e) {
      onFehler(e instanceof Error ? e.message : "Freigaben konnten nicht geladen werden");
    }
  }, [space.id, onFehler]);

  useEffect(() => {
    void laden();
  }, [laden]);

  const name = (userId: number) =>
    benutzer.find((b) => b.id === userId)?.display_name ?? `Benutzer ${userId}`;

  const setzen = async (userId: number, level: Recht) => {
    try {
      await setPermission(space.id, userId, level);
      await laden();
    } catch (e) {
      onFehler(e instanceof Error ? e.message : "Freigabe konnte nicht gesetzt werden");
    }
  };

  const entziehen = async (userId: number) => {
    try {
      await revokePermission(space.id, userId);
      await laden();
    } catch (e) {
      onFehler(e instanceof Error ? e.message : "Freigabe konnte nicht entzogen werden");
    }
  };

  // Administratoren brauchen keine Freigabe, und wer schon eine hat, taucht oben auf.
  const offen = benutzer.filter(
    (b) => !b.is_admin && !freigaben.some((f) => f.user_id === b.id),
  );

  return (
    <div className="rounded-lg border border-border bg-card p-4 shadow-card">
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="text-sm font-medium text-text">{space.name}</p>
          <p className="text-xs text-text-secondary">
            {space.seiten} Seite{space.seiten === 1 ? "" : "n"}
          </p>
        </div>
        <button
          type="button"
          onClick={onLoeschen}
          title={`Bereich „${space.name}" löschen`}
          aria-label={`Bereich ${space.name} löschen`}
          className="shrink-0 rounded-lg p-2 text-text-secondary transition hover:bg-background hover:text-danger"
        >
          <Trash2 className="h-4 w-4" />
        </button>
      </div>

      <div className="mt-3 space-y-2">
        {freigaben.map((freigabe) => (
          <div key={freigabe.id} className="flex items-center gap-2">
            <span className="min-w-0 flex-1 truncate text-sm text-text">
              {name(freigabe.user_id)}
            </span>
            <select
              className={select}
              value={freigabe.level}
              onChange={(e) => void setzen(freigabe.user_id, e.target.value as Recht)}
            >
              {STUFEN.map((stufe) => (
                <option key={stufe.wert} value={stufe.wert}>
                  {stufe.label}
                </option>
              ))}
            </select>
            <button
              type="button"
              onClick={() => void entziehen(freigabe.user_id)}
              title="Freigabe entziehen"
              aria-label={`Freigabe für ${name(freigabe.user_id)} entziehen`}
              className="rounded-lg p-2 text-text-secondary transition hover:bg-background hover:text-danger"
            >
              <Trash2 className="h-4 w-4" />
            </button>
          </div>
        ))}
        {freigaben.length === 0 && (
          <p className="text-sm text-text-secondary">
            Keine Freigaben — außer Administratoren sieht diesen Bereich niemand.
          </p>
        )}
      </div>

      {offen.length > 0 && (
        <div className="mt-3 flex items-center gap-2 border-t border-border pt-3">
          <select
            className={select}
            value={neuerNutzer}
            onChange={(e) => setNeuerNutzer(e.target.value)}
          >
            <option value="">Benutzer wählen …</option>
            {offen.map((b) => (
              <option key={b.id} value={b.id}>
                {b.display_name}
              </option>
            ))}
          </select>
          <select
            className={select}
            value={neueStufe}
            onChange={(e) => setNeueStufe(e.target.value as Recht)}
          >
            {STUFEN.map((stufe) => (
              <option key={stufe.wert} value={stufe.wert}>
                {stufe.label}
              </option>
            ))}
          </select>
          <button
            type="button"
            disabled={neuerNutzer === ""}
            onClick={() => {
              void setzen(Number(neuerNutzer), neueStufe);
              setNeuerNutzer("");
            }}
            className="rounded-lg border border-border px-3 py-1.5 text-sm transition hover:bg-background disabled:opacity-50"
          >
            Freigeben
          </button>
        </div>
      )}
    </div>
  );
}

/** Zeile für einen privaten Bereich — keine Freigaben, nur Metadaten. */
function PrivaterBereich({
  space,
  onLoeschen,
}: {
  space: SpaceAdmin;
  onLoeschen: () => void;
}) {
  return (
    <div className="flex flex-wrap items-center gap-3 rounded-lg border border-border bg-card p-4 shadow-card">
      <Lock className="h-4 w-4 shrink-0 text-text-secondary" aria-hidden="true" />
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm text-text">
          {space.name} <span className="text-text-secondary">· privat · {space.owner_name ?? "ohne Eigentümer"}</span>
        </p>
        <p className="text-xs text-text-secondary">
          {space.seiten} Seite{space.seiten === 1 ? "" : "n"}
        </p>
      </div>
      <button
        type="button"
        onClick={onLoeschen}
        title={`Bereich „${space.name}" löschen`}
        aria-label={`Bereich ${space.name} löschen`}
        className="shrink-0 rounded-lg p-2 text-text-secondary transition hover:bg-background hover:text-danger"
      >
        <Trash2 className="h-4 w-4" />
      </button>
    </div>
  );
}
