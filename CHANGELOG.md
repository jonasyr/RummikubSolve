# Changelog

All notable changes to this project are documented here.
Format: **Phase → What was done → Why it matters**

---

## [0.16.0] — 2026-03-22 — CI hardening & version sync (P2 session)

### Fixed
- **Version sync**: bumped `backend/pyproject.toml` and `backend/api/main.py` from stale
  `0.13.0` to `0.16.0`; updated version assertion in `tests/api/test_solve_endpoint.py`
  to match.
- **Docker healthcheck**: added `healthcheck:` directive to the `backend` service in
  `docker-compose.yml` (`curl -f http://localhost:8000/health`, 10 s interval, 5 retries).
  Without this, the `frontend` `depends_on: backend: condition: service_healthy` condition
  caused `docker compose up` to hang indefinitely.

### CI
- **Vitest wired into frontend CI** (`.github/workflows/frontend.yml`): added
  `npm run test` step after the build step so all 33 Vitest unit tests run on every push
  and pull request to `main` or `claude/**` branches.

---

## [0.15.0] — 2026-03-22 — Testing & quality improvements (P1 session)

### Testing — frontend

- **Vitest unit test setup** (`frontend/vitest.config.ts`, `package.json`): installed
  Vitest 2.x with `@vitejs/plugin-react`, `jsdom`, `@testing-library/react`, and
  `@testing-library/jest-dom`. Added `test` and `test:watch` npm scripts. E2E spec
  files are excluded via `vitest.config.ts` to prevent Playwright tests being picked
  up by Vitest. Total: 33 unit tests.
- **Zustand store tests** (`src/__tests__/store/game.test.ts`, 15 tests): covers every
  action — `addRackTile`, `removeRackTile`, `addBoardSet`, `removeBoardSet`,
  `updateBoardSet`, `setIsFirstTurn`, `setIsBuildingSet`, `setLoading`, `setError`,
  `setSolution`, and `reset`.
- **Tile component tests** (`src/__tests__/components/Tile.test.tsx`, 11 tests): number
  rendering, joker star symbol, `size` variant CSS classes (`xs`/`sm`/`md`), remove
  button presence and callback, and highlight ring on/off.
- **LocaleSwitcher component tests** (`src/__tests__/components/LocaleSwitcher.test.tsx`,
  7 tests): EN/DE button rendering, active locale `bg-blue-600` class, `aria-current`
  attribute, inactive locale calls `router.replace`, active locale click is a no-op.

### Testing — E2E viewport expansion

- **Mobile and tablet viewports** (`playwright.config.ts`): added Pixel 5 (393×851,
  Android mid-range) and iPhone SE (375×667, smallest supported iPhone) Playwright
  projects alongside the existing Desktop Chrome project. All 5 existing spec files now
  run across 3 device profiles (15 total test runs). No spec changes required — tests
  use role/text locators that work at any viewport.

### Testing — backend property tests

- **Hypothesis property-based solver tests** (`tests/solver/test_ilp_solver.py`,
  3 new tests, 60-40 examples each): addresses Audit Report finding of only 1 existing
  Hypothesis test.
  - `test_property_tile_conservation`: verifies `placed_tiles + remaining_rack == rack`
    for any random rack (no tiles created or lost by the solver).
  - `test_property_output_sets_are_valid`: verifies every set in the solution passes
    `is_valid_set` for any random rack input.
  - `test_property_first_turn_threshold_respected`: verifies that when `is_first_turn=True`,
    any placement meets the 30-point meld threshold.

### Fixes

- **pyproject.toml version** (`backend/pyproject.toml`): bumped from `0.6.0` to `0.13.0`
  to match `api/main.py` (missed in the previous session).

---

## [0.14.0] — 2026-03-22 — Deployment fixes & polish (P0/P1/P2 session)

### Deployment — critical fixes (P0)

- **nginx reverse proxy** (`nginx/nginx.conf`, `docker-compose.yml`): added nginx service
  on port 80 that proxies `/api/*` and `/health` to `backend:8000` and everything else to
  `frontend:3000`. Set `NEXT_PUBLIC_API_URL: ""` in the frontend Docker build args so the
  browser uses relative URLs (`/api/solve`) — resolves the critical issue where the baked-in
  `http://backend:8000` URL was unreachable by browsers outside Docker.
- **Container restart policies** (`docker-compose.yml`): added `restart: unless-stopped` to
  backend and frontend services so containers recover automatically after server reboots.
- **Version bump** (`backend/api/main.py`): `app.version` updated from `"0.6.0"` to
  `"0.13.0"` so `/health` returns the correct version.

### Cleanup — P1

- **Remove dead output module** (`backend/solver/output/`): deleted the empty
  `__init__.py` left from the v0.7.0 module deletion. No imports referenced it.
- **Document joker_retrieval stub** (`backend/solver/config/rules.py`): added a NOTE
  comment and a `# TODO` marker clarifying that the field is accepted for forward
  compatibility but has no effect on ILP behaviour.
- **PWA icons** (`frontend/public/icons/`, `manifest.json`): generated 192×192 and
  512×512 PNG icons (blue `#1e40af` background, white "R" lettermark) and populated
  `manifest.json`'s previously-empty `"icons"` array. Enables PWA installation on mobile.

### Polish — P2

- **Dark mode** (6 frontend component files): wired up the existing CSS variables from
  `globals.css` to Tailwind `dark:` classes across `page.tsx`, `RackSection`,
  `BoardSection`, `SolutionView`, `RulesPanel`, and `LocaleSwitcher`. Uses
  `prefers-color-scheme` media strategy — no JS toggle required. Tile colors (red/blue/
  black/yellow) intentionally left unchanged as they carry semantic meaning.
- **README home-server deployment guide** (`README.md`): added Home Server Deployment
  section explaining the nginx proxy architecture, setup steps, and HTTPS options
  (Tailscale / Cloudflare Tunnel). Updated Docker section and environment variable table.
- **.env.example** (`env.example`): updated `NEXT_PUBLIC_API_URL` comment to clarify
  Docker vs local development usage.

---

## [0.13.0] — 2026-03-21 — UX cleanup & solver quality improvements

### UX improvements (frontend)

- **Tooltips on solution badges** (`SolutionView.tsx`): the `↺`, `NEU`/`NEW`, `+`,
  and `unverändert`/`unchanged` badges now show a `title` tooltip on hover explaining
  what each status means. Both EN and DE strings added to `messages/*.json`.
- **Tiles sorted within runs** (`SolutionView.tsx`): tiles inside a run-type solution
  set are now sorted ascending by number before display (e.g. 7 · 8 · 9 instead of
  7 · 9 · 8). Original indices are preserved for rack-tile highlighting.
- **Move descriptions fully translated** (`SolutionView.tsx`): move instruction text
  was previously returned as English-only strings from the backend. The frontend now
  reconstructs localised descriptions from structured data (`new_board`, `new_tile_indices`,
  `set_index`) using new ICU translation keys (`moveDesc.*`, `colors.*`, `types.*`) in
  both `en.json` and `de.json`.
- **Add-set builder appears at top** (`BoardSection.tsx`): the inline tile-picker for
  adding a new board set previously rendered below all existing sets, requiring scroll
  when many sets were present. It now appears immediately below the section header.
- **Auto-detect run vs group** (`BoardSection.tsx`): removed the manual "Folge / Gruppe"
  type selector. The app now tries `run` first and `group` second, accepts whichever
  validates, and shows the detected type in the confirmation feedback. This also removes
  the now-unused `typeRun` / `typeGroup` translation keys from the component logic.
- **Rack tiles counted in board set picker** (`BoardSection.tsx`): the tile-grid picker
  used when building a board set did not account for tiles already on the rack. A tile
  present on the rack now shows count ≥ 1 in the picker, preventing double-booking.

### Solver improvement (backend)

- **Minimise remaining tile value as secondary objective** (`engine/ilp_formulation.py`):
  when no perfect solution exists (not all rack tiles can be placed), the ILP now
  prefers arrangements that leave the lowest total face value in hand. Implemented by
  adding `tile.number / 200.0` to each hand variable's objective coefficient — small
  enough to never override the primary "maximise tiles placed" goal.

---

## [0.12.1] — 2026-03-21 — Post-release solver & test patches

### Bug fixes

- **Backend — duplicate-board-set infeasibility** (`generator/set_enumerator.py`):
  when the board contained two identical sets (e.g. two copies of Red 1-2-3 using both
  physical tile copies), the ILP had only one binary template for that set and could not
  activate it twice → declared infeasible. Each base template is now duplicated up to
  N times where N = `min(available copies of required tiles)`, resolving the constraint.
- **Backend — joker-board infeasibility** (`generator/set_enumerator.py`,
  `engine/solver.py`): type-1 joker variants were incorrectly restricted to rack tiles,
  causing infeasibility when a joker was a board tile whose covered number also appeared
  elsewhere on the board. Reverted to generating type-1 variants for all tile positions
  with fingerprint-based deduplication. Solver timeout raised from 2 s to 30 s for
  complex joker boards.
- **Backend — timeout leaves board tiles unplaced** (`engine/solver.py`): if HiGHS
  timed out before finding a feasible integer solution, `extract_solution` could return
  a partial result missing board tiles. Added a post-extraction guard that detects
  missing board tiles and falls back to no-move (unchanged board, full rack in hand).
- **Backend — copy_id always 0** (`api/main.py`, `validator/solution_verifier.py`):
  all tiles were assigned `copy_id=0` regardless of duplicates, so the ILP treated
  both physical copies of a tile as the same variable. Replaced `_tile_input_to_domain`
  with `_assign_copy_ids` which assigns `copy_id=0`/`1` based on occurrence order
  across board + rack tiles together.
- **Frontend — RulesPanel `FORMATTING_ERROR`** (`components/RulesPanel.tsx`):
  `dangerouslySetInnerHTML` combined with `t()` caused next-intl to throw
  `FORMATTING_ERROR` because `<strong>` tags were parsed as unresolved ICU variables.
  Switched to `t.rich()` with a `strong` component renderer — no `dangerouslySetInnerHTML`
  needed, no XSS surface.
- **E2E — strict-mode locator violations** (`e2e/board_section.spec.ts`,
  `e2e/extend_board_set.spec.ts`): tile buttons and type labels matched multiple
  elements when both the rack and board-builder pickers were visible simultaneously.
  Scoped all tile interactions to the containing `section` element and updated
  assertions to match actual rendered text.

---

## [0.12.0] — 2026-03-21 — Phase 10: Post-merge Bug Fixes, New Tests & Changelog

### Bug fixes

- **Backend — joker validation** (`api/models.py`): a tile sent as
  `{"joker": true, "color": "red"}` previously passed Pydantic validation and
  silently violated the domain invariant. A guard now raises
  `"Joker tiles must not have a color or number."`, returning HTTP 422.
- **Backend — event-loop blocking** (`api/main.py`): the `/api/solve` endpoint
  was declared `async def` despite containing no async I/O. Changed to `def` so
  FastAPI correctly routes it through a thread pool and the event loop stays free
  for other requests.
- **Backend — Counter type annotations** (`api/main.py`): `Counter` generics
  used `str | None` for tile colour fields, but the domain `Tile.color` is a
  `Color` enum. Updated to `Color | None` for correct mypy inference.
- **Frontend — concurrent-solve race condition** (`app/[locale]/page.tsx`):
  rapid clicks on "Solve" would send overlapping requests; a slower response
  could overwrite a newer one. An `AbortController` stored in a `useRef` now
  cancels the previous in-flight fetch before starting a new one. `AbortError`
  is silently swallowed so the UI stays clean.
- **Frontend — missing `aria-live`** (`app/[locale]/page.tsx`): the error
  banner had `role="alert"` but no `aria-live` attribute. Added
  `aria-live="assertive"` so screen readers announce errors immediately.
- **Frontend — accidental reset** (`app/[locale]/page.tsx`): the Reset button
  wiped all board/rack data without confirmation. A `window.confirm()` guard is
  now shown whenever tiles or sets are present. The confirmation message is
  fully translated (`page.resetConfirm` in `en.json` / `de.json`).

### New tests

- **Backend API** — 9 new tests added to `tests/api/test_solve_endpoint.py`,
  each following strict AAA (Arrange / Act / Assert) structure:
  - `test_solve_group_happy_path` — three same-number different-colour tiles
  - `test_solve_with_joker_in_run` — joker fills a gap in a run
  - `test_solve_extends_existing_board_set` — rack tile extends a board run
  - `test_solve_two_tiles_in_rack_returns_no_solution` — insufficient tiles
  - `test_solve_response_contains_all_required_fields` — schema completeness
  - `test_is_unchanged_true_for_unmodified_board_set` — `is_unchanged` flag
  - `test_new_tile_indices_populated_for_rack_tile` — highlight index accuracy
  - `test_joker_with_color_returns_422` — validates joker guard (B1 above)
  - `test_joker_with_number_returns_422` — validates joker guard (B1 above)
- **Backend unit** — 3 new tests added to `tests/test_models.py`:
  - `test_tile_input_joker_minimal_valid` — bare joker is valid
  - `test_tile_input_joker_with_color_raises` — ValidationError expected
  - `test_tile_input_joker_with_number_raises` — ValidationError expected
- **E2E Playwright** — 2 new spec files:
  - `e2e/board_section.spec.ts` — add a set via UI, verify it renders
  - `e2e/extend_board_set.spec.ts` — add board run + rack tile, solve,
    assert extend move shown with correct set reference

---

## [0.11.0] — 2026-03-21 — Phase 9: Multi-language i18n (EN + DE)

### New features

- **`next-intl ^3`** installed; URL-based locale routing (`/en/`, `/de/`) via
  `next-intl/middleware` and `defineRouting`.
- **`src/middleware.ts`** (new): routes every request through next-intl middleware so
  the browser is redirected to `/en` or `/de` based on `Accept-Language` headers and
  cookie preference.
- **`src/i18n/config.ts`** (new): single source of truth — `locales = ["en", "de"]`,
  `defaultLocale = "en"`, exported `Locale` type.
- **`src/i18n/routing.ts`** (new): `defineRouting({ locales, defaultLocale })` consumed
  by middleware and `createNavigation`.
- **`src/i18n/request.ts`** (new): `getRequestConfig` dynamically imports the matching
  `messages/{locale}.json` file per request.
- **`src/i18n/navigation.ts`** (new): typed `Link`, `useRouter`, `usePathname` via
  `createNavigation(routing)`.
- **`src/i18n/messages/en.json`** (new): ~100 English strings across namespaces:
  `common`, `meta`, `page`, `rulesPanel`, `rack`, `board` (with `errors`), `tilePicker`,
  `tile`, `solution`, `errorBoundary`, `localeSwitcher`. ICU plurals for tile counts
  and move summaries.
- **`src/i18n/messages/de.json`** (new): full German translation (e.g.
  `page.solve` → "Lösen", `rack.heading` → "Deine Steine",
  `board.heading` → "Tisch-Sätze", `solution.badge.new` → "NEU").
- **`src/app/[locale]/layout.tsx`** (new): locale-aware root layout with
  `<html lang={locale}>`, `<NextIntlClientProvider>`, and `generateMetadata` using
  translated title/description.
- **`src/app/[locale]/page.tsx`** (new): main page moved here; uses
  `useTranslations("page")` and renders `<LocaleSwitcher />`.
- **`src/components/LocaleSwitcher.tsx`** (new): EN / DE toggle buttons using
  `useLocale()` + typed `router.replace(pathname, { locale })` — no page reload needed.

### Updated components

- `BoardSection.tsx`: `validateSet` now returns `{ key, params } | null` instead of a
  plain string; component resolves the translation key via `t(key, params)`. Headings,
  labels, buttons, and error messages fully translated.
- `RackSection.tsx`, `RulesPanel.tsx`, `SolutionView.tsx`, `TileGridPicker.tsx`,
  `Tile.tsx`, `ErrorBoundary.tsx` — all use `useTranslations(namespace)`.
- `ErrorBoundary.tsx`: added optional `heading?` and `fallback?` props + new
  `TranslatedErrorBoundary` functional wrapper that injects translated strings.
- `src/app/layout.tsx`: reduced to a pass-through wrapper (HTML/body live in
  `[locale]/layout.tsx`).
- `next.config.ts`: wrapped with `createNextIntlPlugin`.

### Bug fixes

- Fixed ruff formatting in `backend/api/main.py` and `backend/api/models.py`
  (trailing whitespace / alignment issues flagged by CI).

---

## [0.10.0] — 2026-03-21 — Phase 8: Rules Panel + Solution Clarity

### New features

- `RulesPanel.tsx` (new): collapsible "ℹ How sets work" panel inserted between the
  page header and the rack picker. Uses native `<details>/<summary>` — zero JS, zero
  React state, closed by default. Explains Run, Group, First-turn threshold (≥30 pts),
  and Joker rules.
- `page.tsx`: imports and renders `<RulesPanel />`.

### Solution display improvements

- **4-way set-status badges** (`SolutionView.tsx`): sets in the solution board now carry
  a colored border + badge derived entirely from existing fields (`is_unchanged`,
  `new_tile_indices`, `tiles.length`) — no new API data needed:
  - **NEW** (green border + green badge) — all tiles came from the rack
  - **+** (blue border + blue badge) — existing set extended with rack tiles
  - **↺** (amber border + amber badge) — board tiles reshuffled, no new tiles
  - *unchanged* (gray, muted) — set is identical to the pre-solve board
- **Move summary line**: one-liner above the step list, e.g.
  *"3 moves: 2 new sets, 1 extension"*, computed from `solution.moves`.
- **Action-typed move bullets**: the numbered circle next to each instruction is now
  color-coded — green for `create`, blue for `extend`, amber for `rearrange`.
  The `action` field was already present in `MoveOutput` but was never surfaced in
  the UI.

### Verification

```
tsc --noEmit:  0 errors
next build:    clean
```

---

## [0.9.0] — 2026-03-21 — Phase 7: Physical Executability

### Bug fixes

- **`new_tile_indices` over-highlighting** (`api/main.py`): replaced `placed_key_set`
  (a plain Python `set`) with a `Counter` that is consumed one entry at a time as tiles
  are matched. Previously, when the same tile appeared in both the board and the rack
  (e.g. Red 5 on board + Red 5 in rack), the set collapsed both copies to one key and
  highlighted every matching tile — including board tiles never placed from the rack.

### New features

- **`is_unchanged` field** (`api/models.py`, `api/main.py`): `BoardSetOutput` now
  carries `is_unchanged: bool`. Computed in `main.py` by comparing each new set's tile
  multiset (`Counter` of color+number+joker) against the old board sets. A set is
  unchanged when no rack tiles were added AND the tile composition matches an existing
  board set exactly.
- **Set numbers in solution UI** (`SolutionView.tsx`): each set in the solution board
  now displays a bold number prefix ("1.", "2.", …) that directly corresponds to the
  set indices referenced in move instructions ("Add to set 2").
- **Source-set hint in rearrange descriptions** (`move_generator.py`): pure-board
  rearrangement moves now say *"Take tiles from set 2 and reform as run: Red 4, Red 5,
  Red 6"* instead of the previous opaque *"Rearrange into run: …"*. The best-matching
  old set is found by tile-key overlap and referenced by 1-based index.
- **`is_unchanged` in frontend types** (`types/api.ts`): `BoardSetOutput` extended
  with `is_unchanged?: boolean`.

### Verification

```
pytest:       147 passed, 0 failed
tsc --noEmit: 0 errors
next build:   clean
```

---

## [0.8.0] — 2026-03-21 — Phase 6: UX Flow Fixes

### Bug fixes

- **Rack picker tile count** (`RackSection.tsx`): `tileCount` now sums tiles across
  both `rack` AND `boardSets`, enforcing the 2-copy Rummikub limit globally. Previously
  only rack tiles were counted, allowing >2 copies of the same tile when some were
  already on the board.
- **Pydantic 422 error format** (`api.ts`): `detail` arrays (FastAPI's default Pydantic
  validation shape) are now joined into a readable string instead of rendering as
  `[object Object],[object Object]`.
- **`SolutionView` null safety** (`SolutionView.tsx`): all `.map()`, `.length`, and
  `.includes()` calls on `new_board`, `moves`, `remaining_rack`, and `new_tile_indices`
  guarded with optional chaining / `?? []` to prevent runtime render crashes when any
  field is unexpectedly null.

### New features

- **`isBuildingSet` store field** (`store/game.ts`): builder open/closed state moved
  from local `useState` in `BoardSection` into the Zustand store. `reset()` clears it
  via `initialState`. Enables page-level awareness of the builder state.
- **Solve button guarded** (`page.tsx`): Solve is disabled and shows *"Finish editing
  first"* while the board set builder is open (`isBuildingSet`), preventing the solver
  from running with incomplete board state.
- **Board locked during solve** (`BoardSection.tsx`): Add Set / Edit (✎) / Remove (×)
  buttons are disabled while `isLoading`, preventing mid-flight board mutations that
  would make the response inconsistent with what was sent.
- **Reset closes builder** (`BoardSection.tsx` + `store/game.ts`): clicking Reset now
  also closes the builder UI because `isBuildingSet` is part of `initialState`.
- **`ErrorBoundary` component** (`ErrorBoundary.tsx`, new): React class-based error
  boundary wrapping `<SolutionView>`. Render errors that previously surfaced only in the
  browser console now show a user-friendly red fallback panel instead of a blank screen.

### Verification

```
tsc --noEmit: 0 errors
next build:   clean
```

---

## [0.7.0] — 2026-03-21 — Phase 5: Cleanup, Polish & API Tests

### Bug fixes

- `api/main.py`: `MoveOutput.set_index` was dropped during serialisation — fixed
  by passing `set_index=m.set_index` in the list comprehension.
- `api/main.py` + `pyproject.toml`: version was `"0.2.0"` / `"0.1.0"` (Phase 2
  artefacts never updated); both now read `"0.6.0"`.
- `BoardSection.tsx`: `TileGridPicker` inside the set builder had no `tileCount`
  prop — users could add more than 2 copies of a tile to a board set, violating
  game rules. Now tracks tiles in the pending set + existing board sets.

### New features

- Board set editing: each set now has an ✎ edit button that repopulates the
  inline builder. `updateBoardSet` (already in the store) is wired up.
- `SolveResponse.is_first_turn` field echoed back to frontend; `SolutionView`
  uses it to show "Below threshold" vs "No valid move" in the `no_solution` case.

### Validation

- `models.py`: Pydantic `Field` constraints added —
  board set `tiles` requires 3–13 entries; `rack` capped at 104;
  `board` capped at 50 sets. Invalid inputs now return 422 with clear messages.
- `solution_verifier.py`: added first-turn meld-threshold check as defense-in-depth.

### Tests

- `tests/api/test_solve_endpoint.py` (new): 9 integration tests covering `/health`,
  `/api/solve` happy paths, 422 error paths, first-turn rules, and `set_index`
  serialisation. Uses `httpx.AsyncClient` + ASGI transport (no real network).
- `test_rule_checker.py`: one Hypothesis property test — `is_valid_set` must return
  a `bool` for any tile combination (200 random examples, never raises).

### Code quality

- Deleted dead-code stubs: `solver/output/solution_formatter.py`,
  `diff_calculator.py`, `explanation.py` — logic already inlined in `main.py`.
- Fixed `type: ignore[arg-type]` in `main.py` with an explicit `Literal` annotation.
- Added per-request `structlog` line in `/api/solve` handler.
- Added `role="alert"` on the frontend error banner.

### Docs

- `README.md`: added environment-variable table, E2E test instructions, expanded
  Docker Compose section, and dev-status link.
- `CHANGELOG.md`: this entry.

---

## [0.6.0] — 2026-03-21 — Phase 4: Observability, Containerisation & E2E Tests

### What was implemented

**Observability — `backend/api/main.py`**

- Sentry SDK initialised at startup via `SENTRY_DSN` env var; no-op (zero overhead)
  when the variable is unset or empty. `traces_sample_rate=0.1` captures 10 % of
  transactions for performance monitoring. `send_default_pii=False` by default.
- `structlog` now configured explicitly: JSON renderer in `ENVIRONMENT=production`,
  colored `ConsoleRenderer` in development. Log level set to `INFO` via standard
  `logging.basicConfig`.
- CORS `allow_origins` now driven by `ALLOWED_ORIGIN` env var (default `"*"`).
  Fixes a pre-existing spec violation where `allow_credentials=True` was combined
  with the wildcard origin; credentials are now disabled when the origin is `"*"`.

**Environment documentation — `.env.example`**

- Documents all four env vars with defaults, descriptions, and production examples:
  `SENTRY_DSN`, `ENVIRONMENT`, `ALLOWED_ORIGIN`, `NEXT_PUBLIC_API_URL`.
- `docker-compose.yml` updated to forward `ENVIRONMENT`, `SENTRY_DSN`, and
  `ALLOWED_ORIGIN` from the host shell / `.env` file into the backend container.

**Frontend containerisation**

- `frontend/next.config.ts`: `output: "standalone"` uncommented — Next.js emits a
  self-contained `server.js` + minimal `node_modules` tree during `next build`.
- `frontend/Dockerfile`: multi-stage image (`node:22-alpine` builder → runner).
  `NEXT_PUBLIC_API_URL` accepted as a `--build-arg` (baked into the JS bundle at
  build time). Non-root `nextjs` user in the runtime stage.
- `docker-compose.yml`: `frontend` service added; depends on `backend`
  `service_healthy` so the UI waits for the API before accepting traffic.

**Playwright E2E tests — `frontend/e2e/`**

- `playwright.config.ts`: Chromium-only, `webServer` auto-starts `next dev`,
  single worker + 1 retry in CI, HTML report artifact on failure.
- `package.json`: `@playwright/test ^1.50.0` added to devDependencies; `e2e` and
  `e2e:ui` npm scripts added.
- `e2e/solve_basic_run.spec.ts`: adds Red 10–12 to rack, solves, asserts
  "3 tiles placed" + "Optimal" + "Move instructions" visible.
- `e2e/solve_first_turn.spec.ts` (2 tests): first-turn pass (33 ≥ 30) and
  first-turn block (15 < 30 → "no tiles can be placed").
- `e2e/tile_limit.spec.ts`: clicks same tile twice, asserts button is disabled on
  the second copy (count ≥ 2).

**CI — `.github/workflows/e2e.yml`**

- Triggered on pushes/PRs touching `backend/**` or `frontend/**`.
- Starts the FastAPI backend in the background, waits for `/health` with retries,
  then runs Playwright (which auto-starts the Next.js dev server via `webServer`).
- Uploads the Playwright HTML report as a workflow artifact on failure (7-day
  retention).

### Verification (all passed before commit)

```
pytest:          137 passed, 0 failed
ruff check:      0 errors
ruff format:     clean
mypy strict:     no issues in 24 source files
tsc --noEmit:    0 errors (includes playwright.config.ts)
next lint:       0 warnings / errors
next build:      ✓ standalone output — .next/standalone/server.js present
```

### What is NOT here yet

- Actual deployment to Vercel + Fly.io (requires external service configuration)
- PWA icon assets (manifest.json placeholder remains)
- Database / persistence layer (stateless solver by design)

---

## [0.5.0] — 2026-03-21 — Phase 2b + 3b: First-Turn Rule, Move Generator & Tile Count Limits

### What was implemented

**Phase 2b — First-Turn ILP Constraint**

- `backend/solver/engine/ilp_formulation.py`: Constraint 3 added — when `rules.is_first_turn=True`,
  encodes `Σ placed_tile_numbers ≥ initial_meld_threshold` as an upper-bound row on `h[t]` variables.
  Jokers contribute 0 points toward the threshold. If the rack value is below the threshold the
  upper bound becomes negative, HiGHS returns `kInfeasible`, and `solver.py` maps that to 0 tiles placed.
- `backend/solver/engine/solver.py`: First-turn solves build a rack-only `BoardState(board_sets=[], rack=...)`;
  `ValueError` from an infeasible ILP is caught and returned as a "no play" outcome instead of a 422 error;
  original board sets are prepended to the result unchanged so the full board is always in the response.
- 6 new ILP tests: above threshold, below threshold, exact threshold, board preservation, board-tile
  isolation, and joker-has-no-value.

**Phase 3b — Move Generator**

- `backend/solver/generator/move_generator.py`: replaces `NotImplementedError` with a diff-based
  implementation. For each new set, partitions tiles into rack-origin vs board-origin and classifies
  the move as `create` (set built entirely from rack), `extend` (rack tiles added to an identifiable
  existing set — carries `set_index`), or `rearrange` (board tiles redistributed across sets).
  Unchanged board sets emit no instruction.
- `backend/solver/engine/solver.py`: `generate_moves` wired in; `moves=[]` placeholder removed.
- 7 new move-generator unit tests in `tests/solver/test_move_generator.py`.

**Phase 3b — Tile Count Limits (frontend)**

- `frontend/src/components/TileGridPicker.tsx`: new optional `tileCount` prop; tile buttons are
  disabled at count ≥ 2 (Rummikub maximum) and show a small count badge overlay when ≥ 1 copy is
  already in the rack.
- `frontend/src/components/RackSection.tsx`: per-tile counts derived from the rack array via
  `useCallback` and passed to `TileGridPicker`.
- `frontend/src/components/SolutionView.tsx`: numbered "Move instructions" section rendered when
  `solution.moves.length > 0`.

### Verification (all passed before commit)

```
pytest:          137 passed, 0 failed  (124 existing + 13 new)
ruff check:      0 errors
ruff format:     clean
mypy strict:     no issues in 24 source files
tsc --noEmit:    0 errors
next lint:       0 warnings / errors
next build:      ✓ clean
```

### What is NOT here yet (next phase)

- Sentry integration — Phase 4
- Playwright E2E tests — Phase 4
- Frontend Dockerfile / standalone containerisation — Phase 4
- Environment variable documentation (`.env.example`) — Phase 4

---

## [0.4.0] — 2026-03-21 — Phase 3: Frontend Core UI

### What was implemented

**`frontend/src/lib/api.ts`** — API client

- `solvePuzzle(request) → Promise<SolveResponse>`: POST to `/api/solve`
- Reads `NEXT_PUBLIC_API_URL` (falls back to `http://localhost:8000`)
- Throws with backend `detail` message on non-2xx; catches JSON parse failures

**`frontend/src/components/Tile.tsx`** — tile chip component

- Three sizes: `xs` (20×24 px, used in picker), `sm` (28×32 px), `md` (36×40 px)
- Color backgrounds via static `BG` map (`tile-blue/red/black/yellow` from Tailwind config)
- Joker renders `★` in yellow-on-dark; `highlighted` prop adds a yellow ring (marks newly placed tiles); `onRemove` renders an `×` overlay button

**`frontend/src/components/TileGridPicker.tsx`** — 4×13 click grid

- 4 rows (blue, red, black, yellow) × 13 columns (1–13) + joker button
- Uses `size="xs"` + `gap-[2px]`: grid is 284 px, fits 320 px–375 px screens without overflow
- Purely presentational; calls `onSelect(tile)` on click

**`frontend/src/components/RackSection.tsx`** — rack input and display

- Embeds `TileGridPicker`; clicking adds tile via `addRackTile`
- Displays current rack as removable tile chips

**`frontend/src/components/BoardSection.tsx`** — board set editor

- Lists existing sets with per-set remove button
- "Add Set" opens inline set-builder: RUN/GROUP toggle + `TileGridPicker` for pending tiles + confirm/cancel

**`frontend/src/components/SolutionView.tsx`** — solution display

- Handles all three statuses: `solved` (summary bar + new board + remaining rack), `no_solution` (yellow callout), `error` (red callout)
- Tiles in `new_tile_indices` rendered with `highlighted` ring to identify rack placements

**`frontend/src/app/page.tsx`** — main page (replaced placeholder)

- `"use client"` single-column mobile layout: header (title + first-turn toggle + reset), rack, board, solve button, error banner, solution
- Solve button disabled while loading or rack is empty
- `handleSolve` dispatches to Zustand store: `setLoading` → `solvePuzzle` → `setSolution` / `setError`

**Fixes applied after audit:**

- `Tile`: added `xs` size (20 px wide) so the picker grid fits all screens ≥ 320 px
- `SolutionView`: `status="error"` now shows a red callout instead of falling through to a broken render
- `globals.css`: `overflow-x: hidden` on body prevents horizontal page scroll
- `manifest.json`: removed references to non-existent icon files

### Verification (all passed before commit)

```
tsc --noEmit:   0 errors
next lint:      0 warnings / errors
next build:     ✓ 3.36 kB page bundle
```

### What is NOT here yet (next phases)

- `generator/move_generator.py` — human-readable move instructions (Phase 3b)
- Per-tile quantity limits in UI — max 2 copies per tile type (Phase 3b)
- Board set edit (currently only delete) (Phase 3b)
- Initial meld threshold constraint in ILP (`rules.is_first_turn` — Phase 2b)
- PWA icons (placeholder icons needed before Phase 4 deploy)
- Sentry integration — Phase 4
- Playwright E2E tests — Phase 4

---

## [0.3.0] — 2026-03-21 — Phase 2: ILP Solver + API Endpoint

### What was implemented

**`backend/solver/generator/set_enumerator.py`** — joker expansion added to `enumerate_valid_sets`

- Two types of single-joker variants generated when jokers are in the pool:
  - **Type 1 (substitute):** joker replaces an *available* tile in a base template, freeing that tile for another set
  - **Type 2 (fill-missing):** joker fills a slot whose non-joker tile is *absent* from the pool — enabling templates that couldn't otherwise form (e.g., [Red 4, Joker, Red 6] when Red 5 is missing)
- `enumerate_runs` and `enumerate_groups` remain unchanged (pure non-joker, used as base)
- No jokers in pool → result is identical to Phase 1a (existing tests unchanged)

**`backend/solver/engine/ilp_formulation.py`** — ILP model construction

- `ILPModel` dataclass: wraps a `highspy.Highs` instance + variable index mappings (`y_vars`, `x_vars`, `h_vars`, `rack_tile_indices`)
- `build_ilp_model(state, candidate_sets, rules) → ILPModel`:
  - **Variables:** `y[s] ∈ {0,1}` per template, `x[t,s] ∈ {0,1}` per (tile, template) pair (sparse), `h[t] ∈ {0,1}` per rack tile
  - **Constraint 1 — Tile conservation:** board tiles placed exactly once; rack tiles placed or held
  - **Constraint 2 — Slot satisfaction:** each template slot filled by exactly one matching physical tile when the template is active
  - **Objective:** minimize Σ h[t] (= maximize tiles placed from rack)
  - Joker slots detected from `tile.is_joker` on template tiles; physical jokers fill them
  - Infeasible board → encoded as `0 = 1` constraint so HiGHS propagates infeasibility
- `extract_solution(model) → (new_sets, placed_tiles, remaining_rack, is_optimal)`:
  - Reads `col_value` with EPS=0.5 threshold; treats `kModelEmpty` (empty pool) as optimal

**`backend/solver/engine/solver.py`** — main orchestrator

- `solve(state, rules) → Solution`:
  1. `enumerate_valid_sets` → candidate templates
  2. `build_ilp_model` → HiGHS model
  3. `model.highs.run()` with 2-second time limit
  4. `extract_solution` → Solution dataclass
  5. `verify_solution` → raises `ValueError` if post-verification fails
- Returns `is_optimal=True` when HiGHS proves optimality (always for typical game sizes)

**`backend/solver/engine/objective.py`** — disruption scoring

- `compute_disruption_score(old_board_sets, new_board_sets) → int`: counts board tiles that moved to a different set index; used as a post-solve metric (not yet encoded in ILP objective)

**`backend/solver/validator/solution_verifier.py`** — post-solve verification

- `verify_solution(state, solution, rules) → bool`:
  - All sets in `solution.new_sets` pass `is_valid_set`
  - `placed_tiles ∪ remaining_rack == original_state.rack` (by tile keys)
  - Tiles in `new_sets == board_tiles ∪ placed_tiles` (multiset equality)

**`backend/api/main.py`** — `/api/solve` endpoint activated (Phase 2)

- `POST /api/solve` converts Pydantic request → domain `BoardState`, calls `solve()`, converts `Solution` → `SolveResponse`
- `new_tile_indices` annotated per set (identifies which tiles came from the rack)
- Returns `status: "solved"` if any tiles placed, `"no_solution"` if rack unchanged
- Error paths: 422 for invalid input or infeasible board

**`backend/tests/solver/test_ilp_solver.py`** — 22 known-answer ILP tests

- Empty board rack-only plays: minimal run, minimal group, 4-tile group, 13-tile run, too-short rack
- Extending existing board sets: end, start, both ends; gap prevents extension
- Board rearrangement: merging runs across positions to place more rack tiles
- Group from rack without disturbing board; all-four-color group
- Duplicate tiles: both copies of same tile usable in different sets simultaneously
- Joker: fills gap in run, fills slot in group, stays in hand when no compatible set
- Edge cases: empty rack (is_optimal=True), solve_time_ms > 0

**`backend/tests/solver/test_solution_verifier.py`** — 9 tests for verify_solution

**`backend/tests/solver/test_objective.py`** — 5 tests for compute_disruption_score

### Verification (all passed before commit)
```
pytest:         124 passed, 0 failed  (88 existing + 36 new)
ruff check:     0 errors
ruff format:    clean
mypy strict:    no issues in 24 source files
```

### What is NOT here yet (next phases)
- `generator/move_generator.py` — human-readable move instructions (Phase 3)
- `output/` modules — diff, formatter, explanation (Phase 3)
- Initial meld threshold constraint in ILP (rules.is_first_turn — Phase 2b)
- Double-joker template variants (currently only single-joker expansion)
- Frontend UI components (tile grid picker, board display, solution view) — Phase 3
- Sentry integration — Phase 4
- Playwright E2E tests — Phase 4

---

## [0.2.0] — 2026-03-21 — Phase 1a: Rule Checker + Set Enumerator

### What was implemented

**`backend/solver/validator/rule_checker.py`** — first real solver logic; pure Python, no dependencies

- `is_valid_set(tileset, rules)` — returns True/False for any TileSet:
  - Dispatches to `_is_valid_run` or `_is_valid_group` based on `tileset.type`
  - **Run validation:** separates jokers from non-jokers; checks same-color, no duplicate
    numbers, then verifies jokers cover internal gaps (`n_max-n_min+1 - len(non_jokers) ≤ len(jokers)`);
    finally checks a valid start position `a` exists within `[1, 14-total]` containing all
    non-joker numbers; respects `rules.allow_wrap_runs`
  - **Group validation:** checks ≤4 tiles total, same number, distinct colors among non-jokers,
    and len(jokers) ≤ (4 - distinct color count)
- `is_valid_board(state, rules)` — checks every set passes `is_valid_set` and that no physical
  tile `(color, number, copy_id, is_joker)` appears more than once across all board sets

**`backend/solver/generator/set_enumerator.py`** — pre-computes candidate sets for the ILP

- `enumerate_runs(state)` — iterates 4 colors × starts 1–11 × ends start+2–13; includes a run
  template only when every required `(color, number)` has ≥1 copy in `state.all_tiles`;
  templates use `copy_id=0` as a placeholder (ILP resolves physical tile assignment)
- `enumerate_groups(state)` — iterates 13 numbers × size-3 and size-4 color combinations
  (`itertools.combinations`); same availability check
- `enumerate_valid_sets(state)` — combines runs + groups; TODO comment marks the joker-expansion
  point needed before Phase 2 ILP work

**`backend/tests/conftest.py`** — added `full_tile_pool` fixture (all 104 non-joker tiles in rack)

**`backend/tests/solver/test_rule_checker.py`** — 42 known-answer tests covering:
- Valid runs: minimal, long, full span (1–13), joker fills gap, joker extends start/end,
  two jokers, boundary cases (ending at 13, starting near 1)
- Invalid runs: too short, gap without joker, mixed colors, duplicate number, too long (14 tiles),
  span too wide for joker count
- Valid groups: size 3 and 4, with joker, boundary numbers
- Invalid groups: too short, too large (5 tiles), duplicate color, different numbers, too many jokers
- Wrap-around rule variant (disabled by default; enabled via RulesConfig)
- Board validation: empty, valid multi-set, invalid set in board, duplicate physical tile, two
  legal copies of same tile

**`backend/tests/solver/test_set_enumerator.py`** — 18 known-answer tests covering:
- Full pool: 264 runs, 65 groups, 329 total (exact arithmetic verified)
- Spot-checks: Red 4-5-6 present, Blue 1-13 present, specific groups present
- Minimal pool: only Red 4-5-6 → exactly 1 run template
- Missing tile: pool without Red 5 → no run containing 5
- Single-number pool: all four "7" tiles → exactly 5 group templates (C(4,3)+C(4,4))
- Three-color pool: only one 3-color group possible, no 4-color group
- Missing color: no groups include a color absent from the pool
- Empty pool: 0 runs, 0 groups
- Cross-validation: every enumerated template passes `is_valid_set`

### Verification (all passed before commit)
```
pytest:         88 passed, 0 failed  (28 existing + 60 new)
ruff check:     0 errors
ruff format:    clean
mypy strict:    no issues in 24 source files
```

### What is NOT here yet (next phases)
- Joker-expansion in `enumerate_valid_sets` (marked TODO — needed for ILP Phase 2)
- `solution_verifier.py` (depends on rule_checker; implements full post-solve cross-check)
- `engine/ilp_formulation.py` — ILP model construction with HiGHS (Phase 2)
- `engine/solver.py` — main orchestrator: enumerate → formulate → solve → verify (Phase 2)
- `engine/objective.py` — `compute_disruption_score` secondary objective (Phase 2)
- `generator/move_generator.py` — human-readable move instructions (Phase 2/3)
- `output/` modules — diff, formatter, explanation (Phase 3)
- `/api/solve` endpoint (Phase 2)

---

## [0.1.0] — 2026-03-21 — Project Foundation

### What was set up

**Repository skeleton**
- `.gitignore` — covers Python (`__pycache__`, `.venv`, `*.pyc`), Node (`node_modules/`, `.next/`), Docker, editor files
- `.editorconfig` — enforces LF line endings, UTF-8, 4-space indent for Python, 2-space for TS/JS/JSON/YAML
- `README.md` — project overview, architecture table, quick-start commands for backend / frontend / Docker
- `docker-compose.yml` — single `backend` service with file-watch sync for local development (no rebuild on code changes)

**Backend — `backend/`**

- `pyproject.toml` — Python 3.12+, hatchling build, all runtime deps pinned:
  `fastapi`, `uvicorn[standard]`, `pydantic>=2.8`, `highspy>=1.7`, `structlog`, `sentry-sdk[fastapi]`
  Dev deps: `pytest`, `pytest-asyncio` (auto mode), `httpx`, `hypothesis`, `ruff`, `mypy` (strict)

- `solver/models/tile.py` — `Color(StrEnum)` with four values (`blue/red/black/yellow`);
  `Tile` as a **frozen hashable dataclass** (copy_id distinguishes the two physical copies of each tile);
  `__post_init__` validates number range 1–13 and copy_id ∈ {0,1}; `Tile.joker()` factory for unassigned jokers

- `solver/models/tileset.py` — `SetType(StrEnum)` (`run`/`group`); `TileSet` dataclass holding an ordered tile list

- `solver/models/board_state.py` — `BoardState` with computed properties `board_tiles` and `all_tiles`;
  `Solution` with `tiles_placed`/`tiles_remaining` properties; `MoveInstruction` for human-readable steps

- `solver/config/rules.py` — `RulesConfig` dataclass: `initial_meld_threshold` (default 30),
  `is_first_turn`, `allow_wrap_runs`, `joker_retrieval` — all rule variants from Blueprint §1.4

- **All solver modules as stubs** (correct signatures + `raise NotImplementedError`, ready to implement):
  - `solver/generator/set_enumerator.py` — `enumerate_valid_sets`, `enumerate_runs`, `enumerate_groups`
  - `solver/generator/move_generator.py` — `generate_moves`
  - `solver/engine/ilp_formulation.py` — `build_ilp_model`
  - `solver/engine/solver.py` — `solve` (main entry point for Phase 2)
  - `solver/engine/objective.py` — `compute_disruption_score` (secondary tiebreaker objective)
  - `solver/validator/rule_checker.py` — `is_valid_set`, `is_valid_board`
  - `solver/validator/solution_verifier.py` — `verify_solution` (post-solve defense-in-depth check)
  - `solver/output/solution_formatter.py` — `format_solution`
  - `solver/output/diff_calculator.py` — `compute_diff`
  - `solver/output/explanation.py` — `describe_move`

- `api/models.py` — Pydantic v2 `SolveRequest` / `SolveResponse` and all nested types;
  `TileInput` has a `@model_validator` that enforces (color+number) OR (joker=true)

- `api/main.py` — FastAPI app with `/health` endpoint returning `{"status":"ok","version":"0.1.0"}`;
  CORS middleware (wildcard, tighten in production); `/api/solve` left as commented stub for Phase 2

- `Dockerfile` — `python:3.12-slim`, non-root `app` user, `HEALTHCHECK` via urllib, listens on port 8000

- `tests/conftest.py` — shared fixtures: `red_4`, `blue_1`, `joker_0`, `simple_run`, `simple_group`,
  `empty_board`, `board_with_one_run`, `board_with_rack`
- `tests/test_models.py` — **28 tests**, all green:
  Color enum values/count, Tile construction/validation/immutability/hashability,
  joker factory, TileSet, BoardState properties, Solution counts, MoveInstruction

**Frontend — `frontend/`**

- `package.json` — Next.js 15.2.0, React 19, Zustand 5, Tailwind CSS 3.4, TypeScript 5
- `tsconfig.json` — Next.js App Router standard config, strict mode, path alias `@/*`
- `next.config.ts` — minimal config, `reactStrictMode: true`
- `tailwind.config.ts` — content paths set; custom `tile.*` colors (`blue/red/black/yellow`) pre-defined
- `postcss.config.js` — Tailwind + autoprefixer
- `.eslintrc.json` — `next/core-web-vitals` + `next/typescript`
- `src/app/globals.css` — Tailwind directives, CSS variables for dark mode, `env(safe-area-inset-*)` body padding
- `src/app/layout.tsx` — root layout with full PWA metadata, `viewport` with `viewportFit: "cover"` for notch support
- `src/app/page.tsx` — placeholder home page (replaced in Phase 3)
- `src/types/api.ts` — TypeScript mirror of backend Pydantic models (`TileInput`, `SolveRequest`, `SolveResponse`, etc.)
- `src/store/game.ts` — Zustand v5 store: `boardSets`, `rack`, `isFirstTurn`, `isLoading`, `solution`, `error`; all CRUD actions + `reset()`
- `public/manifest.json` — PWA manifest: `standalone` display, theme color `#1e40af`, icon placeholders

**CI/CD — `.github/workflows/`**

- `backend.yml` — triggers on `backend/**` changes; runs `ruff check`, `ruff format --check`, `mypy solver/ api/`, `pytest -v`
- `frontend.yml` — triggers on `frontend/**` changes; runs `tsc --noEmit`, `next lint`, `next build`
- Both workflows use dependency caching (pip / npm)

### Verification (all passed before commit)
```
pytest:         28 passed, 0 failed
ruff check:     0 errors
ruff format:    clean
mypy strict:    no issues in 24 source files
```

### What is NOT here yet (next phases)
- ILP solver logic (`solver/engine/`, `solver/generator/`, `solver/validator/`, `solver/output/`) — Phase 1
- `/api/solve` endpoint — Phase 2
- Frontend UI components (tile grid picker, board display, solution view) — Phase 3
- Sentry integration — Phase 4
- Playwright E2E tests — Phase 4

---

## Template for future entries

```
## [0.x.0] — YYYY-MM-DD — <Phase name>

### What was added / changed
- ...

### Verification
...

### What is NOT here yet
- ...
```
