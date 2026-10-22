/**
 * Anmeldezustand fürs ganze Frontend.
 *
 * Beim Start fragt der Provider einmal `/api/auth/me`. Drei Ausgänge:
 *
 *   "laedt"      — noch unklar, es wird nichts gerendert
 *   "anonym"     — Anmeldemaske zeigen
 *   "angemeldet" — normaler Betrieb (auch im offenen Betrieb ohne Anmeldung,
 *                  dann trägt `ich.ist_offener_betrieb` das Merkmal)
 *
 * Läuft irgendwo im Programm ein Aufruf in einen 401, meldet der api-client
 * das hierher — der Zustand fällt auf "anonym" und die Maske erscheint. So
 * muss keine einzelne Komponente daran denken.
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";

import { ApiError, getIch, login as apiLogin, logout as apiLogout, setzeAbmeldeMelder, type Ich } from "./api-client";

type AuthState = "laedt" | "anonym" | "angemeldet";

interface AuthValue {
  ich: Ich | null;
  state: AuthState;
  anmelden: (username: string, password: string) => Promise<void>;
  abmelden: () => Promise<void>;
}

const AuthContext = createContext<AuthValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [ich, setIch] = useState<Ich | null>(null);
  const [state, setState] = useState<AuthState>("laedt");

  const laden = useCallback(async () => {
    try {
      setIch(await getIch());
      setState("angemeldet");
    } catch (e) {
      // 401 heißt "bitte anmelden". Alles andere (Backend aus) genauso — die
      // Maske meldet dann beim Versuch einen verständlichen Fehler.
      if (e instanceof ApiError && e.status !== 401) console.warn(e);
      setIch(null);
      setState("anonym");
    }
  }, []);

  useEffect(() => {
    setzeAbmeldeMelder(() => {
      setIch(null);
      setState("anonym");
    });
    void laden();
    return () => setzeAbmeldeMelder(null);
  }, [laden]);

  const anmelden = useCallback(async (username: string, password: string) => {
    setIch(await apiLogin(username, password));
    setState("angemeldet");
  }, []);

  const abmelden = useCallback(async () => {
    try {
      await apiLogout();
    } finally {
      setIch(null);
      setState("anonym");
    }
  }, []);

  return (
    <AuthContext.Provider value={{ ich, state, anmelden, abmelden }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthValue {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth braucht einen AuthProvider");
  return value;
}
