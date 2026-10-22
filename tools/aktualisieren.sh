#!/usr/bin/env bash
# Holt den neuesten Stand und rollt ihn aus: Code, Python-Pakete, Datenbank-Migration,
# Frontend, Neustart des Dienstes. Vorher wird die Datenbank gesichert.
#
#   bash tools/aktualisieren.sh
set -euo pipefail

# Alles in einem Block: git pull kann diese Datei selbst ändern, die Bash liest den Block
# aber vollständig ein, bevor sie ihn ausführt.
{

WURZEL="$(cd "$(dirname "$0")/.." && pwd)"
cd "$WURZEL"
DIENSTNAME="$(basename "$WURZEL")-backend"

if [ -n "$(git status --porcelain --untracked-files=no)" ]; then
    echo "Es gibt lokale Änderungen am Code (git status). Bitte erst klären, dann erneut starten." >&2
    exit 1
fi

echo "== Neuester Stand"
git pull --ff-only

echo "== Datenbank sichern"
if [ -f backend/app.db ]; then
    SICHERUNG="backend/app.db.vor-update-$(date +%Y%m%d-%H%M%S)"
    .venv/bin/python -c 'import sqlite3, sys
quelle = sqlite3.connect(sys.argv[1]); ziel = sqlite3.connect(sys.argv[2])
quelle.backup(ziel); ziel.close(); quelle.close()' backend/app.db "$SICHERUNG"
    echo "   $SICHERUNG"
fi

echo "== Python-Pakete"
.venv/bin/pip install --quiet -r backend/requirements.txt

echo "== Datenbank migrieren"
(cd backend && PYTHONPATH=. ../.venv/bin/alembic upgrade head)

echo "== Frontend bauen"
(cd frontend && npm ci --no-audit --no-fund --loglevel=error && npm run build --silent)

echo "== Dienst neu starten (braucht sudo)"
sudo systemctl restart "$DIENSTNAME"
systemctl is-active "$DIENSTNAME"
echo "Fertig. Im Browser einmal hart neu laden (Strg+Shift+R)."
exit 0
}
