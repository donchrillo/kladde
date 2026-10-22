---
name: wiki
description: Seiten im eigenen Wiki lesen, suchen, anlegen und ändern — über die API als eigener Benutzer für Claude. Nutzen, wenn der User einen Wiki-Eintrag, eine Wiki-Seite oder Doku "ins Wiki" möchte, aus jedem Projekt.
---

# Ins Wiki schreiben

Seiten sind Markdown, hierarchisch (max. 5 Ebenen) und versioniert. Schreiben **nur über die
API** mit dem Skript unten, nie direkt in die Datenbank (sonst fehlen Version und Suchindex).

## Einrichtung (einmalig)

1. Im Wiki als Administrator unter `#/verwaltung` einen Benutzer `claude` **ohne**
   Administratorrecht anlegen und ihm Schreibrecht nur auf die Bereiche geben, in die Claude
   schreiben soll.
2. Diesen Ordner nach `~/.claude/skills/wiki/` kopieren.
3. Zugangsdatei in einem eigenen Terminal anlegen (Passwort nicht in den Chat):

   ```
   mkdir -p ~/.config/wiki && read -rp 'Adresse (z. B. https://pn40.local): ' U && read -rsp 'Passwort von claude: ' P && printf '{"url":"%s","username":"claude","password":"%s"}' "$U" "$P" > ~/.config/wiki/zugang && chmod 600 ~/.config/wiki/zugang; unset P
   ```

Die Zugangsdatei **nie lesen oder ausgeben**, das erledigt das Skript. Fehlt sie, den User
bitten, sie wie oben anzulegen.

## Werkzeug

```bash
S=~/.claude/skills/wiki/wiki.py
python3 $S bereiche
python3 $S baum <bereich-key>                   # id, parent_id, Titel
python3 $S suche "Begriff" [--bereich-id N]
python3 $S lesen <seiten-id>
python3 $S anlegen --bereich-id N --titel "Titel" --datei seite.md [--eltern-id P]
python3 $S aendern <seiten-id> [--titel T] [--datei seite.md] [--eltern-id P]
```

## Ablauf

1. Platz klären: `bereiche` und `baum`, passende Elternseite mit dem User abstimmen.
2. Inhalt als Markdown in eine temporäre Datei schreiben, **ohne** Titelzeile (der Titel ist ein
   eigenes Feld). Keine Passwörter, Tokens oder anderen Zugangsdaten.
3. Vor dem Anlegen die Gliederung vom User bestätigen lassen. Vor `aendern` immer erst `lesen`,
   um den aktuellen Stand nicht zu überschreiben.
4. Link für den User: `<adresse>/#/<bereich-key>/<slug>`.
