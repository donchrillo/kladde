# backend/ — FastAPI + SQLAlchemy + Alembic

REST-API mit SQLAlchemy-2.0-ORM und Alembic-Migrationen. Liefert in Produktion das
gebaute Frontend (`frontend/dist`) aus.

## Setup

```bash
python3 -m venv ../.venv
../.venv/bin/pip install -r requirements.txt
```

## Datenbank vorbereiten

```bash
PYTHONPATH=. ../.venv/bin/alembic upgrade head
```

Default ist eine lokale **SQLite**-Datei (`backend/app.db`, gitignored). Für **PostgreSQL**
`DATABASE_URL` in der Root-`.env` setzen (z. B.
`postgresql+psycopg://user:pw@127.0.0.1:5432/kladde`) und den Treiber
`psycopg[binary]` installieren.

## Starten

```bash
PYTHONPATH=. ../.venv/bin/uvicorn src.main:app --reload --port 8408
```

- `GET /api/health` → `{"status":"ok"}`
- Bereiche: `GET|POST /api/spaces`, `GET /api/spaces/{key}`,
  `GET /api/spaces/{key}/pages` (Seitenbaum, verschachtelt, ohne Inhalte)
- Seiten: `POST /api/pages`, `GET|PATCH|DELETE /api/pages/{id}`
- Versionen: `GET /api/pages/{id}/versions`, `GET /api/pages/{id}/versions/{revision}`
- OpenAPI-Doku: `http://127.0.0.1:8408/docs`

## Tests

```bash
PYTHONPATH=. ../.venv/bin/pytest
```

Die Tests nutzen eine isolierte In-Memory-SQLite (siehe `tests/conftest.py`), die
echte DB wird nicht berührt.

## Neue Modelle / Migrationen

1. Modell in `src/models/` anlegen, in `src/models/__init__.py` importieren.
2. `PYTHONPATH=. ../.venv/bin/alembic revision --autogenerate -m "beschreibung"`
3. Generierte Migration in `alembic/versions/` prüfen.
4. `PYTHONPATH=. ../.venv/bin/alembic upgrade head`

## Layout

```
src/
  main.py        App-Factory (CORS, Router, Static-Mount)
  config.py      pydantic-settings (.env)
  database.py    Engine, SessionLocal, Base, get_db
  models/        ORM-Modelle (space.py, page.py, page_version.py)
  schemas.py     Pydantic-Schemas
  slug.py        Titel -> URL-Slug
  routers/       health.py, spaces.py, pages.py
alembic/         Migrationen (env.py, versions/)
tests/           pytest (In-Memory-SQLite)
```
