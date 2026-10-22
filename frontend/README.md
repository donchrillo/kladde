# frontend/ — React 19 + Vite + Tailwind v4 (PWA)

Installierbare PWA. Spricht das Backend same-origin über `/api` an (im Dev per
Vite-Proxy, in Produktion liefert das Backend `dist/` aus).

## Setup & Start

```bash
npm install
npm run dev        # Vite auf :8418, proxyt /api -> 127.0.0.1:8408
npm run build      # -> dist/
npm run lint
```

> **Secure Context:** Kamera/Sensor-APIs und die PWA-Installation brauchen `https://`
> oder `http://localhost`. Für den LAN-/Handy-Test daher über den Caddy-Host
> (`https://pn40.local`, siehe `deploy/`).

## Layout

```
src/
  main.tsx             Einstiegspunkt (React 19, StrictMode)
  index.css            Tailwind-Import + Basis-Styles + Markdown-Typografie
  App.tsx              Wiki-View: Seitenbaum links, gerenderte Seite rechts
  components/          PageTree.tsx (rekursiver Seitenbaum)
  lib/api-client.ts    zentraler HTTP-Client (relative /api-Pfade)
  lib/markdown.ts      Markdown -> HTML (marked + DOMPurify)
  hooks/useWiki.ts     useSpaces / useSeitenbaum / useSeite
public/                PWA-Icons (Platzhalter — durch eigene ersetzen)
```

## Konventionen

- Alle Backend-Aufrufe über `lib/api-client.ts` (keine verstreuten `fetch`).
- Server-State über Hooks mit klarer State-Maschine (Muster: `hooks/useWiki.ts`).
- Markdown **nie** ungefiltert einsetzen: immer über `lib/markdown.ts` (DOMPurify).
- TypeScript strict; ESLint + `tsc` müssen grün sein.
- Icons in `public/` sind neutrale Platzhalter — durch projekteigene ersetzen
  (Manifest-Einträge in `vite.config.ts`).
