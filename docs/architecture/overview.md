# Architektur-Überblick

## Zwei Schichten, eine Origin

```
 Browser (PWA) ──── /api ────▶ Backend (FastAPI)
   React 19          HTTP          │
   Vite + Tailwind   JSON          ▼
   vite-plugin-pwa            SQLAlchemy 2.0 ORM
                                   │
                                   ▼
                            Datenbank (SQLite / PostgreSQL)
                              ▲
                              │ Alembic-Migrationen
```

- **Same-origin:** In Produktion liefert das Backend das gebaute Frontend (`frontend/dist`)
  aus; im Dev proxyt Vite `/api` ans Backend. Das Frontend nutzt deshalb überall relative
  Pfade (`/api/...`) über den zentralen Client `frontend/src/lib/api-client.ts`.
- **Keine Querimporte:** Das Frontend kennt das Backend nur über HTTP.

## Backend-Aufbau (`backend/src/`)

| Datei | Zweck |
|-------|-------|
| `main.py` | App-Factory: CORS (Dev), Router-Includes, Static-Mount des Frontends (Prod). |
| `config.py` | `pydantic-settings`: liest `.env` (`DATABASE_URL`, `FRONTEND_URL`). |
| `database.py` | SQLAlchemy-Engine, `SessionLocal`, `Base`, `get_db`-Dependency. |
| `models/` | ORM-Modelle (SQLAlchemy 2.0 `Mapped`/`mapped_column`). |
| `schemas.py` | Pydantic-Schemas für Request/Response (vom ORM entkoppelt). |
| `routers/` | `health`, `spaces` (Bereiche + Seitenbaum), `pages` (Seiten + Versionen). |
| `slug.py` | Titel → URL-Slug (deutsche Umlaute werden ausgeschrieben). |

## Datenmodell

```
space (Bereich)
  key (eindeutig), name, description
    │ 1:n
    ▼
page (Seite)                        parent_id ──┐  Baum über Selbstreferenz
  space_id, parent_id, title, slug,  ◀──────────┘
  body (Markdown), position
    │ 1:n
    ▼
page_version (Revision)
  page_id, revision, title, body, author
```

- **Slug eindeutig pro Bereich**, nicht pro Elternknoten (`uq_page_space_slug`). Damit
  bleiben Links stabil, wenn eine Seite im Baum verschoben wird.
- **Jede inhaltliche Änderung hängt eine Revision an** — auch das Anlegen (Revision 1).
  Die Historie enthält also immer auch den aktuellen Stand. Reines Verschieben oder
  Umsortieren erzeugt keine Revision.
- **Löschen nur blattweise:** eine Seite mit Unterseiten liefert `409`, damit kein
  Teilbaum versehentlich verschwindet. Die Revisionen einer Seite hängen per
  `cascade="all, delete-orphan"` daran.
- Ohne Auth gibt der Client den `author` einer Revision optional selbst an.

## Datenfluss eines Requests

1. Frontend holt den Seitenbaum (`GET /api/spaces/{key}/pages`) über den API-Client.
2. Router-Handler erhält per `Depends(get_db)` eine Session.
3. SQLAlchemy lädt die Zeilen flach; `_baum()` verschachtelt sie in Python — das
   verhält sich auf SQLite und PostgreSQL identisch. Pydantic serialisiert
   (`from_attributes`).
4. Frontend-Hooks (`useSpaces`, `useSeitenbaum`, `useSeite`) halten je den State
   `loading | ready | error`.
5. Der Markdown-Body wird im Frontend gerendert (`marked`) und **immer** durch
   DOMPurify geschickt — Seiten sind von jedem im LAN schreibbar.

## Persistenz & Migrationen

- **DB-Default SQLite** (`sqlite:///./backend/app.db`) — zero-config, ideal für Start &
  Tests. Umstieg auf PostgreSQL: `DATABASE_URL=postgresql+psycopg://user:pw@host/db`
  in `.env`, Treiber `psycopg[binary]` installieren.
- **Schema-Änderungen ausschließlich über Alembic.** `alembic/env.py` importiert
  `Base.metadata`, sodass `--autogenerate` Modelländerungen erkennt. `render_as_batch=True`
  ist gesetzt (nötig für `ALTER TABLE` unter SQLite).
- Tests umgehen die Datei-DB komplett: `conftest.py` hängt eine frische In-Memory-SQLite
  per Dependency-Override ein.

## Constraints

- Secure-Context (`https`/`localhost`) für PWA-Installation und kamera-/sensornahe APIs.
- CORS-Origins im Dev in `main.py` pflegen (Vite-Port).

## Deployment (Homelab)

Headless Linux-Server hinter bestehendem **Caddy** (`tls internal` →
gültiges `https`), Zugriff im LAN. Backend als systemd-Dienst auf
`127.0.0.1:8408`. Details in `deploy/README.md`.

```
pn40.local {
    tls internal
    reverse_proxy 127.0.0.1:8408
    header /api/* Cache-Control "no-store"
}
```

## Weiterführend

- `datenhaltung.md` — wo die Inhalte konkret liegen (Datei, Tabellen, Anhänge, Backup),
  bewusst allgemeinverständlich gehalten.
