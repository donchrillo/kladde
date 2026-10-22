# Beiträge zu Kladde

Danke für dein Interesse! Fehlerberichte und Vorschläge sind als Issue willkommen, Änderungen als
Pull Request aus einem eigenen Fork.

## Rechte an Beiträgen

Kladde steht für alle unter der Lizenz in `LICENSE` (PolyForm Noncommercial 1.0.0). Damit der
Maintainer das Projekt unabhängig davon weiterentwickeln, anders lizenzieren und auch selbst
kommerziell nutzen kann, gilt für jeden Beitrag (Code, Doku, Grafiken):

1. **Du räumst Christian Blass** (Maintainer, GitHub `donchrillo`) **ein einfaches, zeitlich und
   räumlich unbeschränktes, unwiderrufliches und unentgeltliches Nutzungsrecht** an deinem
   Beitrag ein. Es umfasst, den Beitrag zu nutzen, zu verändern, zu veröffentlichen, unter
   beliebigen Lizenzen weiterzugeben (auch kommerziellen) und dieses Recht an Dritte zu
   übertragen oder Unterlizenzen zu erteilen.
2. **Du bestätigst**, dass der Beitrag von dir stammt oder du ihn so einreichen darfst, und dass
   er keine Rechte Dritter verletzt (z. B. fremder Code mit unpassender Lizenz,
   Betriebsgeheimnisse deines Arbeitgebers).
3. Dein Urheberrecht bleibt bestehen. Du darfst deinen Beitrag weiterhin selbst verwenden.
4. Es besteht kein Anspruch darauf, dass ein Beitrag übernommen wird.

Mit dem Einreichen eines Pull Requests stimmst du diesen Bedingungen zu. Bitte schreib dazu in
die Beschreibung des Pull Requests:

> Ich stimme den Bedingungen in CONTRIBUTING.md zu.

## Hinweise für Pull Requests

- Ein Thema pro Pull Request, kurz beschreiben, was und warum.
- Backend: `ruff`, `black` und `pytest` müssen durchlaufen, Schemaänderungen nur mit
  Alembic-Migration.
- Frontend: `npm run lint` und `npm run build` müssen durchlaufen.
- Texte in der Oberfläche und Kommentare auf Deutsch.
