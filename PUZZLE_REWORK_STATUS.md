# Puzzle Rework Status

**Reference plan:** `Puzzle Rework Plan.md`
**Last updated:** 2026-03-31
**Current version:** v0.32.0

This document tracks what has been implemented from the rework plan, what remains open, and where we deviated from the original design and why.

---

## Implemented Phases

### Phase 1 — Chain Depth Metric (`ba75f77`)

**Plan §2.1 — Core New Metric: Chain Depth**

Implemented `compute_chain_depth()` in `backend/solver/generator/puzzle_generator.py`.

- Builds a tile-origin mapping from the ILP solution's move list
- Traces which new sets contain tiles from which old sets
- Computes the longest dependency chain via topological DP
- Returns 0 for pure placement (no rearrangement)
- `chain_depth` field added to `PuzzleResult`

**Deviation:** The plan described a full DAG algorithm based on move-to-move edges. The actual implementation uses a tile-origin matrix approach that is mathematically equivalent but easier to reason about given the ILP output format.

---

### Phase 2 — Uniqueness Check + Active-Set Indices (`a6399a4`)

**Plan §2.3 — Uniqueness Constraint**

Implemented `check_uniqueness()` in `puzzle_generator.py`.

- After finding solution S1 with `tiles_placed = N`, adds exclusion constraint `Σ y[s] ≤ k−1` where S is the set of active y-variables in S1
- Re-solves; if re-solve also places N tiles → not unique; if fewer or infeasible → unique
- `is_unique` field added to `PuzzleResult`
- `active_set_indices` tracked in solver output to enable the ILP exclusion

**Deviation from plan:** The plan says uniqueness is "Required" for Nightmare and "Preferred" for Expert. The implementation computes uniqueness for Expert and Nightmare (via `_COMPUTES_UNIQUE` dict) but does **not** enforce it as a hard filter for Expert — it is informational only. Nightmare does enforce uniqueness. This avoids timeouts for Expert while still surfacing uniqueness to the frontend stats badge.

---

### Phase 3 — Generator Integration (New Difficulties) (`412d00b`)

**Plan §2.2 — New Difficulty Levels**

New difficulty constants:

| Level | Rack | Board | Min Chain | Disruption Floor |
|-------|------|-------|-----------|-----------------|
| Easy | 2–3 | 5–8 | 0 | 2 |
| Medium | 3–5 | 7–11 | 1 | 8 |
| Hard | 5–8 | 10–15 | 2 | 15 |
| Expert | 8–12 | 15–22 | 3 | 25 |
| Nightmare | 10–14 | 20–28 | 4 | 35 |

- `_MIN_CHAIN_DEPTHS` and updated `_DISRUPTION_BANDS` applied in `_attempt_generate()`
- `_SACRIFICE_COUNTS` updated per difficulty
- `Nightmare` difficulty added throughout

**Deviations:**
- **Jokers (Plan §2.4):** Not yet implemented. The plan calls for 1–2 jokers in Hard/Expert/Nightmare boards. Joker integration is tracked as **open (Phase 8)**.
- **Red Herring Scoring (Plan §2.5):** Not implemented. The plan describes a `compute_red_herring_score()` metric; this was deprioritised as it is complex and unverifiable without human playtest data.

---

### Phase 4 — Pre-Generation System (`4cba17a`)

**Plan §3 — Pre-Generation & Persistence System**

- `PuzzleStore` SQLite wrapper in `backend/solver/generator/puzzle_store.py`
- Schema matches plan exactly: `id`, `difficulty`, `board_json`, `rack_json`, `chain_depth`, `disruption`, `rack_size`, `board_size`, `is_unique`, `joker_count`, `seed`, `created_at`
- `pregenerate.py` CLI: `python -m solver.generator.pregenerate --difficulty expert --count 50`
- `joker_count` field added to `PuzzleResult`
- `data/` directory gitignored; `puzzles.db` stays out of version control

**Deviation:** The plan specifies Docker volume configuration for the DB path (`PUZZLE_DB_PATH` env var). This is tracked as **open (Phase 7b)**. The store currently resolves a default path relative to the package; for production it should be mounted as a Docker volume.

---

### Phase 5 — API Pool Integration (`29ca544`)

**Plan §3.2 — POST /api/puzzle**

- `POST /api/puzzle` endpoint added to `backend/api/main.py`
- Expert and Nightmare draw from the SQLite pool first; falls back to live generation if pool is empty
- `seen_ids[]` field in `PuzzleRequest` excludes already-seen puzzles (max 500 per plan §3.4)
- `puzzle_id` field in `PuzzleResponse` returned to frontend for tracking
- `PuzzleResponse` schema includes all rework fields: `chain_depth`, `disruption_score`, `is_unique`, `joker_count`, `difficulty`

**Deviation from plan:** The plan shows a strict pool-only model for Expert/Nightmare (no live fallback). The implementation falls back to live generation so the API never returns 503 on an empty pool. This trades off puzzle quality guarantees for availability.

---

### Phase 6 — Frontend Integration (`d7cda92`, v0.30.0)

**Frontend requirements from plan §3.4**

- Nightmare difficulty button added to `PuzzleControls.tsx`
- Stats badge shows `chain_depth`, `disruption_score`, `is_unique` after puzzle load
- `lastPuzzleMeta` state added to `useGameStore` (Zustand)
- `seenPuzzleIds` persisted in localStorage; sent as `seen_ids` with each puzzle request
- `puzzle_id` stored and deduplication tracked
- i18n keys added: EN + DE for `chainDepth`, `uniqueSolution`, all 6 difficulty labels including `nightmare`/`Albtraum`

---

### Phase 8 — Nightmare Overhaul + Joker Infrastructure (v0.32.0)

**Plan §2.4 — Joker Integration + difficulty escalation**

**DAG chain depth metric** (`objective.py`):
- Rewrote `compute_chain_depth()` from convergence-breadth to DAG longest-path using
  Kahn's BFS topological sort (cycle-safe). Old metric returned 1 for any disruption;
  new metric correctly measures sequential dependency depth.

**Updated difficulty constants** (all six dicts):
- Expert: rack (6,10), board (16,22), sacrifice 5, chain≥2, disruption≥32
- Nightmare: rack (10,14), board (22,28), sacrifice 7, chain≥3, disruption≥38

**Joker integration** (`_JOKER_COUNTS`, `_make_pool()`, `_inject_jokers_into_board()`):
- Jokers are now physically placed on the board (previously they were in the tile pool
  but never appeared because `enumerate_runs/groups` don't produce joker templates)
- `PuzzleResult.joker_count` now reflects actual board jokers (previously always 0)
- Input validation added to `_make_pool()` to guard the `copy_id ∈ {0,1}` invariant

**Pre-generation tier** (`_PREGEN_CONSTRAINTS`, `generate_puzzle(pregen=True)`):
- Strict offline thresholds: Expert (chain≥3, disrupt≥38), Nightmare (chain≥4, disrupt≥45)
- `pregenerate.py` passes `pregen=True`; pool puzzles meet the full intended spec
- Live API fallback unchanged (relaxed thresholds, guaranteed response time)

**Deviations:**
- Nightmare live chain floor is 3 (plan: 4). Chain≥4 + uniqueness gate made live
  generation infeasible (0 successes across 1500 attempts). `pregen=True` enforces chain≥4.
- Uniqueness is informational only — complete-sacrifice always yields many equivalent
  rearrangements; gating would require pure pre-generation serving.

---

### Phase 7a — Custom Mode Rework (v0.31.0)

**Extension beyond original plan (user-requested)**

The original plan was silent on Custom difficulty — it only addressed Easy/Medium/Hard/Expert/Nightmare. Custom was still connected to the old single-parameter interface (`sets_to_remove` 1–5).

Changes in this phase:

**Backend:**
- `generate_puzzle()` now accepts 4 additional Custom-only parameters: `min_board_sets`, `max_board_sets`, `min_chain_depth`, `min_disruption`
- `_attempt_generate()` applies these filters when `difficulty == "custom"`, replacing the old opaque board-size formula
- `sets_to_remove` range expanded from 1–5 to 1–8
- `_COMPUTES_UNIQUE["custom"] = True` — uniqueness is computed and stored but never enforced (informational only; complete-sacrifice rarely yields unique solutions on large boards)
- `PuzzleRequest` model updated with all 5 custom fields

**Frontend:**
- Custom panel in `PuzzleControls.tsx` replaced with a full 4-parameter panel: sets to sacrifice (1–8), board sets range (5–25), min chain depth (0–4), min disruption (0–60)
- Inline `Stepper` helper component extracted inside `PuzzleControls.tsx`
- Chain depth label annotation (none/simple/moderate/deep/expert)
- Amber slow-warning badge when strict settings detected (`minChainDepth >= 2 || minDisruption >= 20 || setsToRemove >= 6`)
- Grey uniqueness info note always shown for Custom (explains why uniqueness is not enforced)
- i18n keys: 11 new keys in EN + DE

---

## Open Items

### Immediate: Build the nightmare pool
- Run: `python -m solver.generator.pregenerate --difficulty nightmare --count 500`
- With `pregen=True` (now the default), acceptance rate ≈ 0.5% → ~2–3 per run
- Run multiple times with different seeds to build a pool of 20–50 certified puzzles
- Also run for expert: `--difficulty expert --count 200` (acceptance rate ~5–10%)

### Phase 7b — Docker + Volume Configuration

- `PUZZLE_DB_PATH` env var support in `PuzzleStore`
- `docker-compose.yml` volume mount for `puzzles.db`
- CI/CD pre-generation step documentation
- Health check endpoint should surface pool size (puzzles available per difficulty)

### Frontend — Joker display

- `joker_count` is now correctly populated in the API response
- Frontend does not yet surface joker information in the stats badge or board rendering
- Joker tiles on the board need a distinct visual treatment (e.g. wildcard icon)
- i18n keys needed: `puzzle.jokerCount` or similar

### Medium-term: Reverse-engineering generation strategy

The evaluation identifies a fundamental ceiling on the complete-sacrifice strategy:
it produces boards with many equivalent rearrangements, bounding both chain depth
and uniqueness. For genuinely unique, deeply-chained puzzles:

1. Define a target solution structure (specific rearrangement chain)
2. Construct a board that requires exactly that structure
3. Verify with the solver; check uniqueness
4. This is the path to a "Nightmare+" tier (chain ≥ 5, uniqueness required)

### Red Herring Scoring (Deprioritised)

- `compute_red_herring_score()` metric not implemented
- Requires human playtest data to validate threshold choices

### Uniqueness Enforcement

Currently informational only — complete-sacrifice yields many equivalent rearrangements.
To enforce uniqueness, either:
- Move to the reverse-engineering strategy (above), OR
- Gate pre-generation (pregen=True) on uniqueness and accept the long batch runtime

---

## Architectural Deviations Summary

| Deviation | Plan Intention | Actual Decision | Reason |
|-----------|---------------|-----------------|--------|
| Nightmare live chain floor = 3 | chain ≥ 4 | chain ≥ 3 (live), ≥ 4 (pregen) | depth ≥ 4 + uniqueness = 0% pass rate in live |
| Nightmare live disruption = 38 | ≥ 45 | ≥ 38 (live), ≥ 45 (pregen) | p90 empirical = 39 on large boards |
| Expert/Nightmare uniqueness informational | Required/Preferred filter | Computed but not gated | Complete-sacrifice has near-0% unique rate |
| Live fallback for Expert/Nightmare | Pool-only | Falls back to live if pool empty | Availability over quality |
| Jokers partially implemented | Full joker boards | Board injection done; frontend rendering open | Display work deferred |
| Red herring score omitted | Computed and scored | Not implemented | Unverifiable without playtest data |
| Custom not in original plan | 5 named difficulties | Custom fully reworked (Phase 7a) | User request |
| Docker volume not yet wired | `PUZZLE_DB_PATH` env var + volume | Default path only | Deferred (Phase 7b) |
