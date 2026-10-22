#!/usr/bin/env bash
# Richtet das Wiki auf einem Linux-Server ein (Ubuntu/Debian), aus einem frischen Klon heraus.
#
#   bash tools/installieren.sh [--name "Mein Wiki"] [--port 8408] [--host pn40.local] [--ohne-dienst]
#
#   --name         Anzeigename im Browser (Standard: Kladde)
#   --port         Port des Backends auf 127.0.0.1 (Standard: 8408)
#   --host         Name, unter dem das Wiki per HTTPS erreichbar ist (Standard: <rechnername>.local)
#   --ohne-dienst  keinen systemd-Dienst einrichten (zum Ausprobieren)
#
# Mehrfaches Ausführen schadet nicht: vorhandene .env-Dateien, Datenbank und Konten bleiben.
# sudo wird nur für den systemd-Dienst gebraucht. Caddy richtet das Skript nicht selbst ein,
# es gibt am Ende den passenden Block aus.
set -euo pipefail

WURZEL="$(cd "$(dirname "$0")/.." && pwd)"
cd "$WURZEL"

NAME="Kladde"
PORT=8408
HOST="$(hostname).local"
DIENST=1
while [ $# -gt 0 ]; do
    case "$1" in
        --name) NAME="$2"; shift 2 ;;
        --port) PORT="$2"; shift 2 ;;
        --host) HOST="$2"; shift 2 ;;
        --ohne-dienst) DIENST=0; shift ;;
        *) echo "Unbekannte Angabe: $1" >&2; exit 2 ;;
    esac
done
DIENSTNAME="$(basename "$WURZEL")-backend"

echo "== Voraussetzungen prüfen"
fehlt=()
python3 -c 'import venv, ensurepip' 2>/dev/null || fehlt+=(python3-venv)
command -v npm >/dev/null || fehlt+=(nodejs npm)
if [ ${#fehlt[@]} -gt 0 ]; then
    echo "Es fehlen Pakete. Bitte installieren und das Skript erneut starten:" >&2
    echo "    sudo apt install -y ${fehlt[*]}" >&2
    exit 1
fi
NODE_HAUPT="$(node -p 'process.versions.node.split(".")[0]')"
if [ "$NODE_HAUPT" -lt 20 ]; then
    echo "Node.js $NODE_HAUPT ist zu alt, gebraucht wird mindestens 20." >&2
    exit 1
fi
if [ "$DIENST" = 1 ] && ss -ltn | grep -q ":$PORT " && ! systemctl is-active -q "$DIENSTNAME"; then
    echo "Port $PORT ist schon belegt (ss -ltnp | grep :$PORT). Anderen Port mit --port wählen." >&2
    exit 1
fi

echo "== Python-Umgebung (.venv)"
[ -d .venv ] || python3 -m venv .venv
.venv/bin/pip install --quiet --upgrade pip
.venv/bin/pip install --quiet -r backend/requirements.txt

echo "== Konfiguration"
if [ ! -f .env ]; then
    # DATABASE_URL auskommentiert: dann greift der absolute Standardpfad backend/app.db,
    # unabhängig vom Arbeitsverzeichnis des Dienstes.
    sed -e 's|^DATABASE_URL=|# DATABASE_URL=|' \
        -e "s|^FRONTEND_URL=.*|FRONTEND_URL=https://$HOST|" \
        -e 's|^AUTH_ENABLED=.*|AUTH_ENABLED=true|' \
        -e 's|^COOKIE_SECURE=.*|COOKIE_SECURE=true|' \
        .env.example > .env
    chmod 600 .env
    echo "   .env angelegt (Anmeldung eingeschaltet, Adresse https://$HOST)"
else
    echo "   .env vorhanden, bleibt unverändert"
fi
if [ ! -f frontend/.env ]; then
    printf 'VITE_WIKI_NAME=%s\n' "$NAME" > frontend/.env
    echo "   frontend/.env angelegt (Name: $NAME)"
else
    echo "   frontend/.env vorhanden, bleibt unverändert"
fi

echo "== Datenbank anlegen bzw. migrieren"
(cd backend && PYTHONPATH=. "$WURZEL"/.venv/bin/alembic upgrade head)

echo "== Frontend bauen"
(cd frontend && npm ci --no-audit --no-fund --loglevel=error && npm run build --silent)

echo "== Erstes Administratorkonto"
ANZAHL="$(cd backend && PYTHONPATH=. "$WURZEL"/.venv/bin/python -c \
    'from src.database import SessionLocal; from src.models import User
with SessionLocal() as db: print(db.query(User).count())')"
if [ "$ANZAHL" = 0 ]; then
    read -rp "   Anmeldename für den Administrator: " ADMIN
    read -rp "   Anzeigename (z. B. Vor- und Nachname): " ANZEIGE
    .venv/bin/python tools/admin_anlegen.py --benutzer "$ADMIN" --name "${ANZEIGE:-$ADMIN}"
else
    echo "   Es gibt schon $ANZAHL Konto/Konten, nichts zu tun."
fi

if [ "$DIENST" = 1 ]; then
    echo "== systemd-Dienst $DIENSTNAME (braucht sudo)"
    EINHEIT="$(mktemp)"
    sed -e "s|@BENUTZER@|$(id -un)|g" -e "s|@WURZEL@|$WURZEL|g" -e "s|@PORT@|$PORT|g" \
        deploy/wiki-backend.service.vorlage > "$EINHEIT"
    sudo install -m 644 "$EINHEIT" "/etc/systemd/system/$DIENSTNAME.service"
    rm -f "$EINHEIT"
    sudo systemctl daemon-reload
    sudo systemctl enable "$DIENSTNAME"
    sudo systemctl restart "$DIENSTNAME"
    for _ in 1 2 3 4 5 6 7 8 9 10; do
        curl -fsS "http://127.0.0.1:$PORT/api/health" >/dev/null 2>&1 && break
        sleep 1
    done
    if curl -fsS "http://127.0.0.1:$PORT/api/health" >/dev/null 2>&1; then
        echo "   läuft: http://127.0.0.1:$PORT/api/health"
    else
        echo "   Dienst antwortet nicht. Protokoll: journalctl -u $DIENSTNAME -n 50" >&2
        exit 1
    fi
fi

cat <<EOF

Fertig. Für HTTPS fehlt noch Caddy (einmalig, braucht sudo):

    sudo apt install -y caddy
    sudo ufw allow 443/tcp

Block für /etc/caddy/Caddyfile:

    $HOST {
        tls internal
        encode gzip zstd
        reverse_proxy 127.0.0.1:$PORT
        header /api/* Cache-Control "no-store"
    }

Danach: sudo systemctl reload caddy, Stammzertifikat von Caddy auf den Geräten installieren
(/var/lib/caddy/.local/share/caddy/pki/authorities/local/root.crt), dann https://$HOST öffnen.
Updates später mit: bash tools/aktualisieren.sh
EOF
