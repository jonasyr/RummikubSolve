 # RummikubSolve — Technical Audit Report

**Date:** 2026-03-21
**Auditor:** Senior Technical Audit
**Scope:** Full repository vs. Blueprint, deployment readiness for home-server + VPN

-----

## Executive Summary

RummikubSolve is a well-architected Rummikub move solver with an ILP-powered backend and a Next.js frontend. The core solver is **production-ready**: it implements the full ILP formulation from the blueprint, handles jokers, first-turn rules, board rearrangement, and post-solve verification. The frontend covers tile input, board set management, solution display with diffs, i18n (EN/DE), and basic E2E tests.

**What’s solid:**

- The ILP solver is complete and correct (147+ tests, property-based testing, post-solve verification)
- The API layer is functional with proper validation, error handling, and structured logging
- The frontend provides a working mobile-first tile input UX and solution display
- Docker Compose orchestration for both services exists
- CI/CD pipelines cover lint, type-check, unit tests, and E2E

**What’s missing for deployment:**

- No reverse-proxy / HTTPS configuration for home-server deployment
- No PWA icons (manifest references empty array)
- No dark mode support in UI components (CSS variables defined but unused)
- Several blueprint UX features not yet implemented (animations, undo, share, history)
- Puzzle generator is not started (acknowledged as future)

**Overall verdict:** The core product (solver + API + UI) is **functionally complete for an MVP**. It needs 2–3 focused sessions of work to be deployment-ready on a home server behind VPN.

-----

## Blueprint Coverage Table

### §1 — Problem Framing

|Item                                                 |Status           |Evidence                                                                                                      |Notes                                                                                                                                               |
|-----------------------------------------------------|-----------------|--------------------------------------------------------------------------------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------|
|Formal problem statement (maximize rack tiles placed)|✅ Implemented    |`ilp_formulation.py` objective: minimize Σ h[t]                                                               |Primary objective correct                                                                                                                           |
|Secondary objective (minimize disruption)            |⚠️ Partial        |`objective.py` has `compute_disruption_score()` but it is a **post-solve metric only**, not encoded in the ILP|Blueprint says “one extra term in the objective function” — not done. However, a secondary objective for **tile value** was added in v0.13.0 instead|
|Inputs: board sets + rack                            |✅ Implemented    |`api/models.py`: `SolveRequest`, `BoardSetInput`, `TileInput`                                                 |                                                                                                                                                    |
|Outputs: solution + residual + moves                 |✅ Implemented    |`api/models.py`: `SolveResponse`, `BoardSetOutput`, `MoveOutput`                                              |                                                                                                                                                    |
|Joker support                                        |✅ Implemented    |`set_enumerator.py` Type 1 + Type 2 variants; `ilp_formulation.py` joker slot handling                        |Single-joker expansion only; double-joker templates not generated (noted in CHANGELOG)                                                              |
|Initial meld threshold (first turn)                  |✅ Implemented    |`ilp_formulation.py` Constraint 3; `solver.py` rack-only sub-problem                                          |6 dedicated tests in `test_ilp_solver.py`                                                                                                           |
|Wrap-around runs config                              |✅ Implemented    |`rules.py`: `allow_wrap_runs`; `rule_checker.py`: `_is_valid_run` checks it                                   |Default: False (standard rules)                                                                                                                     |
|Joker retrieval config                               |🔲 Not implemented|`rules.py` has the field `joker_retrieval=True` but **no code** references it                                 |Stub only — no solver or validator logic uses this flag                                                                                             |
|Two-copy tile handling                               |✅ Implemented    |`_assign_copy_ids()` in `api/main.py`; v0.12.1 fix                                                            |Bug was found and fixed in v0.12.1                                                                                                                  |

### §2 — Solving Method

|Item                               |Status       |Evidence                                                                      |Notes                                                                   |
|-----------------------------------|-------------|------------------------------------------------------------------------------|------------------------------------------------------------------------|
|ILP via HiGHS                      |✅ Implemented|`ilp_formulation.py` uses `highspy`; `pyproject.toml` has `highspy>=1.7.0`    |                                                                        |
|Pre-enumerate set templates        |✅ Implemented|`set_enumerator.py`: `enumerate_runs()`, `enumerate_groups()`, joker expansion|                                                                        |
|Binary decision variables (x, h, y)|✅ Implemented|`build_ilp_model()` creates y_vars, x_vars, h_vars                            |                                                                        |
|Tile conservation constraint       |✅ Implemented|Constraint 1 in `ilp_formulation.py`                                          |                                                                        |
|Slot satisfaction constraint       |✅ Implemented|Constraint 2 in `ilp_formulation.py`                                          |                                                                        |
|First-turn threshold constraint    |✅ Implemented|Constraint 3 in `ilp_formulation.py`                                          |                                                                        |
|Solve timeout                      |✅ Implemented|`solver.py`: `_SOLVE_TIMEOUT_SECONDS = 30.0`                                  |Blueprint says 2s; was raised to 30s in v0.12.1 for complex joker boards|
|Post-solve verification            |✅ Implemented|`solution_verifier.py`: 5 verification checks                                 |Defense-in-depth as blueprint §10.4 requires                            |

### §3 — Solver Architecture

|Item                            |Status       |Evidence                                                        |Notes                                     |
|--------------------------------|-------------|----------------------------------------------------------------|------------------------------------------|
|`models/tile.py`                |✅ Implemented|Frozen dataclass, Color enum, joker factory, copy_id            |                                          |
|`models/tileset.py`             |✅ Implemented|SetType enum, TileSet dataclass                                 |                                          |
|`models/board_state.py`         |✅ Implemented|BoardState, Solution, MoveInstruction                           |                                          |
|`generator/set_enumerator.py`   |✅ Implemented|Runs, groups, joker expansion (Type 1 + Type 2)                 |Duplicate-set duplication added in v0.12.1|
|`generator/move_generator.py`   |✅ Implemented|create/extend/rearrange classification with source-set hints    |                                          |
|`engine/ilp_formulation.py`     |✅ Implemented|`build_ilp_model()` + `extract_solution()`                      |                                          |
|`engine/solver.py`              |✅ Implemented|Full orchestration: enumerate → build → solve → extract → verify|                                          |
|`engine/objective.py`           |✅ Implemented|`compute_disruption_score()` (post-solve metric only)           |                                          |
|`validator/rule_checker.py`     |✅ Implemented|`is_valid_set()`, `is_valid_board()`                            |42+ known-answer tests                    |
|`validator/solution_verifier.py`|✅ Implemented|5 verification checks including first-turn threshold            |                                          |
|`output/solution_formatter.py`  |❌ Deleted    |Removed in v0.7.0 — logic inlined in `api/main.py`              |Intentional simplification                |
|`output/diff_calculator.py`     |❌ Deleted    |Removed in v0.7.0                                               |                                          |
|`output/explanation.py`         |❌ Deleted    |Removed in v0.7.0                                               |                                          |
|`config/rules.py`               |✅ Implemented|`RulesConfig` dataclass with all 4 fields                       |`joker_retrieval` is a dead field         |

### §4 — Product / App Architecture

|Item                       |Status           |Evidence                                                            |Notes                                                   |
|---------------------------|-----------------|--------------------------------------------------------------------|--------------------------------------------------------|
|Next.js frontend           |✅ Implemented    |`frontend/package.json`: Next.js 15.2.0, React 19                   |                                                        |
|FastAPI backend            |✅ Implemented    |`backend/api/main.py`                                               |                                                        |
|REST `/api/solve` endpoint |✅ Implemented    |POST with full request/response models                              |                                                        |
|`/health` endpoint         |✅ Implemented    |Returns `{"status":"ok","version":"0.6.0"}`                         |⚠️ Version is hardcoded `0.6.0` but project is at v0.13.0|
|CORS configuration         |✅ Implemented    |`ALLOWED_ORIGIN` env var; wildcard vs. specific origin logic correct|                                                        |
|Rate limiting              |🔲 Not implemented|Blueprint §4.2 mentions “per-IP, simple in-memory or Redis”         |Not needed for VPN-only deployment with 3–4 users       |
|Solve timeout enforcement  |✅ Implemented    |30s via HiGHS `time_limit` + fallback logic                         |                                                        |
|Input validation (Pydantic)|✅ Implemented    |`api/models.py`: Field constraints, model validators                |Board set 3–13 tiles, rack max 104, board max 50 sets   |
|Stateless design (no DB)   |✅ Implemented    |No database, no sessions, no persistence                            |Correct for the use case                                |
|Docker backend             |✅ Implemented    |`backend/Dockerfile`: python:3.12-slim, non-root user, healthcheck  |                                                        |
|Docker frontend            |✅ Implemented    |`frontend/Dockerfile`: multi-stage node:22-alpine, standalone output|                                                        |
|Docker Compose             |✅ Implemented    |`docker-compose.yml`: both services, health dependency              |                                                        |
|Sentry integration         |✅ Implemented    |`api/main.py`: conditional init via `SENTRY_DSN`                    |No-op when unset — good                                 |
|structlog logging          |✅ Implemented    |JSON in production, colored console in dev                          |                                                        |
|`.env.example`             |✅ Implemented    |Documents all 4 env vars                                            |                                                        |

### §4.4 — Deployment / Infrastructure

|Item                        |Status          |Evidence                                                        |Notes                               |
|----------------------------|----------------|----------------------------------------------------------------|------------------------------------|
|Vercel frontend hosting     |🔲 Not deployed  |Blueprint suggests Vercel; project has standalone Docker instead|Docker is better for home server    |
|Fly.io / self-hosted backend|🔲 Not deployed  |Docker Compose ready but no reverse-proxy config                |Needs nginx config                  |
|SSL                         |🔲 Not configured|No TLS setup in Docker Compose or nginx config                  |Behind VPN: optional but recommended|
|CI/CD (GitHub Actions)      |✅ Implemented   |3 workflows: `backend.yml`, `frontend.yml`, `e2e.yml`           |                                    |

### §4.6 — Testing Strategy

|Item                              |Status           |Evidence                                                               |Notes                                        |
|----------------------------------|-----------------|-----------------------------------------------------------------------|---------------------------------------------|
|Solver unit tests (pytest)        |✅ Implemented    |147+ tests across 7 test files                                         |                                             |
|Solver property tests (Hypothesis)|✅ Implemented    |`test_rule_checker.py`: `test_is_valid_set_never_raises` (200 examples)|Only 1 property test; blueprint suggests more|
|API integration tests             |✅ Implemented    |`test_solve_endpoint.py`: 18 tests via httpx ASGI transport            |                                             |
|Frontend unit tests (Vitest)      |🔲 Not implemented|No Vitest config, no `__tests__/` or `*.test.tsx` files                |Blueprint §4.6 specifies Vitest              |
|Frontend E2E (Playwright)         |✅ Implemented    |5 spec files: basic run, first turn, tile limit, board section, extend |                                             |
|Performance benchmarks            |🔲 Not implemented|No `pytest-benchmark` usage, no P50/P95/P99 tracking                   |Not critical for 3–4 users                   |

### §5 — Tech Stack

|Item                   |Status       |Evidence                                    |Notes                                                                   |
|-----------------------|-------------|--------------------------------------------|------------------------------------------------------------------------|
|Next.js 15 (App Router)|✅ Implemented|App Router with `[locale]` dynamic segment  |                                                                        |
|Tailwind CSS           |✅ Implemented|`tailwind.config.ts` with custom tile colors|                                                                        |
|Radix UI primitives    |🔲 Not used   |No Radix dependency in `package.json`       |Native HTML used instead (`<details>`, `<button>`) — fine for this scale|
|Zustand                |✅ Implemented|`store/game.ts` with full CRUD actions      |                                                                        |
|FastAPI + Pydantic v2  |✅ Implemented|                                            |                                                                        |
|HiGHS (highspy)        |✅ Implemented|                                            |                                                                        |
|Sentry                 |✅ Implemented|Backend only; frontend Sentry not integrated|Blueprint says both; frontend Sentry unnecessary for VPN use            |

### §6 — UI / UX

|Item                                  |Status           |Evidence                                                                        |Notes                                          |
|--------------------------------------|-----------------|--------------------------------------------------------------------------------|-----------------------------------------------|
|Tile Grid Picker (4×13 + joker)       |✅ Implemented    |`TileGridPicker.tsx`: responsive grid, count badges, max-2 disable              |                                               |
|Board set input                       |✅ Implemented    |`BoardSection.tsx`: inline builder, auto-detect run/group                       |                                               |
|Board set editing (✎)                 |✅ Implemented    |Added in v0.7.0                                                                 |                                               |
|Board set removal (×)                 |✅ Implemented    |                                                                                |                                               |
|Solution summary bar                  |✅ Implemented    |Tiles placed, remaining, solve time, optimal badge                              |                                               |
|Solution diff view (highlighted tiles)|✅ Implemented    |`new_tile_indices` → yellow ring highlight                                      |                                               |
|4-way set-status badges               |✅ Implemented    |NEW/+/↺/unchanged with colored borders                                          |Added in v0.10.0                               |
|Move instructions                     |✅ Implemented    |Numbered, color-coded bullets with action types                                 |                                               |
|Localised move descriptions           |✅ Implemented    |Frontend reconstructs from structured data in v0.13.0                           |                                               |
|Tile sorting in runs                  |✅ Implemented    |Ascending by number in SolutionView                                             |Added in v0.13.0                               |
|Tooltips on badges                    |✅ Implemented    |`title` attribute on each badge                                                 |Added in v0.13.0                               |
|No-solution state                     |✅ Implemented    |Yellow callout; first-turn variant message                                      |                                               |
|Error state                           |✅ Implemented    |Red callout + Sentry capture                                                    |                                               |
|Empty/onboarding state                |⚠️ Partial        |“Click tiles above” and “No board sets yet” text shown                          |No illustrated onboarding as blueprint suggests|
|Solving spinner                       |⚠️ Partial        |Button text changes to “Solving…” but no skeleton/spinner animation             |Solve is <200ms so barely visible anyway       |
|Haptic feedback                       |🔲 Not implemented|No Vibration API usage                                                          |Nice-to-have                                   |
|Swipe to remove                       |🔲 Not implemented|Uses × button instead                                                           |                                               |
|Long press for details                |🔲 Not implemented|                                                                                |Not needed                                     |
|Landscape support                     |⚠️ Partial        |Grid scales via `clamp(8px, 2vw, 13px)` but no explicit landscape layout        |                                               |
|iPad side-by-side layout              |🔲 Not implemented|Single-column `max-w-xl` only                                                   |                                               |
|Safe areas (notch)                    |✅ Implemented    |`globals.css`: `env(safe-area-inset-*)` padding                                 |                                               |
|Accessibility (ARIA labels)           |✅ Implemented    |`aria-label` on tile buttons, `role="alert"` + `aria-live="assertive"` on errors|                                               |
|Reduced motion                        |🔲 Not implemented|No `prefers-reduced-motion` media query                                         |No animations exist yet anyway                 |
|Keyboard navigation                   |🔲 Not verified   |Standard HTML buttons are keyboard-accessible by default                        |Likely works via native behavior               |
|PWA manifest                          |⚠️ Partial        |`manifest.json` exists but `"icons": []` — no icons provided                    |PWA install will fail without icons            |
|PWA service worker                    |🔲 Not implemented|No service worker registration                                                  |Not critical for VPN use                       |

### §7 — Implementation Roadmap

|Phase                   |Status    |Evidence                                                                 |
|------------------------|----------|-------------------------------------------------------------------------|
|Phase 1: Solver Core    |✅ Complete|v0.1.0 + v0.2.0                                                          |
|Phase 2: API Layer      |✅ Complete|v0.3.0 + v0.5.0                                                          |
|Phase 3: Frontend MVP   |✅ Complete|v0.4.0 + v0.5.0                                                          |
|Phase 4: Polish & Deploy|⚠️ Partial |v0.6.0 (Sentry, Docker, E2E) but no actual deployment, no PWA icons      |
|Phase 5: Refinement     |⚠️ Partial |v0.7.0–v0.13.0 cover many items but not: animations, undo, history, share|

### §8 — Testing Strategy

|Item                                             |Status           |Evidence                                              |Notes                                                                           |
|-------------------------------------------------|-----------------|------------------------------------------------------|--------------------------------------------------------------------------------|
|Known-answer solver tests                        |✅ Implemented    |22 ILP tests in `test_ilp_solver.py`                  |                                                                                |
|Edge cases (empty, jokers, duplicates, max board)|✅ Implemented    |Comprehensive coverage                                |                                                                                |
|Property-based tests                             |⚠️ Minimal        |1 Hypothesis test for `is_valid_set`                  |Blueprint calls for Hypothesis on random board states with solution verification|
|Regression tests from bugs                       |✅ Implemented    |v0.12.1 fixes became test cases                       |                                                                                |
|Performance benchmarks                           |🔲 Not implemented|No `pytest-benchmark`                                 |Not critical at this scale                                                      |
|Frontend unit tests                              |🔲 Not implemented|No Vitest setup                                       |                                                                                |
|E2E on mobile viewport                           |⚠️ Partial        |Playwright uses Desktop Chrome, not iPhone SE viewport|                                                                                |

### §9 — Future Extensions

|Item                  |Status       |Notes                                                                             |
|----------------------|-------------|----------------------------------------------------------------------------------|
|Puzzle Generation     |🔲 Not started|Acknowledged as future; requires completed base                                   |
|Difficulty Levels     |🔲 Not started|Depends on puzzle generation                                                      |
|Hint System           |🔲 Not started|Progressive disclosure of existing solution — relatively easy to add              |
|Explainable Solutions |⚠️ Partial    |Move instructions exist; counterfactual analysis (“why this move”) not implemented|
|Multiplayer / Training|🔲 Not started|Requires state persistence — significant scope increase                           |
|Camera-based OCR      |🔲 Not started|Blueprint correctly defers this                                                   |

-----

## Implemented Features (Complete)

1. **ILP Solver** — Full formulation with HiGHS, pre-enumerated set templates, joker support (Type 1 + Type 2), first-turn threshold, post-solve verification
1. **REST API** — `/api/solve` with Pydantic validation, structured error responses, timeout enforcement, CORS
1. **Tile Grid Picker** — 4×13 responsive grid with count badges, max-2 enforcement, joker button
1. **Board Set Management** — Add/edit/remove sets, auto-detect run vs. group, rack-aware tile counting
1. **Solution Display** — Summary bar, 4-way set badges, highlighted new tiles, sorted runs, numbered sets
1. **Move Instructions** — Classified (create/extend/rearrange), color-coded, source-set hints, fully translated
1. **i18n** — English + German via `next-intl`, URL-based locale routing, locale switcher
1. **Rules Panel** — Collapsible “How sets work” explainer
1. **Docker Compose** — Backend + frontend containers with health dependency
1. **CI/CD** — 3 GitHub Actions workflows (backend, frontend, E2E)
1. **Observability** — Sentry (backend), structlog with env-aware formatting
1. **Error Handling** — React ErrorBoundary, AbortController for concurrent solves, reset confirmation
1. **Secondary objective** — Minimize remaining tile value when not all tiles can be placed (v0.13.0)

-----

## Partially Implemented Features

1. **Disruption scoring** — `compute_disruption_score()` exists as a post-solve metric but is **not encoded in the ILP objective**. The blueprint’s “minimize edit distance as tiebreaker” is not realized. The v0.13.0 secondary objective (minimize remaining value) is a different tiebreaker.
1. **PWA** — Manifest exists but has no icons. No service worker. The app cannot be installed as a PWA.
1. **Property-based testing** — Only 1 Hypothesis test exists. Blueprint calls for random board state generation with full solution verification.
1. **Dark mode** — CSS variables defined in `globals.css` but no component uses them. All components use hardcoded Tailwind classes (e.g., `text-gray-900`, `bg-white`).
1. **E2E viewport coverage** — Playwright tests run on Desktop Chrome. Blueprint specifies iPhone SE (smallest common viewport) and landscape orientation testing.

-----

## Missing Features

1. **Reverse proxy / HTTPS for home server** — No nginx config, no TLS certificates, no deployment instructions for home server
1. **PWA icons** — `manifest.json` has `"icons": []`
1. **Frontend unit tests (Vitest)** — No test files, no Vitest dependency
1. **Undo / edit state** — Blueprint §7 Phase 5
1. **History (local storage)** — Blueprint §7 Phase 5
1. **Share solution as image** — Blueprint §7 Phase 5
1. **Animated solution transitions** — Blueprint §7 Phase 5
1. **Rate limiting** — Blueprint §4.2 (unnecessary for VPN)
1. **Puzzle generator** — Blueprint §9.1 (acknowledged as future)
1. **Double-joker template variants** — CHANGELOG notes this gap
1. **`joker_retrieval` rule logic** — Config field exists but no code uses it
1. **iPad/tablet layout** — Single-column only

-----

## Obsolete / Unnecessary for This Deployment

|Item                                      |Why                                                           |
|------------------------------------------|--------------------------------------------------------------|
|**Rate limiting**                         |3–4 trusted users behind VPN — no abuse vector                |
|**Vercel deployment**                     |Home server with Docker is the target                         |
|**Fly.io deployment**                     |Same — Docker Compose on home server                          |
|**Frontend Sentry**                       |Overkill for 3–4 users who can report bugs directly           |
|**PWA service worker / offline**          |Behind VPN, always online when connected                      |
|**WCAG AA compliance audit**              |Trusted personal users, not public                            |
|**Camera OCR**                            |Blueprint correctly defers; too complex for the value         |
|**Multiplayer / WebSockets**              |Major scope increase, not needed for “solve my board” use case|
|**Redis for rate limiting**               |No Redis needed at all                                        |
|**Performance benchmarking (P50/P95/P99)**|Solve is <100ms for typical boards; 3–4 users won’t stress it |
|**CDN / edge network**                    |VPN access, single origin                                     |

-----

## Contradictions and Documentation Drift

### 1. Version number mismatch

- `backend/api/main.py`: `version="0.6.0"` (line in FastAPI init)
- `backend/pyproject.toml`: `version = "0.6.0"`
- `CHANGELOG.md`: latest entry is `[0.13.0]`
- `/health` endpoint returns `"version":"0.6.0"`
- **Impact:** Misleading for debugging. Should be `0.13.0`.

### 2. Solver timeout discrepancy

- Blueprint §4.2: “2s hard cap”
- `solver.py`: `_SOLVE_TIMEOUT_SECONDS = 30.0`
- CHANGELOG v0.12.1: “Solver timeout raised from 2 s to 30 s for complex joker boards”
- **Impact:** Blueprint is outdated. 30s is the correct current value. Should update Blueprint or add a comment.

### 3. Dead `output/` module directory

- Blueprint §3.1 lists `output/solution_formatter.py`, `diff_calculator.py`, `explanation.py`
- These were deleted in v0.7.0 (logic inlined in `api/main.py`)
- `solver/output/__init__.py` still exists as an empty file
- **Impact:** Confusing. Delete the empty `__init__.py`.

### 4. `joker_retrieval` config field

- `rules.py` documents the field and defaults it to `True`
- No solver, validator, or API code references `joker_retrieval`
- **Impact:** Dead code. Either implement or remove with a comment explaining why it’s deferred.

### 5. Blueprint says “Zustand or React Context” — project uses Zustand

- Not a contradiction, just noting the decision was made.

### 6. Blueprint says Radix UI — project uses native HTML

- `<details>/<summary>` for the rules panel, native `<button>` elements
- **Impact:** None. Native elements are simpler and sufficient.

### 7. CHANGELOG dates

- Every CHANGELOG entry from v0.1.0 to v0.13.0 is dated `2026-03-21` (today)
- This means the entire project was built in a single day
- **Impact:** No issue for functionality, but if you want meaningful release tracking later, consider using actual dates for future releases.

### 8. README deployment instructions

- README mentions Vercel + Fly.io but the actual target is a home server
- Docker Compose section exists but doesn’t mention VPN or reverse proxy
- **Impact:** Should be updated to reflect actual deployment target.

-----

## Risks for Home-Server Deployment

### Critical

1. **No reverse proxy configuration.** The Docker Compose exposes ports 3000 and 8000 directly. On a home server you’d typically put nginx in front. Without it:
- No TLS termination (relevant even behind VPN for local network security)
- No request buffering
- The Next.js standalone server and uvicorn are directly exposed
1. **Frontend `NEXT_PUBLIC_API_URL` is baked at build time.** The Docker Compose sets `NEXT_PUBLIC_API_URL: http://backend:8000` which is the Docker-internal hostname. A browser cannot resolve `backend`. You need to set this to the VPN-accessible URL (e.g., `http://rummikub.local:8000` or whatever your home DNS resolves to).

### Moderate

1. **No container restart policy.** `docker-compose.yml` has no `restart: unless-stopped` or `restart: always`. If the server reboots or a container crashes, services won’t auto-recover.
1. **No volume mounts for logs.** Logs go to stdout (Docker captures them), but there’s no log rotation configuration. Over months, `docker logs` output can grow unbounded.
1. **No backup strategy.** The app is stateless (no DB), so there’s nothing to back up data-wise. But the Docker images and configuration should have a documented recovery path.

### Low

1. **HiGHS solver memory.** HiGHS is a C++ solver that allocates memory per solve. With 3–4 users, no concern, but there’s no memory limit on the container.
1. **No health monitoring.** The backend has a `/health` endpoint and a Docker `HEALTHCHECK`, but there’s no external uptime monitor configured. For personal use, Docker’s built-in restart-on-unhealthy would suffice.

-----

## Recommended Next Steps (Priority Order)

### P0 — Required Before Deployment

#### 1. Fix `NEXT_PUBLIC_API_URL` for home-server access

The frontend Docker build bakes `http://backend:8000` which is unreachable from a browser. Options:

- **Option A (recommended):** Add nginx as a reverse proxy in Docker Compose that serves both frontend and proxies `/api/*` to the backend. Frontend then uses relative URLs (`NEXT_PUBLIC_API_URL=""`).
- **Option B:** Set `NEXT_PUBLIC_API_URL` to your VPN-accessible address at build time (e.g., `http://192.168.x.x:8000`).

**Files to change:** `docker-compose.yml`, `frontend/src/lib/api.ts`, potentially add `nginx.conf`

#### 2. Add container restart policy

```yaml
services:
  backend:
    restart: unless-stopped
  frontend:
    restart: unless-stopped
```

#### 3. Update version numbers

Set `version` in `pyproject.toml`, `api/main.py` (FastAPI), and `/health` response to `0.13.0`.

### P1 — Should Do Soon

#### 4. Add nginx reverse proxy to Docker Compose

A single nginx container that:

- Serves frontend on port 80 (or 443 with self-signed cert)
- Proxies `/api/*` and `/health` to the backend
- Eliminates the CORS complexity entirely (same-origin)
- Single entry point for VPN users

This is the single biggest improvement for deployment quality.

#### 5. Generate PWA icons

The manifest has `"icons": []`. Generate a set of icons (192×192, 512×512) from a simple Rummikub-themed design. Without them, mobile browsers won’t offer “Add to Home Screen.”

#### 6. Clean up dead code

- Delete `solver/output/__init__.py` (empty, module was removed in v0.7.0)
- Either implement `joker_retrieval` or remove the field from `RulesConfig` with a comment
- Delete or document the `joker_retrieval` field

### P2 — Nice to Have

#### 7. Dark mode support

CSS variables are defined but unused. Either:

- Wire up Tailwind dark mode (`dark:` variants) in components
- Or remove the CSS variables to avoid confusion

#### 8. Add `restart: on-failure` for Docker healthcheck-aware recovery

#### 9. Update README for home-server deployment

Replace Vercel/Fly.io references with actual Docker Compose instructions for home server. Include:

- VPN access note
- Reverse proxy setup
- Environment variable configuration

#### 10. Frontend Vitest setup

Blueprint calls for component unit tests. For 3–4 users this isn’t critical, but it would catch regressions in the tile picker and board section logic during future development.

### P3 — Future (After Base Is Stable)

#### 11. Puzzle Generator

Blueprint §9.1 describes a feasible approach:

- Generate random valid board → remove subset to form rack → solve to verify → score difficulty
- Expose via `/api/puzzle` endpoint
- Frontend: “Practice” mode with difficulty selector

This is the right next major feature after the base is deployed and stable.

#### 12. Double-joker template expansion

Currently only single-joker variants are generated. With 2 jokers on the board simultaneously, some solutions may be missed. Low priority — affects rare game states.

#### 13. Local history (localStorage)

Store last 10 solves in the browser. Quick to implement, nice for replay.

-----

## Final Verdict

### Production-Ready ✅

- **ILP Solver**: Correct, fast, well-tested (147+ tests), handles all standard Rummikub rules
- **API Layer**: Proper validation, error handling, structured logging, timeout enforcement
- **Core UI Flow**: Tile input → board setup → solve → view solution works end-to-end
- **i18n**: EN + DE fully translated
- **Docker Containers**: Both build and run correctly

### Not Ready ❌

- **Deployment configuration**: No reverse proxy, no restart policy, incorrect `NEXT_PUBLIC_API_URL` for browser access
- **PWA install**: No icons, no service worker
- **Version tracking**: Hardcoded at 0.6.0 despite being at 0.13.0

### Must Do Before Deployment

1. Fix `NEXT_PUBLIC_API_URL` so the browser can reach the backend (nginx proxy or correct address)
1. Add `restart: unless-stopped` to Docker Compose
1. Update version numbers to 0.13.0
1. (Strongly recommended) Add nginx reverse proxy for single-port access

### Estimated Effort

|Task                                       |Time          |
|-------------------------------------------|--------------|
|nginx reverse proxy + Docker Compose update|1–2 hours     |
|Fix API URL + test from browser            |30 min        |
|Restart policy + version bump              |15 min        |
|PWA icons                                  |30 min        |
|README update for home server              |30 min        |
|**Total for deployment-ready**             |**~3–4 hours**|

-----

## Appendix: File Inventory

### Backend (19 source files, 7 test files)

```
backend/
├── api/main.py              — FastAPI app, /health, /api/solve
├── api/models.py            — Pydantic request/response models
├── solver/config/rules.py   — RulesConfig
├── solver/models/tile.py    — Tile, Color
├── solver/models/tileset.py — TileSet, SetType
├── solver/models/board_state.py — BoardState, Solution, MoveInstruction
├── solver/engine/ilp_formulation.py — ILP model construction + extraction
├── solver/engine/solver.py  — Main orchestrator
├── solver/engine/objective.py — Disruption score (post-solve)
├── solver/generator/set_enumerator.py — Template enumeration
├── solver/generator/move_generator.py — Move instruction generation
├── solver/validator/rule_checker.py — Independent rule validation
├── solver/validator/solution_verifier.py — Post-solve verification
├── solver/output/__init__.py — DEAD (should delete)
├── tests/test_models.py — 31 tests
├── tests/api/test_solve_endpoint.py — 18 tests
├── tests/solver/test_rule_checker.py — 42+ tests
├── tests/solver/test_set_enumerator.py — 18 tests
├── tests/solver/test_ilp_solver.py — 22 tests
├── tests/solver/test_solution_verifier.py — 9 tests
├── tests/solver/test_move_generator.py — 7 tests
├── tests/solver/test_objective.py — 5 tests
```

### Frontend (17 source files, 5 E2E specs)

```
frontend/src/
├── app/layout.tsx — Root pass-through
├── app/globals.css — Tailwind + CSS variables
├── app/[locale]/layout.tsx — Locale-aware layout
├── app/[locale]/page.tsx — Main page
├── components/BoardSection.tsx — Board set management
├── components/RackSection.tsx — Rack input
├── components/SolutionView.tsx — Solution display
├── components/Tile.tsx — Tile chip component
├── components/TileGridPicker.tsx — 4×13 picker grid
├── components/RulesPanel.tsx — Collapsible rules explainer
├── components/ErrorBoundary.tsx — Error boundary + translated wrapper
├── components/LocaleSwitcher.tsx — EN/DE toggle
├── store/game.ts — Zustand store
├── lib/api.ts — API client
├── types/api.ts — TypeScript API types
├── i18n/ — 6 files (config, routing, request, navigation, messages/en.json, messages/de.json)
├── middleware.ts — next-intl middleware

frontend/e2e/
├── solve_basic_run.spec.ts
├── solve_first_turn.spec.ts
├── tile_limit.spec.ts
├── board_section.spec.ts
├── extend_board_set.spec.ts
```
