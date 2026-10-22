# CLAUDE.md — Kladde

Selbst gehostetes Wiki: hierarchische Bereiche und Seiten, Markdown-Editor, Versionierung,
Volltextsuche, Anmeldung mit Rechten pro Bereich. Überblick und Installation: `README.md`.

## Architektur

```
backend/      FastAPI: REST-API unter /api, SQLAlchemy-ORM + Alembic-Migrationen, SQLite.
              Liefert in Produktion das gebaute Frontend (frontend/dist) mit aus.
frontend/     React 19 + TS + Vite PWA, spricht das Backend nur über /api an.
tools/        installieren.sh, aktualisieren.sh, admin_anlegen.py, bereich_entfernen.py
skill/        Skill für Claude Code: Seiten über die API lesen und schreiben
deploy/       systemd-Vorlage, Hinweise zum Betrieb
docs/         Architektur und Datenhaltung
```

## Harte Regeln

- **Secrets nie ins Repo.** `.env`, `.venv`, `backend/app.db`, `backend/attachments/` sind in
  `.gitignore`.
- **Inhalte nur über die API ändern**, nie direkt in `backend/app.db` (sonst fehlen Versionen
  und Suchindex). Ausnahme: `tools/admin_anlegen.py` für das erste Konto.
- **Schema nur über Migrationen ändern:** Modelländerung in `backend/src/models/` immer mit
  `alembic revision --autogenerate`, die erzeugte Migration durchlesen (FTS5-Tabellen stehen
  nicht in `Base.metadata`, ein Filter in `alembic/env.py` hält sie heraus).
- **Schichtentrennung:** Frontend kennt das Backend nur über HTTP.
- Generierte Artefakte (`dist/`, `node_modules/`, `__pycache__/`) nicht committen.
- Texte in der Oberfläche und Kommentare auf Deutsch.

## Betrieb

- Backend-Änderungen brauchen einen Neustart des Dienstes (`sudo systemctl restart
  <ordnername>-backend`), Frontend-Builds sind sofort live. Nach einem Build im Browser hart
  neu laden (Strg+Shift+R), der Service-Worker hält sonst die alte Version.
- Ob das Backend läuft: `curl http://127.0.0.1:8408/api/health`.
- Prozesse nie per Muster beenden (`pkill`), sondern per PID (`ss -ltnp | grep :8408`).

## Code-Qualität

- Python: ruff + black + mypy (Konfiguration in `pyproject.toml`), Tests mit pytest
  (`cd backend && PYTHONPATH=. ../.venv/bin/pytest`).
- Frontend: ESLint + TypeScript strict (`npm run lint`, `npm run build`).
