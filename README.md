# Kladde

Ein kleines, selbst gehostetes Wiki für den eigenen Server: hierarchische Bereiche und Seiten,
Markdown-Editor, Versionierung, Volltextsuche, Anmeldung mit Rechten pro Bereich.
**React 19 + FastAPI + SQLAlchemy + SQLite**, ein einziger Dienst, keine weitere Datenbank.

Gedacht für einen headless Linux-Server im eigenen Netz (z. B. einen Mini-PC mit Ubuntu Server),
auf dem auch [Claude Code](https://claude.com/claude-code) läuft. Ein mitgelieferter Skill lässt
Claude Seiten lesen und schreiben.

## Was es kann

- **Bereiche und Seiten** bis fünf Ebenen tief, per Hoch/Runter umsortierbar
- **Editor** mit Überschriften, Listen, Tabellen, Code, Links und Hinweis-Kästen.
  Gespeichert wird Markdown, damit Versionsvergleiche lesbar bleiben.
- **Volltextsuche** über Titel und Inhalt (SQLite FTS5) mit Trefferausschnitt
- **Versionierung:** jede Änderung wird zur Version, mit Vergleich und Zurückholen
- **Anhänge** an Seiten, Bilder per Zwischenablage direkt in den Text
- **Schlagwörter**, Startseite mit „zuletzt geändert“, Rückverweise, Inhaltsverzeichnis
- **Anmeldung und Rechte:** Konten, Privatbereiche, Freigaben pro Bereich (lesen, schreiben,
  verwalten)
- **PWA:** als App auf PC und Handy installierbar (braucht HTTPS)

## Installation

Voraussetzungen: Ubuntu/Debian, Python 3.12 oder neuer, Node.js 20 oder neuer.

```bash
sudo apt install -y git python3-venv nodejs npm
git clone https://github.com/donchrillo/kladde.git ~/kladde
cd ~/kladde
bash tools/installieren.sh --name "Kladde" --host "$(hostname).local"
```

Das Skript legt `.venv`, `.env` und die Datenbank an, baut das Frontend, fragt nach dem ersten
Administratorkonto und richtet den systemd-Dienst `kladde-backend` auf `127.0.0.1:8408` ein
(anderer Port: `--port`). Mehrfaches Ausführen schadet nicht.

### HTTPS mit Caddy

Browser installieren eine PWA nur über HTTPS. Das Skript gibt am Ende einen passenden Block für
Caddy aus, im Kern:

```
pn40.local {
    tls internal
    reverse_proxy 127.0.0.1:8408
}
```

```bash
sudo apt install -y caddy
sudo ufw allow 443/tcp              # falls ufw aktiv ist
sudo systemctl reload caddy
```

`tls internal` heißt: Caddy betreibt eine eigene kleine Zertifizierungsstelle. Deren
Stammzertifikat (`/var/lib/caddy/.local/share/caddy/pki/authorities/local/root.crt`) muss
einmal auf jedem Gerät installiert werden, das das Wiki öffnet.

Hinweis zu `.local`-Namen (Avahi/mDNS): Sie funktionieren nur im selben lokalen Netz, nicht über
VPN. Dort die IP-Adresse oder einen DNS-Eintrag verwenden.

### Updates

```bash
bash tools/aktualisieren.sh
```

Holt den neuesten Stand, sichert vorher `backend/app.db`, migriert, baut neu und startet den
Dienst neu.

### Claude Code einbinden

Im Wiki unter `#/verwaltung` einen Benutzer `claude` ohne Administratorrecht anlegen und ihm
Schreibrecht auf die gewünschten Bereiche geben. Dann den Ordner `skill/` nach
`~/.claude/skills/wiki/` kopieren und die Zugangsdatei anlegen, wie in `skill/SKILL.md`
beschrieben.

## Daten und Sicherung

Alles Wichtige liegt in zwei Orten: `backend/app.db` (Seiten, Versionen, Konten) und
`backend/attachments/` (hochgeladene Dateien). Beides gehört ins Backup, nicht ins Git.
Details: `docs/architecture/datenhaltung.md`.

## Entwicklung

```bash
python3 -m venv .venv && .venv/bin/pip install -r backend/requirements.txt
( cd backend && PYTHONPATH=. ../.venv/bin/alembic upgrade head )
( cd backend && PYTHONPATH=. ../.venv/bin/uvicorn src.main:app --reload --port 8408 )
( cd frontend && npm install && npm run dev )     # Vite auf :8418, /api -> :8408
```

Für die Entwicklung über `http://localhost` in `.env` `COOKIE_SECURE=false` setzen.
Tests: `.venv/bin/pip install pytest`, dann `cd backend && PYTHONPATH=. ../.venv/bin/pytest`.
Architektur: `docs/architecture/`.

## Lizenz

[PolyForm Noncommercial 1.0.0](https://polyformproject.org/licenses/noncommercial/1.0.0), siehe
`LICENSE`: Nutzen, Verändern und Weitergeben sind für **nicht-kommerzielle** Zwecke erlaubt
(privat, Vereine, Bildung, gemeinnützige Einrichtungen). Kommerzielle Nutzung, etwa Verkauf
oder Einsatz als Teil eines kostenpflichtigen Angebots, ist nicht gestattet. Bei Weitergabe
müssen Lizenztext und die Zeile `Required Notice` mitgegeben werden.

Beiträge sind willkommen, die Bedingungen dafür stehen in `CONTRIBUTING.md`.
