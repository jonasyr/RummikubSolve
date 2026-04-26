# Skin-System für Rummikub — Implementation Plan

> Hinweis zum Projektnamen: Der Request spricht von „RomiCub”, das tatsächliche
> Repository heißt **RummikubSolve**. Ich verwende durchgehend den korrekten
> Namen. Sollte das ein bewusster Arbeitstitel gewesen sein, einfach durch
> Suchen/Ersetzen anpassen.

-----

## 0. Vorab: Bestätigte Fakten und verbleibende Unklarheiten

Nach Sichtung der Config-Dateien sind mehrere vorher offene Punkte jetzt
geklärt. Der Vollständigkeit halber hier der Status:

### 0.1 Bestätigter Tech-Stack (aus `package.json` + Configs)

|Komponente                           |Version / Status                                                |Relevanz für das Skin-System                                                                     |
|-------------------------------------|----------------------------------------------------------------|-------------------------------------------------------------------------------------------------|
|Next.js                              |**15.5.15** (App Router)                                        |moderner, `output: "standalone"` für Docker, `reactStrictMode: true`                             |
|React                                |**19**                                                          |Keine Skin-spezifischen Bedenken; moderne Hooks verfügbar                                        |
|Tailwind CSS                         |**3.4** mit `tailwind.config.ts`                                |TypeScript-Config, `theme.extend.colors.tile.*` existiert mit konkreten Hex-Werten (siehe 0.3)   |
|next-intl                            |4.9.1                                                           |i18n-Infrastruktur vollständig vorhanden                                                         |
|Zustand                              |5                                                               |State-Management wie bereits genutzt in `game.ts`, `play.ts`                                     |
|Vitest                               |3.2.4 (jsdom)                                                   |Unit-/Integration-Tests; Setup-File unter `src/__tests__/setup.ts`                               |
|Playwright                           |1.50                                                            |**bereits installiert** mit `npm run e2e` / `e2e:ui`; E2E-Specs leben in `e2e/` (vitest excluded)|
|Storybook                            |**nicht installiert**                                           |Visual Regression läuft über Playwright (wie vorher geplant)                                     |
|next-pwa                             |**nicht installiert**                                           |Es gibt `public/manifest.json`, aber KEINEN Service Worker → Phase 6 wird deutlich einfacher     |
|Validierungs-Libs (zod, pngjs, sharp)|**nicht installiert**                                           |Müssen als neue Dev-Dependencies hinzugefügt werden (siehe Phase 3 und 4)                        |
|ESLint                               |`next/core-web-vitals` + `next/typescript`, keine Custom-Plugins|CI-Guards brauchen eigene Scripts (nicht Eslint-Rule-basiert)                                    |
|TypeScript                           |strict mode + `@/*` Alias → `./src/*`                           |Alle neuen Imports nutzen den Alias für Konsistenz                                               |

### 0.2 Konkrete Default-Tile-Farben aus `tailwind.config.ts`

```ts
colors: {
  tile: {
    blue:   "#1d4ed8",   // Tailwind blue-700
    red:    "#dc2626",   // Tailwind red-600
    black:  "#1f2937",   // Tailwind gray-800
    yellow: "#d97706",   // Tailwind amber-600
  },
}
```

Diese Werte sind die Quelle der Wahrheit für den Default-Skin und werden in
Phase 1 als `CssSkinSpec` verwendet. Text-Farbe bleibt wie bisher: weiß für
blau/rot/schwarz, `text-gray-900` (= `#111827`) für gelb; Joker bleibt
`bg-gray-800` (= `#1f2937`) + `text-yellow-400` (= `#facc15`).

### 0.3 Verbleibende (kleinere) Unklarheiten

|# |Unklarheit                                      |Umgang im Plan                                                                                                                                                           |
|--|------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
|U1|Drag-and-Drop-Skin-Preview im Play-Modus        |`interactionMode="drag"` ist im Play-Store definiert, aber nicht implementiert. Das Skin-System bleibt drag-ready; wenn Drag später kommt, ist das ein No-Op-Integration.|
|U2|Backend-Dockerfile und Frontend-Deployment-Setup|Nicht im Context — der Plan geht davon aus, dass `public/skins/**` einfach mit deployed wird (was bei `output: "standalone"` automatisch passiert).                      |
|U3|CI-Pipeline-Definition (GitHub Actions o.ä.)    |Nicht im Context — die vorgeschlagenen CI-Guards sind in der Form „Script das läuft als Step” formuliert und passen in jedes CI-System.                                  |

### 0.4 Implikationen aus `reactStrictMode: true`

React-Strict-Mode ruft Effects im Dev zweimal auf, um Idempotenz-Bugs
sichtbar zu machen. Das betrifft unseren Skin-Preloader direkt: **jeder
`preload()`-Aufruf muss idempotent sein**. Das Token-basierte Commit-Pattern
(siehe 3.4 / R1) erfüllt das ohnehin; wichtig ist nur, dass neue Phase-3-
Implementierungen keinen Seiteneffekt beim Preload haben, der sich beim
doppelten Aufruf summiert (z.B. Counter hochzählen).

-----

## 1. Repository-Verständnis

### 1.1 Architektur-Überblick

Monorepo mit klarer Frontend/Backend-Trennung:

- **Backend** (`backend/`) — Python, FastAPI, HiGHS-ILP-Solver, SQLite-Pools
  für pregenerierte Puzzle, Telemetry-Store. Produziert rein logische Zustände:
  `(color, number, copy_id, is_joker)`. **Kein Backend-Code berührt
  Darstellung.**
- **Frontend** (`frontend/`) — Next.js 15 App Router, React 19, TypeScript
  (strict), Tailwind CSS 3.4, next-intl (DE/EN), Zustand-Stores. Zwei
  Hauptmodi: Solver (`app/[locale]/page.tsx`) und Play
  (`app/[locale]/play/page.tsx`), außerdem eine Calibration-Page für
  Telemetry-Batches. Docker-Image via `output: "standalone"` (d.h.
  `public/`-Assets werden automatisch in die Runtime bundled).

### 1.2 Rendering-Pipeline der Steine

Der einzige echte Renderer ist **`frontend/src/components/Tile.tsx`**. Diese
Komponente ist das zentrale Artefakt für das Skin-System. Sie rendert aktuell
rein CSS-basiert — es gibt keine Bild-Assets für Steine.

Relevante Ausschnitte (gekürzt):

```tsx
const BG: Record<TileColor, string> = {
  blue:   "bg-tile-blue text-white",
  red:    "bg-tile-red text-white",
  black:  "bg-tile-black text-white",
  yellow: "bg-tile-yellow text-gray-900",
};

const sizeClass =
  size === "xs" ? "w-5 h-6 text-[10px]" :
  size === "sm" ? "w-7 h-8 text-xs"     :
                  "w-9 h-10 text-sm";

const bgClass = isJoker
  ? "bg-gray-800 text-yellow-400"
  : color ? BG[color] : "bg-gray-300 text-gray-600";
```

Props-Schnittstelle: `color, number, isJoker, highlighted, onRemove, size, label, selected, onClick`.

**Nicht-optische Zustände** (Ring-Highlights, Remove-Button, Label-Chip,
cursor-pointer) sind klar vom rein optischen Tile-Kern getrennt. Das ist
wichtig: **nur der Tile-Körper (Hintergrund + Nummer/Stern)** ist Skinning-
Gegenstand. Rings, Buttons, Labels bleiben rein CSS-basiert.

### 1.3 Zweite (kritische) Duplikat-Stelle: `TileGridPicker.tsx`

```tsx
const TILE_BG: Record<TileColor, string> = {
  blue:   "bg-tile-blue text-white",
  red:    "bg-tile-red text-white",
  black:  "bg-tile-black text-white",
  yellow: "bg-tile-yellow text-gray-900",
};
```

Dieselbe Farb-Map als separates Objekt, inline in der Komponente. Der
`TileGridPicker` rendert **bewusst keine `Tile`-Komponenten**, sondern eigene
`<button>`-Elemente — vermutlich weil Tiles dort als Auswahl-Buttons mit
abweichendem Sizing-/Aspect-Ratio-Verhalten dienen (`aspect-[5/6]` +
`clamp()`-Font-Size). Das ist eine klare technische Schuld und die zentrale
Risikostelle für Skin-Drift: wenn der Picker nicht mit dem Rest synchron
bleibt, sieht die App inkonsistent aus.

### 1.4 Alle Verwendungsstellen von `Tile`

|Datei                         |Zweck                                   |Größe       |Besonderheiten                               |
|------------------------------|----------------------------------------|------------|---------------------------------------------|
|`components/RackSection.tsx`  |Solver-Rack                             |md (default)|`onRemove`                                   |
|`components/BoardSection.tsx` |Solver-Board + Set-Builder-Pending-Tiles|sm          |`onRemove` im Builder                        |
|`components/SolutionView.tsx` |Solution-Karten                         |sm          |`highlighted`, `selected`, `onClick`, `label`|
|`components/play/GridCell.tsx`|Play-Grid-Zelle                         |sm          |gekapselt in memoisiertem Cell-Wrapper       |
|`components/play/PlayRack.tsx`|Play-Hand                               |sm          |—                                            |

### 1.5 Datenfluss für Tile-Darstellung

```
Backend (Tile: color, number, copy_id, is_joker)
  → REST-JSON (TileInput/TileOutput)
  → Frontend-Store (game.ts / play.ts)
  → Component-Props
  → Tile.tsx → DOM (CSS classes)
```

**Darstellungsinformation existiert ausschließlich in `Tile.tsx`
(+ `TileGridPicker.tsx`).** Kein Backend-Code, kein Store-Code, kein Type-
System-Code referenziert visuelle Darstellung. Das ist eine
außergewöhnlich saubere Ausgangslage für ein Skin-System.

### 1.6 Aktueller Stand im Kontext von Tests

Die Test-Suite (`__tests__/components/*.test.tsx`) enthält eine große Zahl
an Assertions auf konkrete CSS-Klassen:

- `Tile.test.tsx`: `.w-5`, `.w-7`, `.w-9`, `.ring-2`, `.ring-blue-400`,
  `.ring-yellow-300`, `.cursor-pointer`
- `SolutionView.*.test.tsx`: `.ring-blue-400`
- `PlayGrid.test.tsx`: `.cursor-pointer`, `.border-dashed`, `.ring-blue-500`

Wichtig: **Keiner** dieser Tests assertiert auf `bg-tile-*`-Klassen. Das
Skin-Refactoring bricht also voraussichtlich **null** bestehende Tests,
solange nicht-visuelle Zustände (Rings, Borders, Cursors) CSS-basiert bleiben
— was architektonisch ohnehin das richtige Vorgehen ist.

### 1.7 Build/Deploy-relevante Pfade

- `frontend/public/` — statische Assets, wird in Build kopiert. Unser
  natürlicher Ort für Skin-Assets: `public/skins/<id>/...`.
- `frontend/public/manifest.json` — PWA-Manifest, nicht zu verwechseln
  mit unserem zukünftigen Skin-Manifest.
- `frontend/src/i18n/messages/{de,en}.json` — Übersetzungen, werden für
  Skin-Namen erweitert.

-----

## 2. Ist-Analyse

### 2.1 Was bereits vorhanden ist

- Einzige zentrale Tile-Komponente (`Tile.tsx`)
- Saubere Typisierung (`TileColor`, `TileInput`, `TileOutput`)
- Keine Backend-Kopplung an Darstellung
- Dark-Mode-Unterstützung ist orthogonal zu Tile-Farben (Tile-Farben werden
  im Dark Mode nicht invertiert — das ist beabsichtigt: blau bleibt blau)
- Drei Tile-Größen (xs/sm/md)
- Zustand-basierte UI-State-Verwaltung — leicht erweiterbar um Skin-State
- localStorage-Nutzung bereits etabliert
  (`seenPuzzleIds`, `play:interactionMode`, `calibration:access-granted`)

### 2.2 Was fehlt

- Skin-Abstraktionsschicht
- Skin-Registry / statisches Skin-Inventar
- Skin-Auswahl-UI (Dropdown + Thumbnail-Preview)
- Skin-Persistierung
- Asset-Loading-Pipeline für Bilder
- Fallback-Verhalten bei fehlenden/defekten Skins
- Asset-Validierungs-Tool für selbst erstellte Skins
- i18n-Einträge für Skin-Namen
- Visual-Regression-Tests

### 2.3 Direkt zu ändernde Dateien

|Datei                              |Änderungstyp                                                                                           |
|-----------------------------------|-------------------------------------------------------------------------------------------------------|
|`src/components/Tile.tsx`          |Komplette Render-Logik → Skin-basiert                                                                  |
|`src/components/TileGridPicker.tsx`|Konsolidierung, nutzt dieselbe Skin-Quelle                                                             |
|`src/app/globals.css`              |Optionales CSS-Variablen-Setup                                                                         |
|`src/i18n/messages/{de,en}.json`   |Neue Keys: `skinPicker.*`, Skin-Namen                                                                  |
|`tailwind.config.ts`               |**Kein Change nötig** — `colors.tile.*` bleibt unangetastet und wird vom Default-Skin weiterhin benutzt|
|`package.json`                     |Neue Dev-Deps: `zod` (Manifest-Validierung), `pngjs` oder `sharp` (Asset-Validator-CLI)                |

### 2.4 Indirekt betroffene Dateien

- Alle Komponenten, die `<Tile … />` direkt verwenden (Liste in 1.4):
  müssen nichts ändern, solange die Props-Signatur stabil bleibt.
- `components/ErrorBoundary.tsx` — kein Change nötig, aber
  Skin-Load-Fehler werden in einem Mini-Banner oberhalb angezeigt
  (nicht als globale Boundary).
- `public/manifest.json` (PWA) — keine Änderung.
- Calibration-Page — kein Change nötig, Skin-Auswahl liegt im Header.

### 2.5 Technische Schulden und Migrationsprobleme

1. **Code-Duplikation `BG` vs. `TILE_BG`** — muss in Phase 0 aufgelöst werden.
1. **`Tile`-Props sind mehrfach optional** (color, number können null sein
   — für Placeholder-Darstellung `?`). Das Skin-System muss das sauber
   weiterreichen.
1. **Größenabhängige Font-Sizes sind hardkodiert** in CSS-Klassen. Für
   Sprite-Atlas-Skins wird die Schrift Teil der Bitmap — das ist ok, aber
   für CSS-Skins muss die Font-Größe weiter steuerbar bleiben.
1. **`aspect-[5/6]` im `TileGridPicker`** weicht vom Hauptrenderer ab
   (dort `w-9 h-10` = 9/10 ≈ 10/11). Konsolidierung empfohlen.
1. **Test-Suite asseriert auf CSS-Klassen von nicht-visuellen Zuständen**
   (Rings, Cursor). Diese Zustände bleiben CSS — kein Refactor nötig.

-----

## 3. Zielarchitektur für das Skin-System

### 3.1 Architekturprinzipien

- **Strikte Trennung Logik ↔ Darstellung** — das Skin-System kennt
  `(color, number, isJoker)` als reine Daten. Die Rendering-Entscheidung
  ist Strategie-Pattern pro Skin.
- **Default-Skin = äquivalent zum Ist-Zustand** — der Rollout wird
  vollständig verhaltens-äquivalent begonnen. Keine Visual-Regression
  bevor neue Skins existieren.
- **Skin-Contract ist stabil und dokumentiert** — neue Skins werden
  gegen ein Manifest-Schema validiert.
- **Assets sind statisch und cache-bar** — jedes Skin bekommt eine
  versionierte URL, damit PWA/Browser-Cache deterministisch bleibt.
- **Fail-safe** — defektes/fehlendes Skin → silently Fallback auf Default.

### 3.2 Datenmodell

Die folgenden TypeScript-Typen bilden den Skin-Contract. Sie gehören
nach `src/lib/skins/types.ts`.

```typescript
import type { TileColor } from "../../types/api";

export type SkinId = string;                 // "default", "classic-wood", …
export type SkinKind = "css" | "sprite-atlas";
export type TileSize = "xs" | "sm" | "md";

export interface TileRenderContext {
  color: TileColor | null;                   // null → Placeholder
  number: number | null;                     // 1..13 oder null
  isJoker: boolean;
  size: TileSize;
}

export interface LocalizedText {
  en: string;
  de: string;
}

export interface SpriteAtlasSpec {
  url: string;                               // "/skins/<id>/v<version>/atlas.png"
  tileWidth: number;                         // Atlas-Pixel pro Stein-Breite
  tileHeight: number;                        // Atlas-Pixel pro Stein-Höhe
  grid: {
    cols: number;                            // 13 — Zahlen 1..13
    rows: number;                            // 5 — 4 Farben + Joker
    colorRowOrder: TileColor[];              // ["blue","red","black","yellow"]
    jokerRow: number;                        // 4
    jokerCol: number;                        // 0
  };
}

export interface CssSkinSpec {
  colors: Record<TileColor, { bg: string; fg: string }>; // CSS-Werte (hex/rgb)
  joker: { bg: string; fg: string; symbol: string };     // Symbol meist "★"
  placeholder: { bg: string; fg: string };               // color=null
}

export interface SkinManifest {
  id: SkinId;
  version: string;                           // semver, Bestandteil der URL
  kind: SkinKind;
  displayName: LocalizedText;
  description: LocalizedText;
  author?: string;
  thumbnail: string;                         // "/skins/<id>/v<version>/thumbnail.png"
  sprite?: SpriteAtlasSpec;                  // wenn kind="sprite-atlas"
  css?: CssSkinSpec;                         // wenn kind="css"
}
```

### 3.3 Renderer-Contract

Ein Skin liefert genau einen Renderer:

```typescript
export interface SkinRenderer {
  manifest: SkinManifest;
  /**
   * Liefert die React-Children für das Tile-Innere (Body). Rings,
   * Remove-Buttons, Labels werden vom `Tile`-Wrapper gezeichnet und
   * sind NICHT Teil des Renderers.
   */
  renderTileBody(ctx: TileRenderContext): React.ReactNode;
  /**
   * Liefert die CSS-Klassen oder Inline-Styles für den Tile-Container
   * in der jeweiligen Größe. Der Wrapper kombiniert diese mit den
   * nicht-visuellen Zuständen.
   */
  containerStyle(ctx: TileRenderContext): {
    className?: string;
    style?: React.CSSProperties;
  };
  /** True, sobald dieser Renderer bereit ist, Tiles auszugeben. */
  isReady(): boolean;
  /** Ressourcen preloaden. Resolvt nach Ready. */
  preload(): Promise<void>;
}
```

### 3.4 Lade- und Auswahlmechanismus

```
App-Mount
  ↓
skinStore hydrate: activeSkinId = localStorage ?? "default"
  ↓
registry.resolve(activeSkinId) → SkinRenderer
  ↓
renderer.preload() (async, fire-and-forget bei Default; await bei Sprite)
  ↓
User wechselt Skin → setSkin(newId) → preload → commit
  ↓
Bei Fehler: activeSkinId bleibt, loadState="error", UI zeigt Banner,
           Rendering verwendet currentSkin (alter Skin oder Default)
```

Race-Condition-Schutz: jeder Preload trägt einen Request-Token. Nur das
Ergebnis zum aktuellsten Token wird committed.

### 3.5 Fallback-Verhalten

|Situation                                                  |Verhalten                                                                      |
|-----------------------------------------------------------|-------------------------------------------------------------------------------|
|`activeSkinId` aus localStorage existiert nicht in Registry|silent fallback auf `"default"`, kein Fehler-Banner                            |
|Sprite-Atlas-Image lädt nicht (404, CORS, etc.)            |Fallback auf `"default"`, sichtbarer Dismiss-able Banner mit i18n-String       |
|Sprite-Atlas lädt, aber Größe stimmt nicht mit Manifest    |identisch wie oben, zusätzlich Console-Warnung                                 |
|`"default"` selbst defekt (sollte nie passieren)           |letzter Ausweg: hardkodierter Minimal-Renderer, nur Zahl in Monospace-Container|

### 3.6 Warum Sprite-Atlas statt SVG / per-Tile-PNG?

Verglichen:

|Option                        |Pro                                               |Contra                                                                                           |
|------------------------------|--------------------------------------------------|-------------------------------------------------------------------------------------------------|
|**Per-Tile-PNG** (53 Dateien) |einfach zu ersetzen                               |53 HTTP-Requests, Browser-Request-Pipelining rettet nicht alles, Cache-Invalidation komplex      |
|**Sprite-Atlas-PNG** (1 Datei)|1 Request, perfektes Caching, Procreate-freundlich|Nicht-Skin-Agnostisches Tile-Rendering via `background-position`, Atlas-Maße müssen exakt stimmen|
|**SVG**                       |vektor-skalierbar, winzig                         |Procreate exportiert kein SVG; Konvertierung aus PNG = qualitativ mäßig; komplizierte Pipeline   |
|**per-Tile-SVG inline**       |wie SVG + keine Requests                          |wie SVG, zusätzlich große Bundle-Size wenn inline                                                |

**Entscheidung: Sprite-Atlas-PNG.** Begründung:

1. Einziges Format, das sich aus Procreate ohne Zwischenschritte ergibt
1. Ein Asset → trivialer PWA-Cache
1. `background-image` + `background-position` ist browserübergreifend
   robust und hardware-beschleunigt
1. Skalierung via CSS (`background-size`) liefert akzeptable Qualität,
   wenn der Atlas mindestens @3x der maximal dargestellten Größe ist

Der **Default-Skin** bleibt jedoch ein `css`-Skin, damit die App ohne
jegliche Bild-Assets lauffähig ist und der existierende Look exakt
reproduziert wird.

-----

## 4. Detaillierter Implementierungsplan in Phasen

### Phase 0 — Vorbereitung und Konsolidierung ✅ DONE

**Ziel:** Doppelte Farb-Maps beseitigen, Test-Baseline stabilisieren.

**Konkrete Änderungen:**

1. Neue Datei `src/components/tile-colors.ts`:
   
   ```ts
   import type { TileColor } from "../types/api";
   export const TILE_BG_CLASSES: Record<TileColor, string> = {
     blue:   "bg-tile-blue text-white",
     red:    "bg-tile-red text-white",
     black:  "bg-tile-black text-white",
     yellow: "bg-tile-yellow text-gray-900",
   };
   export const JOKER_BG_CLASSES = "bg-gray-800 text-yellow-400";
   export const PLACEHOLDER_BG_CLASSES = "bg-gray-300 text-gray-600";
   ```
1. `Tile.tsx` und `TileGridPicker.tsx` importieren aus `tile-colors.ts`.
1. `data-tile-color` und `data-tile-joker` Attribute in `Tile.tsx` ergänzen
   (nützlich für Phase 7-Visual-Tests).
1. `data-skin-kind="css"` temporär hardcoded — wird Phase 1 dynamisch.

**Betroffene Dateien:**

- `src/components/Tile.tsx` (Änderung)
- `src/components/TileGridPicker.tsx` (Änderung)
- `src/components/tile-colors.ts` (neu)

**Refactorings:** keine Verhaltensänderung, rein strukturell.

**Risiken:**

- Vergessen, eine Stelle zu aktualisieren — **Maßnahme:** `grep -r "bg-tile-"`
  in CI als Guard (muss nur in `tile-colors.ts` erscheinen).

**Definition of Done:**

- `grep -r "bg-tile-" src/components/ | grep -v tile-colors.ts` ist leer.
- Alle bestehenden Tests laufen grün.
- Manuelles Smoke-Test im Browser: Solver + Play sehen unverändert aus.

**Testanforderungen:**

- Keine neuen Tests erforderlich. Bestehende Tests müssen weiterlaufen.

**GitHub-Issue-Aufteilung:** 1 Issue („Consolidate duplicated tile color
constants and add data-attributes”).

-----

### Phase 1 — Skin-Abstraktion mit transparentem Default ✅ DONE

**Ziel:** `Tile` rendert über einen `SkinRenderer`; Default-Skin produziert
das exakt gleiche DOM wie vorher.

**Konkrete Änderungen:**

1. Neue Dateien (alle Imports nutzen den bestehenden `@/*`-Alias, z.B.
   `import { TileColor } from "@/types/api"`):
- `src/lib/skins/types.ts` (Typen aus Abschnitt 3.2)
- `src/lib/skins/renderer.ts` (Interface `SkinRenderer`)
- `src/lib/skins/css-renderer.ts` (generische CSS-Skin-Implementierung)
- `src/lib/skins/default-skin.ts` (konkrete Instanz mit den
  Klassen aus `tile-colors.ts` — baut auf den in `tailwind.config.ts`
  definierten `tile.{blue,red,black,yellow}` Tokens auf und ist damit
  verhaltens-äquivalent zum Ist-Zustand)
- `src/lib/skins/registry.ts` (Map `id → SkinManifest`; zunächst nur Default)
- `src/lib/skins/context.tsx` (React-Context + Provider,
  `useActiveSkinRenderer()` Hook)
1. `app/[locale]/layout.tsx` wrap’d `NextIntlClientProvider` mit dem neuen
   `SkinProvider`.
1. `Tile.tsx` refactored:
- benutzt `useActiveSkinRenderer()` für `containerStyle` und `renderTileBody`
- Rings / Remove-Button / Label / onClick-Logik bleibt **unverändert**
- der Remove-Button-Layer ist eine Geschwister-Absolute, Skin-unabhängig
1. **React-19-Strict-Mode-Hinweis:** `reactStrictMode: true` in
   `next.config.ts` führt dazu, dass Components in Dev doppelt gemountet
   werden. Der Renderer-Hook muss daher reine Props-Funktionen zurückgeben
   (ohne Side-Effects oder Counter). Für reine CSS-Skins trivial; für
   Sprite-Skins relevant für den Preloader (s. Phase 3).

**Betroffene Dateien:**

- `src/components/Tile.tsx`
- `src/app/[locale]/layout.tsx`

**Neue Dateien:** siehe oben.

**Refactorings:** Tile-Komponente ist jetzt „dumm” — sie kennt nur noch
Zustand, keine Farben.

**Risiken:**

- Verhaltens-Regression nicht sofort sichtbar — **Maßnahme:** DOM-Snapshot-
  Test von `Tile` in allen Permutationen vor und nach dem Refactor.
- `TileGridPicker` nutzt nicht `Tile` — hier muss eine eigene Lösung rein
  (s.u. Phase 5). Vorerst bleibt er unverändert und benutzt
  `tile-colors.ts` weiter.

**Definition of Done:**

- Tile rendert über Renderer-Interface.
- DOM-Snapshots vor/nach sind identisch (bis auf ggf. neue data-Attribute).
- Registry enthält genau 1 Eintrag: `default`.
- `useActiveSkinRenderer()` wirft nicht, wenn Provider fehlt (gibt Default).

**Testanforderungen:**

- Snapshot-Test für alle 12 Permutationen (3 Größen × 4 Farben + Joker +
  Placeholder × highlighted/selected/neutral). Produziert auf Basis der
  aktuellen Implementierung vor dem Refactor einmal die Baseline,
  danach gegenprüfen.
- Existierende `Tile.test.tsx` Assertions müssen unverändert grün sein.

**GitHub-Issue-Aufteilung:**

- Issue „Define skin types and renderer contract”
- Issue „Implement default CSS skin renderer”
- Issue „Add SkinProvider + useActiveSkinRenderer hook”
- Issue „Refactor Tile.tsx to consume skin renderer”

-----

### Phase 2 — Skin-Auswahl-Store + Persistierung ✅ DONE

**Ziel:** Skin per API wechseln, Auswahl überlebt Reload.

**Konkrete Änderungen:**

1. Neue Datei `src/store/skin.ts`:
   
   ```ts
   interface SkinState {
     activeSkinId: SkinId;
     loadState: "idle" | "loading" | "ready" | "error";
     errorMessage: string | null;
     setSkin: (id: SkinId) => Promise<void>;    // orchestriert preload + commit
     retryCurrent: () => Promise<void>;
     reset: () => void;                         // zurück auf default
   }
   ```
   
   Persistenz-Key: `rummikub_active_skin_v1`.
1. Hydrate beim Store-Create:
- Lesen aus localStorage
- Wenn ID nicht in Registry: silent Default
- `loadState = "ready"` (Default ist sofort ready)
1. Dummy-Second-Skin in Registry — `high-contrast` als reiner CSS-Skin
   (noch kein Asset nötig, dient nur der Store-API-Validierung).
1. `SkinProvider` konsumiert Store und liefert den aktuellen Renderer.

**Betroffene Dateien:**

- `src/lib/skins/registry.ts`
- `src/lib/skins/context.tsx`

**Neue Dateien:**

- `src/store/skin.ts`
- `src/lib/skins/high-contrast-skin.ts` (temporärer zweiter CSS-Skin zum
  Testen der Store-API)

**Risiken:**

- Race-Condition: `setSkin('A')` gefolgt von `setSkin('B')`, A’s preload
  resolved zuletzt und überschreibt B — **Maßnahme:** Abort-Token wie im
  Typ-Entwurf in Abschnitt 3.4 beschrieben.
- Korrupter localStorage-Wert — **Maßnahme:** try/catch + Validierung
  gegen Registry.

**Definition of Done:**

- `setSkin("high-contrast")` wechselt sofort, Reload persistiert.
- Test: localStorage mit Garbage füllen, Store hydriert sauber.
- Test: Schneller Doppelwechsel verliert keine Konsistenz.

**Testanforderungen:** Unit-Tests für den Store (4 Cases: happy, corrupted
localStorage, unknown id, race).

**GitHub-Issue-Aufteilung:** 1 Issue mit klaren Akzeptanzkriterien.

-----

### Phase 3 — Sprite-Atlas-Renderer + Preloader ✅ DONE

**Ziel:** Infrastruktur für bildbasierte Skins, noch ohne reales Asset.

**Konkrete Änderungen:**

1. Neue Datei `src/lib/skins/sprite-atlas-renderer.ts`:
- Implementiert `SkinRenderer`
- `renderTileBody()` gibt `<div style={{backgroundImage, backgroundPosition, backgroundSize}} />` zurück
- `containerStyle()` liefert Größen-abhängige CSS (`width`, `height`)
- `preload()` lädt `new Image()`, resolvt on `load`, rejectet on `error`
1. Neue Datei `src/lib/skins/preloader.ts`:
- generischer `preloadImage(url, timeoutMs)` mit Promise + AbortController
- **Idempotenz-Garantie** (wg. React-19-StrictMode-Double-Invocation):
  ein modulweiter `Map<url, Promise>`-Cache stellt sicher, dass
  `preloadImage(sameUrl)` denselben Promise zurückgibt — auch wenn Strict
  Mode den umgebenden Effect zweimal aufruft.
1. HiDPI-Logik (im Renderer oder Preloader):
- `tileWidth` im Manifest ist die Atlas-Quelle
- CSS-Rendering-Size kommt aus Tile-Size (xs/sm/md) × Pixel-Basis
- `background-size` wird so gesetzt, dass Atlas auf Rendering-Skalar
  skaliert
1. Registry erweitert um Manifest-Schema-Validierung. **Neue Dev-Dependency:
   `zod`** (ca. 12 KB gzipped, typsicher, runtime-prüfbar). Alternativ ein
   handgeschriebener Validator — bei nur einem Schema (Skin-Manifest) ist
   das auch akzeptabel, aber `zod` macht den Schema-Generator für Phase 6
   CI-Guards trivial und skaliert mit, wenn später weitere Schemas dazukommen.
   **Empfehlung:** `zod` installieren.

**Betroffene Dateien:** —

**Neue Dateien:** siehe oben + eine Fixture-JSON für Tests.

**Refactorings:** keine.

**Risiken:**

- `background-position` Pixel-Drift bei Subpixel-Rendering auf HiDPI —
  **Maßnahme:** alle Positionen exakt `-col * tileWidth`, niemals
  fractional.
- Image-Load-Hang (Server antwortet nicht) — **Maßnahme:** Timeout
  im Preloader (z.B. 5 s).
- CORS: falls Assets von separater CDN kommen — **Maßnahme:** `crossOrigin = "anonymous"`
  setzen, auf /public/ keine Relevanz.

**Definition of Done:**

- Sprite-Renderer besteht Unit-Tests mit Dummy-Atlas (1×1 px PNG data-URI
  reicht).
- Preloader resolvt auf 200, rejected auf 404 und auf Timeout.

**Testanforderungen:** Unit-Tests für Preloader (200/404/timeout/abort) und
für Sprite-Position-Berechnung (alle 53 Tiles × 3 Größen, jeweils
`background-position` vergleichen).

**GitHub-Issue-Aufteilung:**

- Issue „Add image preloader utility”
- Issue „Implement sprite-atlas skin renderer”
- Issue „Add manifest schema validation”

-----

### Phase 4 — Asset-Pipeline und erste Procreate-Integration

**Ziel:** Einen vollständigen, vom User in Procreate erstellten Skin
end-to-end im Produkt haben.

**Konkrete Änderungen:**

1. Asset-Konventionen (Details in Abschnitt 5) finalisieren.
1. Verzeichnisstruktur:
   
   ```
   frontend/public/skins/
     classic-wood/
       v1.0.0/
         atlas.png
         thumbnail.png
         manifest.json
   ```
1. Validierungs-CLI `scripts/validate-skin.mjs`:
- Liest `manifest.json`
- Prüft `atlas.png` existiert, Maße = `grid.cols*tileWidth × grid.rows*tileHeight`
- Prüft Alpha-Kanal vorhanden
- Warnt, falls die Mitte einer Tile-Zelle vollständig transparent ist
- Warnt, falls Pixel am Zellrand nicht transparent sind (Bleeding-Check)
- **Neue Dev-Dependency: `pngjs`** (schlank, zero-config) ODER `sharp`
  (mächtiger, aber native Build). **Empfehlung:** `pngjs` — genügt für
  Pixel-Inspektion und vermeidet platform-spezifische Node-Module.
1. Skript-Einträge in `package.json` (`scripts` Block):
   
   ```json
   "validate:skin": "node scripts/validate-skin.mjs",
   "validate:all-skins": "node scripts/validate-skin.mjs --all"
   ```
   
   Das bestehende `scripts`-Objekt enthält bereits `lint`, `type-check`,
   `test`, `e2e` usw. — wir erweitern es, nicht mehr.
1. Registry ergänzt um den neuen Skin (statischer Import des Manifests).

**Betroffene Dateien:**

- `src/lib/skins/registry.ts`
- `package.json`

**Neue Dateien:**

- `frontend/public/skins/classic-wood/v1.0.0/atlas.png` (vom User
  produziert — siehe Abschnitt 5)
- `frontend/public/skins/classic-wood/v1.0.0/thumbnail.png`
- `frontend/public/skins/classic-wood/v1.0.0/manifest.json`
- `scripts/validate-skin.mjs`

**Risiken:**

- Asset-Mismatch (falsches Layout, falsche Maße) — **Maßnahme:**
  Validierungs-CLI in `npm run check` mit aufnehmen.
- Vergessenes Version-Bump führt zu stale Browser-Cache — **Maßnahme:**
  Pfad enthält Version, Manifest-URL ist versioniert.

**Definition of Done:**

- Skin ist im Dropdown auswählbar, wird korrekt gerendert.
- `npm run validate:skin classic-wood` ist grün.
- Sichtprüfung aller 53 Tiles in allen 3 Größen.

**Testanforderungen:**

- Visuelle Stichproben in Playwright: Referenzbild pro Tile-Größe für
  den ausgewählten Skin.

**GitHub-Issue-Aufteilung:**

- Issue „Define asset pipeline conventions and validation CLI”
- Issue „Add classic-wood skin (assets + manifest + registry entry)”

-----

### Phase 5 — Skin-Auswahl-UI

**Ziel:** User kann Skin in beiden Modi wechseln.

**Konkrete Änderungen:**

1. Neue Komponente `src/components/SkinPicker.tsx`:
- Dropdown mit Thumbnail-Preview
- i18n-Namen
- Live-Switch (keine Modal-Bestätigung nötig)
- Anzeige `loadState` (Spinner während Preload)
1. Integration:
- Im Solver-Header neben `LocaleSwitcher`
- Im Play-Modus in `ControlBar.tsx` (als kleiner Button oder Kebab-Menü,
  je nach Platz auf Mobile)
1. i18n-Einträge in `messages/de.json` und `messages/en.json`:
   
   ```json
   "skinPicker": {
     "label": "Tile style",
     "current": "Current: {name}",
     "loading": "Loading skin…",
     "error": "Could not load skin — reverted to default.",
     "skins": {
       "default": { "name": "Default", "description": "Standard colored tiles" },
       "classic-wood": { "name": "Classic Wood", "description": "Hand-painted wooden tiles" }
     }
   }
   ```
   
   (Struktur gleich in de-Datei.)
1. `TileGridPicker` konsolidieren: statt eigener `<button>` mit `TILE_BG`
   soll er die `Tile`-Komponente nutzen mit einem zusätzlichen
   `variant="picker"` Prop (nutzt denselben Skin, aber mit `aspect-[5/6]`
   und disabled-overlay). **Alternative** (falls das Aspect-Ratio-Verhalten
   zu viel Umbau erfordert): `TileGridPicker` rendert stattdessen einen
   neuen `<TileThumbnail />` Wrapper, der intern den aktuellen Skin-
   Renderer nutzt.

**Betroffene Dateien:**

- `src/components/TileGridPicker.tsx`
- `src/app/[locale]/page.tsx` (Header)
- `src/components/play/ControlBar.tsx`
- `src/i18n/messages/{de,en}.json`

**Neue Dateien:**

- `src/components/SkinPicker.tsx`

**Risiken:**

- Layout-Regression im Solver-Header (wrap-Verhalten auf Mobile) —
  **Maßnahme:** manuelle Tests bei 320 px Viewport + Playwright-Check.
- Performance: `TileGridPicker` rendert 4×13 = 52 Tiles, alle mit
  Skin-Renderer. Bei Sprite-Atlas ist das weiterhin 1 Asset — ok.
- i18n-Keys für dynamische Skin-IDs: `t(\`skinPicker.skins.${id}.name`)` ist
  next-intl-kompatibel, aber Compiler-TS-Check erkennt fehlende Keys nicht.
  **Maßnahme:** CI-Script, das alle Registry-Skin-IDs gegen beide i18n-
  Dateien prüft.

**Definition of Done:**

- Picker in beiden Modi sichtbar und funktional.
- Wechsel in Solver-Modus → geht zurück zu Play → Auswahl persistiert.
- Tastatur-Navigation funktioniert (button + dropdown aria-*).

**Testanforderungen:**

- Component-Test `SkinPicker.test.tsx` (Render-States, Click → Store).
- Integration-Test „Skin-Wechsel propagiert auf alle Tile-Instanzen”.

**GitHub-Issue-Aufteilung:**

- Issue „Build SkinPicker component”
- Issue „Integrate SkinPicker into Solver and Play headers”
- Issue „Refactor TileGridPicker to use active skin renderer”
- Issue „Add i18n keys and CI guard for skin names”

-----

### Phase 6 — Performance & Caching

**Ziel:** Keine sichtbaren Tile-Flashes bei Initial-Load, saubere HTTP-
Cache-Header.

> **Vereinfachung gegenüber der ursprünglichen Annahme:** Das Projekt nutzt
> **kein `next-pwa`** und hat keinen Service Worker. Es existiert zwar eine
> `public/manifest.json` (PWA-Manifest für Home-Screen-Install), aber keine
> Runtime-Cache-Strategie. Wir müssen uns daher nur um HTTP-Header und
> Preload-Hints kümmern — deutlich einfacher als geplant.

**Konkrete Änderungen:**

1. Prefetch des aktiven Skins im Root-Layout via
   `<link rel="preload" as="image" href={atlasUrl} />` (SSR-freundlich).
   Bei Default-Skin (CSS) entfällt das.
1. Background-Preload aller Registry-Skins nach `window.requestIdleCallback`
   mit Fallback auf `setTimeout(..., 2000)` für Safari
   (Thumbnails zuerst, Atlas danach).
1. Cache-Headers für unveränderliche Asset-Pfade — am saubersten über die
   `headers()`-Function in `next.config.ts`:
   
   ```ts
   async headers() {
     return [{
       source: "/skins/:path*",
       headers: [{
         key: "Cache-Control",
         value: "public, max-age=31536000, immutable",
       }],
     }];
   }
   ```
   
   Funktioniert sowohl im Standalone-Build (Docker) als auch auf Vercel.
1. Bundle-Analyzer-Check: Manifeste inline ok (JSON in Registry-Modulen),
   Atlas-PNGs **nicht** im Haupt-Bundle (stattdessen aus `public/` via URL).
1. Standalone-Output-Check: `output: "standalone"` kopiert `public/` mit
   ins Runtime-Image — keine zusätzliche Docker-Copy-Zeile nötig. Einmal
   per Build verifizieren, dass `/skins/default/...` oder `/skins/<id>/...`
   im Container unter `/app/public/skins/` ankommt.

**Betroffene Dateien:**

- `src/app/[locale]/layout.tsx`
- `next.config.ts` (`headers()` ergänzen)

**Risiken:**

- Versehentlicher PNG-Import in Bundle (`import atlasUrl from "./atlas.png"`
  wäre Bundle-Inlining) — **Maßnahme:** Skin-Manifest referenziert nur
  String-URLs, nie `import`.
- Prefetch blockiert LCP — **Maßnahme:** nur aktiver Skin eager, Rest idle.
- `requestIdleCallback` nicht in Safari verfügbar — **Maßnahme:** Fallback
  auf `setTimeout` (oben bereits erwähnt).

**Definition of Done:**

- Lighthouse-Score (Performance) nicht schlechter als vor dem Skin-System.
- Reload auf langsamer Verbindung zeigt den Skin sofort oder mit Default-
  Fallback, niemals mit weißem Quadrat.
- Curl auf `/skins/classic-wood/v1.0.0/atlas.png` liefert den
  `Cache-Control`-Header korrekt aus.

**Testanforderungen:**

- Manueller Throttle-Test (Slow 3G in Chrome DevTools).
- Bundle-Size-Diff im Build-Log (vorher/nachher).
- HTTP-Header-Check per curl oder Playwright.

**GitHub-Issue-Aufteilung:** 1 Issue, ggf. aufgesplittet in
„Preload-hints and idle background preload” und „Cache-Control headers
via next.config.ts”.

-----

### Phase 7 — Tests und Visual Regression

**Ziel:** Das System bleibt nachhaltig korrekt, Skin-Änderungen sind
kontrolliert.

> **Status der Infrastruktur:** Playwright 1.50 ist bereits als
> Dev-Dependency installiert, `npm run e2e` und `npm run e2e:ui` existieren
> als Scripts, und `vitest.config.ts` schließt das `e2e/`-Verzeichnis
> explizit aus. Das heißt: wir brauchen weder neue Test-Frameworks noch
> Storybook. Einzig `e2e/` muss neu angelegt werden (oder bereits
> vorhanden — nicht ersichtlich aus dem Context), und ggf. eine
> `playwright.config.ts` im Repo-Root bzw. in `frontend/`.

**Konkrete Änderungen:**

1. Playwright-Visual-Tests unter `e2e/skins/`:
- Pro Skin × pro Größe × pro Tile-Identität ein Screenshot
- Playwrights eingebauter `toHaveScreenshot()` Matcher
- Baseline als `.png` im Repo committed; Diff-Gate in CI
- Test-Harness-Page unter `app/[locale]/_test-harness/skins/page.tsx`
  (nur in dev / test-Build — per ENV-Gate ausblenden)
1. Unit-Tests (Vitest, jsdom — bestehende Infrastruktur):
- Skin-Store (4 Szenarien — s. Phase 2)
- Preloader (4 Szenarien — s. Phase 3)
- Sprite-Position-Berechnung (mathematisch)
1. Integration-Tests (Vitest + Testing Library):
- Skin-Wechsel updated alle Tile-Instanzen synchron (ein Re-Render)
- Skin-Asset-404 → Default-Fallback + Banner
1. E2E-Testcase (Playwright):
- User öffnet Solver, wählt Skin, reloadet, Skin ist noch aktiv.

**Betroffene Dateien:**

- `src/__tests__/**` (neue Vitest-Specs)
- `e2e/skins/**` (neue Playwright-Specs)
- `playwright.config.ts` (anlegen falls nicht vorhanden)

**Risiken:**

- Flaky Pixel-Diffs — **Maßnahme:** `toHaveScreenshot({ maxDiffPixelRatio: 0.001 })` als Toleranz, Font-Loading deterministisch (z.B. via
  `fonts.ready` await vor Screenshot).
- Headless Chromium rendert Schriften minimal anders als lokales macOS —
  **Maßnahme:** Baselines im CI erzeugen, nicht lokal.
- CI-Runtime steigt — **Maßnahme:** Visual-Tests nur auf main + PR gegen
  main, nicht auf Feature-Branches (Workflow-Trigger-Filter).

**Definition of Done:**

- `npm test` grün.
- `npm run e2e` grün, mit Screenshot-Baselines im Repo.
- CI-Gate gegen Visual-Regressions aktiv.

**GitHub-Issue-Aufteilung:**

- Issue „Add Playwright visual regression suite”
- Issue „Store / preloader / position unit tests”
- Issue „E2E: skin switch persists across reload”

-----

## 5. Asset-Pipeline für Procreate

### 5.1 Empfohlene Strategie: Single Sprite Atlas pro Skin

Begründung in 3.6. Kurzfassung: ein PNG, ein Manifest, Versionierung
über den Pfad.

### 5.2 Exakte Leinwand- und Tile-Größe

**Basis-Entscheidung:** Atlas-Tile-Größe 120 × 135 px.

**Herleitung:**

- Maximal dargestellte Tile-Größe in der App ist `size="md"` →
  `w-9 h-10` = 36 × 40 CSS-px (= Tailwind-Standard `4px`-Einheit).
- @3x für Retina-Displays → 108 × 120 physische Pixel minimum.
- Aufgerundet auf „glatte” Werte zum Arbeiten in Procreate: **120 × 135 px**.
- Verhältnis 8 : 9 ≈ 1 : 1.125 — angenehm nah am echten Rummikub-Stein
  (real ca. 1 : 1.3, aber quadrat-näher passt besser zum kompakten UI-Layout).

**Atlas-Gesamtgröße:**

- 13 Spalten × 5 Zeilen → `1560 × 675` Pixel.
- Deutlich unter Procreate’s 16384 × 4096 Limit.

### 5.3 Aufbau der Atlas-Datei

```
    col 0   col 1   col 2   ...   col 12
   +-------+-------+-------+-----+-------+
r0 | blue1 | blue2 | blue3 | ... |blue13 |
   +-------+-------+-------+-----+-------+
r1 | red 1 | red 2 | red 3 | ... |red 13 |
   +-------+-------+-------+-----+-------+
r2 |black1 |black2 |black3 | ... |black13|
   +-------+-------+-------+-----+-------+
r3 |yell 1 |yell 2 |yell 3 | ... |yell13 |
   +-------+-------+-------+-----+-------+
r4 | JOKER |       |       | ... |       |
   +-------+-------+-------+-----+-------+
```

- Jede Zelle ist **exakt** 120 × 135 px.
- **Keine** Zellränder, Gitterlinien oder Shared-Pixels zwischen Zellen.
- Die Zellen 1..12 in Row 4 sind transparent (reserviert für zukünftige
  Joker-Varianten oder Sonderzeichen).

### 5.4 Sicherheits-Padding / Bleeding-Vermeidung

Wichtig, weil `background-position` beim Skalieren in manchen Browsern
Subpixel-Artefakte von Nachbarzellen zieht:

- **2 px Padding** innerhalb jeder Zelle — die effektive sichtbare
  Zeichen-Fläche ist **116 × 131 px** (zwischen px 2 und px 118
  horizontal, 2 und 133 vertikal).
- **Die äußere 2-px-Bordüre jeder Zelle muss vollständig transparent sein.**
- Schatten, Glows, Outlines auf den Steinen dürfen den Padding-Rand nicht
  überschreiten.

Das Validierungs-Script überprüft beides automatisch (s. 5.10).

### 5.5 Transparenz-Regeln

- Der Hintergrund außerhalb des Steins ist **voll transparent** (Alpha = 0).
- Der Stein selbst muss an der Unterseite **mindestens 1 Pixel deckend**
  haben (sonst verschwindet er optisch), außer bei explizit gewolltem
  Stil.
- Weiche Schatten unterhalb des Steins sind erlaubt, müssen aber innerhalb
  der Zelle bleiben.

### 5.6 Procreate-Setup

**Canvas erstellen:**

- Neues Bild → Benutzerdefiniert
- Breite: 1560 px, Höhe: 675 px
- DPI: 300 (reine Metadaten, egal für Rendering)
- Farbprofil: **sRGB** (wichtig — nicht DisplayP3, das macht auf Nicht-Mac-
  Browsern inkonsistente Farben)
- Hintergrundfarbe: **Transparent** (Häkchen unten setzen)

**Hilfslinien:**

- Zeichenhilfe → 2D-Raster
- Rastergröße: 120 × 120 **oder** über ein reference-Layer ein exportiertes
  Grid aus unserem Validation-Tool einfügen (empfohlen — garantiert exakte
  Ausrichtung).
- Grid-Layer stets ganz oben, vor Export **unsichtbar** schalten.

**Layer-Struktur (empfohlen):**

```
📁 _grid-reference         ← Hilfs-Raster, vor Export unsichtbar
📁 blue/
   ├─ blue-01
   ├─ blue-02
   ├─ ...
   └─ blue-13
📁 red/
📁 black/
📁 yellow/
📁 joker/
   └─ joker
```

Die flache Alternative (ein Layer pro Tile ohne Gruppe) geht auch, ist
aber bei 53 Tiles unübersichtlich. Gruppen lassen sich in Procreate
ausblenden, um einzelne Farben isoliert zu überarbeiten.

### 5.7 Namenskonventionen

|Ebene                   |Konvention                                                      |
|------------------------|----------------------------------------------------------------|
|Master-Datei (Procreate)|`skin-<id>-v<x.y.z>-master.procreate`                           |
|Atlas-Export            |`atlas.png`                                                     |
|Thumbnail-Export        |`thumbnail.png` (96 × 96 px, freiwählbares Motiv)               |
|Manifest                |`manifest.json`                                                 |
|Pfad                    |`public/skins/<id>/v<x.y.z>/…`                                  |
|Layer-Namen             |`<color>-<number>` z.B. `blue-07`, `joker`                      |
|Skin-ID                 |`kebab-case`, keine Umlaute, keine Version; Version lebt separat|

**Warum Zero-Padding bei Zahlen (`blue-07` statt `blue-7`)?**
Procreate sortiert Layer alphabetisch — ohne Padding steht `blue-10`
zwischen `blue-1` und `blue-2`, was bei visuellem Scroll verwirrt.

### 5.8 Export-Einstellungen in Procreate

- Aktionen → Teilen → **PNG** (nicht JPG — Alpha-Verlust)
- Qualität: unbeeinflusst (PNG ist lossless)
- Vorher: Grid-Referenz-Layer-Sichtbarkeit auf **aus**

**Selbst-Check vor dem Export:**

1. Datei → Canvas-Informationen öffnen — Größe muss exakt 1560 × 675 px sein.
1. Alle Farb-Gruppen sichtbar?
1. Grid-Layer unsichtbar?
1. Hintergrund-Farbe unsichtbar (transparent)?

### 5.9 HiDPI / Retina / Mipmapping

- Der 120 × 135-Tile-Atlas ist **bereits @3x** der maximalen App-Größe.
- Browser-Rendering skaliert den Atlas über `background-size` herunter —
  in modernen Browsern (Chrome, Safari, Firefox, Edge 2023+) qualitativ
  hervorragend.
- Separate @1x/@2x/@3x Varianten sind **nicht nötig**; der Bandbreiten-
  Unterschied zwischen 1560 × 675 und 520 × 225 PNG ist bei
  verlustfreier Kompression gering (≈ 3-5× statt der erwarteten 9×).
- Mipmapping wird vom Browser automatisch gemacht — kein Custom-Code.

### 5.10 Validierungs-Tool

Script `scripts/validate-skin.mjs` prüft:

1. **Dateien existieren:** `manifest.json`, `atlas.png`, `thumbnail.png`.
1. **Manifest-Schema korrekt** (via zod oder handgeschrieben).
1. **Atlas-Maße** = `grid.cols * tileWidth` × `grid.rows * tileHeight`.
1. **Alpha-Kanal vorhanden** (PNG mit RGBA).
1. **Bleeding-Check:** die 2-Pixel-Bordüre jeder Zelle ist vollständig
   transparent (Alpha < 10 an jedem Rand-Pixel).
1. **Coverage-Check:** jede Tile-Zelle in Rows 0..3 hat mindestens
   einen Nicht-transparenten-Pixel im inneren 60×60-Quadrat (sonst ist
   der Tile vermutlich leer/vergessen).
1. **Joker-Zelle:** (jokerRow, jokerCol) erfüllt denselben Coverage-Check.
1. **Warnings** (Fail nicht, aber Output):
- Atlas-Datei > 1 MB (Performance-Hinweis)
- Thumbnail nicht quadratisch

Implementation nutzt `pngjs` oder `sharp` — beides im Node-Ökosystem
Standard.

Aufruf:

```
cd frontend
npm run validate:skin classic-wood v1.0.0
```

CI-Integration: Pre-Commit-Hook **plus** CI-Step, der alle Skins in
`public/skins/**` validiert.

### 5.11 Beispiel-Manifest (full)

```json
{
  "id": "classic-wood",
  "version": "1.0.0",
  "kind": "sprite-atlas",
  "displayName": {
    "en": "Classic Wood",
    "de": "Klassisches Holz"
  },
  "description": {
    "en": "Hand-painted wooden tiles with worn edges.",
    "de": "Handgemalte Holz-Steine mit abgegriffenen Kanten."
  },
  "author": "Jonas",
  "thumbnail": "/skins/classic-wood/v1.0.0/thumbnail.png",
  "sprite": {
    "url": "/skins/classic-wood/v1.0.0/atlas.png",
    "tileWidth": 120,
    "tileHeight": 135,
    "grid": {
      "cols": 13,
      "rows": 5,
      "colorRowOrder": ["blue", "red", "black", "yellow"],
      "jokerRow": 4,
      "jokerCol": 0
    }
  }
}
```

### 5.12 Typische Fehlerquellen (aus Erfahrung)

|Fehler                                               |Symptom                                       |Abhilfe                                                               |
|-----------------------------------------------------|----------------------------------------------|----------------------------------------------------------------------|
|Falsche Canvas-Größe (z.B. aus Template kopiert)     |Validation fehlschlägt                        |Größe erstmal im Validator prüfen                                     |
|Hintergrund **weiß** statt transparent               |Steine haben weiße Ränder                     |Canvas-Hintergrund auf transparent                                    |
|Drop-Shadow ragt aus Zelle                           |Beim Rendering Artefakte zwischen Nachbartiles|Shadow innerhalb Padding halten                                       |
|JPG statt PNG exportiert                             |Kein Alpha, Steine haben weiße Artefakte      |PNG erzwingen                                                         |
|Layer „_grid-reference” versehentlich sichtbar       |Grid-Linien im Produktions-Asset              |Vor Export prüfen                                                     |
|Version im Pfad nicht bumped                         |Browser zeigt alten Atlas                     |Semver-Bump + Manifest.version + Pfad syncen                          |
|Zahl-Reihenfolge falsch (z.B. bei manuellem Kopieren)|Tile zeigt falsche Nummer                     |Eigener Spotcheck: PNG in Browser öffnen, überprüfen ob row/col stimmt|
|sRGB vs. Display-P3                                  |Farben wirken auf anderen Geräten anders      |Farbprofil in Procreate checken                                       |
|Alpha-Premultiplied vs. Straight                     |Kantentransparenz sieht schmutzig aus         |PNG-Export verwendet Straight-Alpha (Standard bei Procreate)          |

-----

## 6. Test- und Qualitätssicherung

### 6.1 Unit-Tests

|Modul                            |Test-Szenarien                                                                                                                              |
|---------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------|
|`store/skin`                     |Initial state, hydrate valid ID, hydrate unknown ID, hydrate corrupted, setSkin happy, setSkin rapid-double (race), retryCurrent nach Fehler|
|`lib/skins/preloader`            |success, 404, timeout, abort, Netzwerk-Fehler                                                                                               |
|`lib/skins/sprite-atlas-renderer`|Position-Berechnung für alle 53 Tiles, alle 3 Größen, Placeholder, Joker                                                                    |
|`lib/skins/registry`             |resolve known id, resolve unknown (→ default), schema validation reject                                                                     |
|`components/SkinPicker`          |render all states (idle/loading/ready/error), Click → setSkin call, aria-Attribute                                                          |

### 6.2 Integration-Tests

- `Tile` + `SkinProvider` mit Default-Skin → DOM wie vor dem Refactor
  (DOM-Snapshot-Vergleich)
- `Tile` mit Sprite-Skin → `style.backgroundImage` korrekt gesetzt
- Skin-Wechsel im Provider → alle Tile-Instanzen re-rendern einmalig
- Missing-Asset-Fallback: `window.fetch` stub → 404 → Store loadState=error,
  Tile rendert mit Default

### 6.3 Visual-Regression-Tests

- Test-Page `/test-harness/skins` (nur in dev/test-Build) mit allen
  Permutationen als Grid
- Playwright-Screenshot pro Skin
- Baseline committed als `__visual__/skins-<id>.png`
- CI-Gate: Pixel-Diff-Toleranz 0.1 %

### 6.4 Manuelle Testfälle

1. Solver-Modus: Skin wechseln → Rack, Board, Solution alle konsistent.
1. Play-Modus: Skin wechseln → Grid, Rack, SolvedBanner alle konsistent.
1. Solver-Calibration-Modus: Skin wechseln funktioniert.
1. Schneller Doppelwechsel (Klick-Klick in <200 ms) → keine inkonsistente
   Mischung.
1. localStorage via DevTools manuell auf bogus String setzen → Reload → Default.
1. `/skins/classic-wood/v1.0.0/atlas.png` im DevTools blocken → Fallback +
   Banner.
1. Throttle „Slow 3G” → kein visueller Flash, Default-Rendering während
   Load.
1. Safari iOS / Chrome Android / Firefox Desktop Sichttest.

### 6.5 Edge Cases

- `color=null, number=null, isJoker=false` (Placeholder in Tile.test.tsx)
- Tile sowohl `selected` als auch `highlighted` → blau gewinnt (wie jetzt)
- Tile `onClick` während Skin-Load → Click ignoriert? Nein, Click ist
  Skin-unabhängig
- Skin mit zerschnittenem/halb-fehlendem Atlas → Validator fängt vor Deploy

### 6.6 Fehlerbehandlung

- Jede Fehler-Pfad in Store/Preloader produziert **strukturiertes** Error-
  Objekt, nicht nur Strings. UI zeigt übersetzten Text.
- Keine Errors auf die globale ErrorBoundary durchreichen — das würde
  die ganze App abstürzen lassen; Skin-Fehler sind lokal.

### 6.7 Performance-Checks

- Bundle-Analyzer nach Phase 6 → Atlas-PNGs **nicht** in JS-Bundle.
- Lighthouse Performance vor/nach, muss mindestens gleich sein.
- `React.memo` auf `Tile.tsx` (falls nicht bereits) um Re-Renders bei
  Skin-Wechsel auf Liste-Ebene zu minimieren.
- Profile-Check: Frame-Rate beim Drag (zukünftig) und beim großen
  `TileGridPicker` bleiben ≥ 60 fps.

-----

## 7. Risiken und technische Fallstricke

### R1 — Race Conditions bei Skin-Load

Beschreibung: User klickt A → B → A in 100 ms. Ohne Token-Schutz kann
B’s Preload-Success den aktuellen A-State überschreiben.
Gegenmaßnahme: Jeder `setSkin`-Aufruf bekommt einen monoton wachsenden
Token. Preload-Result wird nur committed, wenn Token `===` dem letzten
gesetzten Token. Tests in Phase 2.

### R2 — localStorage-Korruption / Migrations-Lücke

Beschreibung: User hat in localStorage eine Skin-ID, die inzwischen aus
der Registry entfernt wurde.
Gegenmaßnahme: Hydration validiert gegen Registry; unbekannte ID →
silent Default. Versioning-Key (`rummikub_active_skin_v1`) erlaubt
zukünftige Migration (v2) ohne Konflikt.

### R3 — Sprite-Atlas-Caching nach Version-Bump

Beschreibung: Atlas-Update ohne Pfadänderung, Browser/PWA cached alten
Atlas.
Gegenmaßnahme: Version ist **Bestandteil des Pfads** (`v1.0.0`). Neue
Version = neuer Pfad = Cache-Miss = frischer Fetch.

### R4 — Visual-Regression unerkannt

Beschreibung: Skin-Änderung sieht okay aus auf Dev-Maschine, bricht
auf Retina/Android.
Gegenmaßnahme: Playwright-Suite läuft in mehreren Viewport/DPR-
Kombinationen (mindestens 1× und 2× DPR, Mobile + Desktop).

### R5 — Tailwind-Config-Drift

Beschreibung: Jemand fügt später eine neue `bg-tile-*`-Klasse außerhalb
des Default-Skins hinzu (z.B. in einer neuen Komponente), die dann
skin-unabhängig immer die Default-Farben zeigt — das bricht die
Logik-Darstellung-Trennung still.
Gegenmaßnahme: Die Tokens in `tailwind.config.ts` bleiben bewusst
erhalten (Default-Skin nutzt sie). Zusätzlich CI-Check (Phase 0 Guard
bereits definiert), der `bg-tile-*` in `src/` **nur** in
`src/lib/skins/default-skin.ts` zulässt. Ein Grep-Gate reicht:
`! grep -rn "bg-tile-" src/ --include="*.tsx" --include="*.ts" | grep -v "src/lib/skins/default-skin.ts"`.

### R6 — Test-Suite-Brechen

Beschreibung: Refactor von Tile könnte bestehende Tests brechen.
Gegenmaßnahme: Phase 0 legt DOM-Snapshot als Baseline; Phase 1
akzeptiert identischen Snapshot. Neue data-Attribute sind additiv.

### R7 — i18n-Lücke für Skin-Namen

Beschreibung: Skin-ID in Registry, aber kein zugehöriger Key in
messages/*.json → Runtime-Error (missing key) beim Picker.
Gegenmaßnahme: CI-Script vergleicht Registry-Keys gegen beide i18n-
Dateien; Pre-Commit-Hook.

### R8 — PWA / Service-Worker-Caching ~(obsolet)~

~Beschreibung: Falls Next-PWA aktiv ist, könnte der Service-Worker alte
JS-Chunks ausliefern.~
**Status:** Entfällt. Das Projekt hat keinen Service Worker (kein
`next-pwa`, keine Workbox, kein `public/sw.js`). Die `public/manifest.json`
ist nur ein PWA-Manifest für Home-Screen-Installation, steuert aber kein
Runtime-Caching. Cache-Verhalten wird ausschließlich durch die in Phase 6
definierten HTTP-Header gesteuert. Risiko bleibt als Platzhalter
dokumentiert, falls später ein Service Worker ergänzt wird.

### R9 — Dark-Mode-Verhalten unklar

Beschreibung: Dark Mode ist aktuell via Tailwind `dark:` Klassen. Skins
kennen kein Dark Mode.
Gegenmaßnahme: Skin-Container hat nur Tile-Körper; Dark/Light beeinflusst
die Umgebung (Card-Background, Ring-Farben), nicht den Tile selbst. Der
Rummikub-Stein ist im Original-Spiel auch beleuchtungsunabhängig.

### R10 — Play-Mode Drag-Implementation (zukünftig)

Beschreibung: Play-Store hat `interactionMode: "tap" | "drag"`. Drag
ist noch nicht implementiert, wird aber kommen.
Gegenmaßnahme: Das Skin-System ist unabhängig vom Interaction-Mode;
Drag-Ghost sollte den aktiven Skin konsumieren (benutzt `<Tile />` oder
renderer direkt). Explizit als Test-Case in Phase 7 aufnehmen, wenn
Drag-Feature startet.

### R11 — Backend-Puzzle-Store und copy_id

Beschreibung: Die Domain unterscheidet `copy_id=0/1` für doppelte Tiles.
Manche Skins könnten „beide Kopien sehen identisch aus” (wie bisher)
oder (langfristig) „Kopien leicht anders” (handgemalte Asymmetrie).
Gegenmaßnahme: `TileRenderContext` enthält zunächst **kein** `copy_id`.
Das hält die Asset-Anforderungen bei 53 Tiles. Falls später erwünscht,
ist es eine rückwärtskompatible Erweiterung (`copy_id?: number`, Atlas
bekommt 2 Zeilen pro Farbe).

### R12 — TileGridPicker-Aspect-Ratio-Konflikt

Beschreibung: Der Picker nutzt `aspect-[5/6]` während `Tile` fixe
w/h-Klassen nutzt. Eine Integration ist nicht trivial.
Gegenmaßnahme: Entweder den Picker-Tile als neuen `variant="responsive"`
im Tile definieren, oder eine separate `<TileThumbnail />` Komponente, die
denselben Renderer konsumiert. Beide Optionen sind dokumentiert; Entscheidung
in Phase 5.

-----

## 8. Konkrete Umsetzungsreihenfolge

### Reihenfolge

1. **Phase 0** — Konsolidierung. Blockiert alles. Geht schnell (< 1 Tag).
1. **Phase 1** — Abstraktion. Blockiert 2, 3, 5. Parallel dazu kann
   Phase 4’s Asset-Entwurf (Procreate-Arbeit) schon starten, da sie
   keinen Code braucht.
1. **Phase 2** — Store. Parallel zu Phase 3 möglich, wenn zwei Entwickler.
1. **Phase 3** — Sprite-Renderer. Parallel zu Phase 2.
1. **Phase 4** — Erstes Asset + Registry-Eintrag. Braucht Phase 3 +
   User-Produced Asset.
1. **Phase 5** — UI. Braucht Phase 2 + Phase 4.
1. **Phase 6** — Performance/Cache. Optimierung, blockiert nichts fachlich.
1. **Phase 7** — Test-Suite. Läuft kontinuierlich mit, finale Konsolidierung
   nach Phase 5.

### Parallelisierbarkeit

|Kann parallel laufen zu…   |Begründung|
|---------------------------|----------|
|Phase 2                              ||
|Asset-Produktion (5.1–5.12)          ||
|Phase 6                              ||

### Besonders review-kritisch

- **Phase 1** — Abstraktions-Schnitt. Nach dem Merge ist das Contract
  faktisch eingefroren (Test-Baseline schützt, aber Änderungen am
  Renderer-Interface sind teuer).
- **Phase 3** — HiDPI- und Sprite-Positioning-Logik. Off-by-one-Fehler
  sind hier erst bei Sichtprüfung auf Retina-Displays sichtbar.
- **Phase 4** — Asset-Contract (Manifest-Schema, Pfadkonvention).
  Nach Merge ist das Layout für alle zukünftigen Skins festgelegt.
- **Phase 7** — Visual-Regression-Baseline. Wenn die Baseline einmal
  schlecht ist, zementiert sie Bugs.

-----

## 9. GitHub-Issue-Backlog

### Epic: Skin-System für Spielsteine

Dauer grob geschätzt (inkl. Testing): **3–5 Entwicklertage** für einen
Senior-Dev (ohne Asset-Produktion in Procreate, die läuft parallel).

### Issues

|# |Titel                                                   |Kurzbeschreibung                                                                                   |Abhängigkeiten    |Priorität|Risiko|
|--|--------------------------------------------------------|---------------------------------------------------------------------------------------------------|------------------|---------|------|
|1 |Consolidate duplicated tile color constants             |`BG` und `TILE_BG` in `tile-colors.ts` extrahieren; `data-tile-*` Attribute ergänzen; CI-Grep-Guard|—                 |P0       |low   |
|2 |Capture Tile DOM snapshot baseline                      |Alle Permutationen als Snapshot, Baseline für Phase 1                                              |1                 |P0       |low   |
|3 |Define skin types and renderer contract                 |`types.ts`, `renderer.ts`                                                                          |2                 |P1       |low   |
|4 |Implement default CSS skin renderer                     |`default-skin.ts` produziert identisches DOM wie heute                                             |3                 |P1       |medium|
|5 |Add SkinProvider + useActiveSkinRenderer hook           |Context + Hook, in RootLayout einbauen                                                             |4                 |P1       |low   |
|6 |Refactor Tile.tsx to consume skin renderer              |Zentrale Komponente umgestellt, Snapshot grün                                                      |5                 |P1       |high  |
|7 |Add skin Zustand store with localStorage                |Store + Hydrate + Race-Token                                                                       |6                 |P2       |medium|
|8 |Add high-contrast dummy CSS skin                        |Zweiter CSS-Skin zum Testen der Store-API                                                          |7                 |P2       |low   |
|9 |Add image preloader utility                             |`preloadImage(url, timeout)` + StrictMode-safe Cache                                               |5                 |P2       |low   |
|10|Implement sprite-atlas skin renderer                    |Position-Berechnung + inline-style                                                                 |9                 |P2       |medium|
|11|Add `zod` dependency + manifest schema validation       |`npm install zod`, Registry rejectet invalides Manifest                                            |3                 |P2       |low   |
|12|Add `pngjs` dependency + asset validator CLI            |`npm install -D pngjs @types/pngjs`, `scripts/validate-skin.mjs`, `docs/SKINS.md`                  |10, 11            |P2       |low   |
|13|Produce classic-wood atlas + thumbnail in Procreate     |Asset-Arbeit — parallel möglich                                                                    |12 (für Validator)|P3       |medium|
|14|Integrate classic-wood skin into registry               |Manifest-Datei + Registry-Eintrag                                                                  |10, 13            |P3       |low   |
|15|Build SkinPicker component                              |Dropdown + Thumbnail + i18n                                                                        |7, 14             |P3       |low   |
|16|Integrate SkinPicker into Solver header                 |In `app/[locale]/page.tsx` neben LocaleSwitcher                                                    |15                |P3       |low   |
|17|Integrate SkinPicker into Play ControlBar               |Mobile-tauglich platzieren                                                                         |15                |P3       |medium|
|18|Refactor TileGridPicker to use active skin              |Entscheidung aus Phase 5 umsetzen                                                                  |6                 |P3       |medium|
|19|Add i18n keys for skin names & CI check                 |Messages-Dateien + CI-Guard (Registry-IDs vs. messages)                                            |15                |P3       |low   |
|20|Preload active skin in root layout                      |`<link rel="preload" as="image">` in Layout                                                        |14                |P4       |low   |
|21|Background-preload inactive skins                       |`requestIdleCallback` + Safari-`setTimeout`-Fallback                                               |20                |P4       |low   |
|22|Add immutable Cache-Control headers via `next.config.ts`|`headers()` Function für `/skins/:path*`                                                           |14                |P4       |low   |
|23|Add Playwright visual regression suite                  |Alle Skins × Größen × Tiles, `e2e/skins/`                                                          |14                |P5       |medium|
|24|Unit tests for store / preloader / positions            |Gemäß 6.1 (Vitest)                                                                                 |7, 9, 10          |P5       |low   |
|25|E2E test: skin switch persists across reload            |1 Playwright-Test in `e2e/`                                                                        |16, 17            |P5       |low   |

### Empfohlene Sprint-Aufteilung

- **Sprint 1:** #1, #2, #3, #4, #5, #6 → Abstraktion funktioniert end-to-end mit Default.
- **Sprint 2:** #7, #8, #9, #10, #11, #12 → alle Skin-Typen lauffähig, Validator parat.
- **Sprint 3 (Jonas-Arbeit parallel, plus Dev):** #13, #14, #15, #16, #17, #18, #19 → Produkt-Feature fertig.
- **Sprint 4:** #20, #21, #22, #23, #24, #25 → Production-Hardening.

-----

## Anhang A — Architektur-Diagramm (textuell)

```
┌──────────────────────────────────────────────────────────────┐
│                     RootLayout ([locale])                     │
│  ┌────────────────────────────────────────────────────────┐   │
│  │                 NextIntlClientProvider                 │   │
│  │  ┌──────────────────────────────────────────────────┐  │   │
│  │  │                   SkinProvider                    │  │   │
│  │  │  (reads activeSkinId from skinStore)              │  │   │
│  │  │  (resolves SkinRenderer via registry)             │  │   │
│  │  │                                                   │  │   │
│  │  │    ┌────────────────────────────────────┐         │  │   │
│  │  │    │         Page Components             │         │  │   │
│  │  │    │  (Solver / Play / Calibration)      │         │  │   │
│  │  │    │                                     │         │  │   │
│  │  │    │  ┌─────────────┐  ┌──────────────┐  │         │  │   │
│  │  │    │  │ SkinPicker  │  │   Tile × N   │  │         │  │   │
│  │  │    │  │             │  │              │  │         │  │   │
│  │  │    │  │  uses       │  │  uses        │  │         │  │   │
│  │  │    │  │  skinStore  │  │  useActive-  │  │         │  │   │
│  │  │    │  │             │  │  SkinRenderer│  │         │  │   │
│  │  │    │  └─────────────┘  └──────────────┘  │         │  │   │
│  │  │    └────────────────────────────────────┘         │  │   │
│  │  └──────────────────────────────────────────────────┘  │   │
│  └────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────┘

      ┌───────────────────┐      ┌──────────────────────────┐
      │   skinStore       │      │   Skin Registry          │
      │                   │      │                          │
      │ - activeSkinId    │◄────►│ { "default": Manifest,   │
      │ - loadState       │      │   "classic-wood": M,     │
      │ - setSkin()       │      │   "high-contrast": M }   │
      │                   │      │                          │
      │ localStorage:     │      │  resolve(id) → Renderer  │
      │ rummikub_active_  │      └──────────────────────────┘
      │ skin_v1           │
      └───────────────────┘                 │
                                            ▼
                             ┌──────────────────────────┐
                             │    SkinRenderer impls     │
                             │                           │
                             │  - CssSkinRenderer        │
                             │    (default, high-contrast)│
                             │  - SpriteAtlasRenderer    │
                             │    (classic-wood, future) │
                             │                           │
                             │  All implement:           │
                             │  - renderTileBody(ctx)    │
                             │  - containerStyle(ctx)    │
                             │  - preload() / isReady()  │
                             └──────────────────────────┘
```

-----

## Anhang B — Kurzreferenz „so arbeitet der User mit Procreate”

1. **Vorlage öffnen:** `skin-template-v1.procreate` (einmalig erstellen —
   leerer 1560×675 sRGB Canvas mit Grid-Referenz-Layer).
1. **Arbeiten:** einen Stein pro Zelle zeichnen, Gruppen für `blue/red/black/yellow/joker`.
1. **Speichern als:** `skin-<id>-v<version>-master.procreate`.
1. **Exportieren:** Aktionen → Teilen → PNG. Datei nennen `atlas.png`.
1. **Thumbnail:** eigenen 96 × 96 Export (kann beliebig sein — z.B. nur
   die „7”-Steine aller vier Farben).
1. **Ablegen unter:** `frontend/public/skins/<id>/v<version>/`
   (neben `manifest.json`).
1. **Validieren:** `npm run validate:skin <id> <version>`.
1. **Manifest-Eintrag:** `registry.ts` um neuen Import ergänzen.
1. **Testen:** dev-Server starten, Skin im Picker wählen.
1. **Commit & PR.**

-----

## Anhang C — Was dieser Plan bewusst ausklammert

- **Drag & Drop Skin-Preview** — der Play-Store hat `interactionMode="drag"`
  vorgesehen, aber nicht implementiert. Das Skin-System bleibt drag-ready,
  aber Drag ist Scope eines separaten Epics.
- **Animierte Skins / APNG / Lottie** — technisch machbar, aber Procreate-
  unfreundlich. Wenn jemals gewünscht, eigener Manifest-`kind`-Typ.
- **Pro-Kopie-Unterschiede** (copy_id=0 vs. 1) — rückwärtskompatibel
  erweiterbar, aktuell nicht nötig.
- **Skin-Marktplatz / User-Uploads** — dieser Plan setzt voraus, dass
  Skins vom Entwickler/Owner committet werden.
- **Sound-Effekte pro Skin** — orthogonal zum visuellen Skin-Contract,
  eigene Mechanik.

-----

## Schlusswort

Die Ausgangslage ist außergewöhnlich sauber: ein einziger zentraler
Tile-Renderer, keine Backend-Kopplung, saubere Typen. Das Skin-System
kann daher mit moderatem Aufwand (drei bis fünf konzentrierten
Entwicklertagen plus der Procreate-Arbeit parallel) robust implementiert
werden.

Die größten Risiken liegen **nicht** im Code, sondern in der Asset-
Disziplin (Bleeding, Alpha, exakte Maße) — deswegen ist das
Validierungs-CLI ein früher, harter Gate.