# Datenhaltung — wo und wie die Inhalte liegen

Verständliche Erklärung des Ist-Zustands, auch für Leser ohne Datenbank-Hintergrund.
Technische Details zum Schema stehen zusätzlich in `overview.md`.

## Ein einziger Ort: eine Datenbankdatei

Alles steckt in **einer Datei**: `backend/app.db` (SQLite). Kein Datenbankserver, kein
Cloud-Dienst, kein Netzwerkzugriff. Die Datei kopieren heißt: Backup gemacht.
Vorstellen kann man sich das wie eine Mappe mit mehreren Tabellenblättern — nur dass
das Programm darin auch bei Hunderttausenden Zeilen sofort findet, was es sucht.

Der Pfad ist über `DATABASE_URL` in `.env` änderbar; Standard siehe `backend/src/config.py`.

## Die Tabellen darin

| Tabelle | Was drinsteht |
|---|---|
| `space` | Bereiche — oberste Gliederung, z. B. „IT" |
| `page` | Die Seiten selbst |
| `page_version` | Alte Stände jeder Seite (Historie) |
| `attachment` | Metadaten hochgeladener Dateien (nicht die Datei selbst) |
| `label`, `page_label` | Schlagwörter und ihre Zuordnung zu Seiten |
| `page_link` | Wer verlinkt auf wen |
| `user`, `space_permission` | Konten und Bereichsrechte (Login noch aus) |
| `page_fts` | Volltext-Suchindex (von SQLite gepflegt) |
| `alembic_version` | Merkt sich, welche Migrationen schon gelaufen sind |

## Wie eine Seite gespeichert wird

Eine Zeile in `page` enthält Titel, den **Text als Markdown** (reiner Text mit `#` für
Überschriften, `**fett**` usw. — kein Word-Format, kein HTML), den Kurznamen für die URL
(Slug), die Zugehörigkeit zum Bereich und eine Sortiernummer.

Die Baumstruktur entsteht über **`parent_id`**: Jede Seite zeigt auf ihre Mutterseite.
Es gibt keine Tabellen für „Ebene 1", „Ebene 2" — dadurch ist die Tiefe unbegrenzt und
Verschieben heißt nur, einen einzigen Wert zu ändern.

Der Slug ist **pro Bereich** eindeutig, nicht pro Ebene. Deshalb bleiben Links stabil,
wenn eine Seite im Baum an eine andere Stelle wandert.

## Historie: nichts wird überschrieben

Bei **jedem Speichern** wird eine Kopie von Titel und Text als neue Revision in
`page_version` abgelegt — Revision 1 ist bereits das Anlegen. Die aktuelle Fassung steht
damit doppelt da (in `page` und als jüngste Revision). Das ist Absicht: Anzeigen bleibt
schnell, und die Historie ist lückenlos.

## Anhänge: Datei getrennt von Datenbank

Die **Dateien selbst** liegen im Ordner `backend/attachments/` (Pfad über
`ATTACHMENT_DIR` konfigurierbar), nicht in der Datenbank. In der Tabelle steht nur der
Verweis.

Auf der Platte bekommt jede Datei einen Zufallsnamen (UUID) statt des Originalnamens —
so kann ein präparierter Dateiname weder Pfade verlassen noch etwas überschreiben. Der
lesbare Name für die Anzeige steht in der Tabelle.

Vorteil: Die Datenbank bleibt klein und schnell, und Backups lassen sich getrennt fahren.

> **Fürs Backup wichtig:** Es sind **zwei** Dinge zu sichern — die Datei `app.db` **und**
> der Ordner `attachments/`. Einzeln ist keins von beiden vollständig.

## Suche und Links

- **Suche:** SQLite führt einen eigenen Volltextindex (`page_fts`, FTS5), der bei jedem
  Speichern mitgepflegt wird. Die Suche liest daher nicht alle Seitentexte durch, sondern
  schlägt wie in einem Buchindex nach. Siehe `backend/src/search.py`.
- **Links:** Beim Speichern wird aus dem Markdown ausgelesen, auf welche Seiten verwiesen
  wird, und in `page_link` festgehalten. Damit ist „wer verlinkt hierher?" sofort
  beantwortbar, statt jedes Mal alle Texte zu durchsuchen. Siehe `backend/src/links.py`.

Beide Tabellen sind **abgeleitete Daten** — sie lassen sich jederzeit aus `page` neu
aufbauen und müssen nicht gesondert gesichert werden.

## Schemaänderungen

Die Struktur der Tabellen wird nie von Hand geändert, sondern über **Migrationen**
(Alembic, in `backend/alembic/versions/`). Jede Migration ist ein nachvollziehbarer
Schritt, den man auf einer bestehenden, gefüllten Datenbank ausführen kann, ohne Daten
zu verlieren. Regel aus `CLAUDE.md`: Modelländerung nie ohne begleitende Revision.

## Sicherungskonzept

Weil alles in einer Datei plus einem Ordner liegt, ist die Sicherung einfach — sie muss
nur *konsistent* sein. Ein `cp` der `app.db` während eines Schreibvorgangs kann eine
halbfertige Datei erzeugen. Richtig ist SQLites eigener Online-Backup-Befehl, der auch
im laufenden Betrieb einen sauberen Stand zieht:

```bash
# Variante A: ohne Zusatzsoftware (sqlite3-CLI ist auf diesem Rechner nicht installiert)
python3 -c "import sqlite3,sys; s=sqlite3.connect(sys.argv[1]); d=sqlite3.connect(sys.argv[2]); s.backup(d); d.close()" \
  backend/app.db /pfad/zum/backup/app-$(date +%F).db

# Variante B: mit sqlite3-CLI (apt install sqlite3)
sqlite3 backend/app.db ".backup '/pfad/zum/backup/app-$(date +%F).db'"
```

Danach den Anhang-Ordner dazu, z. B. `rsync -a backend/attachments/ /pfad/zum/backup/attachments/`.

Beides zusammen als täglicher Cronjob, mit Aufbewahrung täglich/wöchentlich/monatlich.
Ein Restore ist ein Zurückkopieren beider Teile — kein
Import, kein Werkzeug nötig.
