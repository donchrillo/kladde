# deploy/ — Betrieb

Kladde läuft als ein systemd-Dienst (`<ordnername>-backend`, uvicorn auf `127.0.0.1:<port>`),
der API und gebautes Frontend ausliefert. Davor sitzt Caddy für HTTPS.

- **Einrichten:** `bash tools/installieren.sh` (siehe `README.md`). Die Unit entsteht aus
  `wiki-backend.service.vorlage`, mit Benutzer, Pfad und Port dieser Installation.
- **Updates:** `bash tools/aktualisieren.sh`
- **Zustand:** `systemctl status <ordnername>-backend`, `journalctl -u <ordnername>-backend -f`,
  `curl http://127.0.0.1:8408/api/health`
- **Neustart nach Backend-Änderungen:** `sudo systemctl restart <ordnername>-backend`
- **Caddy:** Block wie im `README.md`, danach `sudo caddy validate --config /etc/caddy/Caddyfile`
  und `sudo systemctl reload caddy`
