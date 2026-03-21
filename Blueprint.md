# Rummikub Solver — Complete Project Blueprint

-----

## 1. Problem Framing

### 1.1 Formal Problem Statement

The Rummikub solving problem is a **constrained combinatorial optimization** problem. Given:

- A multiset **B** of tiles currently on the board, arranged in valid sets
- A multiset **R** of tiles on the player’s rack
- The universal tile domain: numbers 1–13 in four colors (blue, red, black, yellow), each appearing twice, plus 2 jokers → 106 tiles total

**Find** a partition of **B ∪ R’** (where R’ ⊆ R) into valid sets such that |R’| is maximized (i.e., the player places as many rack tiles as possible), subject to:

1. Every set is either a **run** (≥3 consecutive numbers, same color) or a **group** (≥3 same-number tiles, each a different color, max 4)
1. Every tile in B ∪ R’ belongs to exactly one set
1. No tile from B may be removed (it must remain in some valid set, though the sets themselves may be rearranged)
1. Jokers may substitute for any tile, but a joker’s identity (color/number) is determined by its set context

### 1.2 Inputs and Outputs

|                    |Description                                                             |Representation                                                |
|--------------------|------------------------------------------------------------------------|--------------------------------------------------------------|
|**Input: Board**    |All tiles currently on the table, grouped by their current sets         |List of sets, each a list of `(color, number)` or `joker`     |
|**Input: Rack**     |All tiles on the player’s rack                                          |List of `(color, number)` or `joker`                          |
|**Output: Solution**|A new valid board arrangement using all board tiles + maximum rack tiles|List of new sets, annotation of which tiles came from the rack|
|**Output: Residual**|Tiles remaining on the rack                                             |List of tiles not placed                                      |

### 1.3 Defining “Minimal Moves”

The phrase “minimal possible number of moves” is ambiguous. There are three reasonable interpretations:

1. **Maximize tiles placed from rack** — the standard Rummikub objective. Place as many tiles as possible. This is the primary optimization target.
1. **Minimize set rearrangements** — among all solutions that place the maximum tiles, prefer the one that disrupts the fewest existing sets. This is a secondary objective useful for UX (smaller visual diff).
1. **Minimize physical tile movements** — count individual tile pick-up-and-place actions. Useful for practical play but computationally harder to define.

**Recommendation:** Use a two-tier objective: **(1) maximize tiles placed from rack**, then **(2) minimize the edit distance between the old board and new board** as a tiebreaker. This gives users the best move that’s also easiest to execute physically.

### 1.4 Rule Variations That Affect Solver Design

|Variation                                                                         |Impact                                         |Recommendation                                         |
|----------------------------------------------------------------------------------|-----------------------------------------------|-------------------------------------------------------|
|**Initial meld threshold** (e.g., first play must total ≥30 points from rack only)|Adds a constraint on the first turn            |Model as a boolean flag + sum constraint               |
|**Joker retrieval** (can you swap a tile for a placed joker?)                     |Affects whether jokers are “locked” in position|Default: jokers are fully flexible during rearrangement|
|**Wrap-around runs** (does 12-13-1 form a run?)                                   |Changes run definition                         |Default: no wrap-around (most common rules)            |
|**Number of tile copies**                                                         |Affects combinatorics                          |Standard: 2 copies of each non-joker tile              |
|**Max group size**                                                                |Always 4 (one per color)                       |Hard constraint                                        |

-----

## 2. Best Solving Method

### 2.1 Recommendation: Integer Linear Programming (ILP)

**ILP is the objectively best method for this problem.** Here’s why:

The Rummikub placement problem maps naturally to an ILP formulation where binary decision variables assign tiles to sets, linear constraints enforce run/group validity, and the objective function maximizes tiles placed from the rack. Modern ILP solvers (COIN-OR CBC, HiGHS, Gurobi, CPLEX) can solve instances of this size (≤106 tiles, bounded set counts) in milliseconds to low seconds.

### 2.2 ILP Formulation Sketch

**Decision variables:**

- `x[t][s] ∈ {0,1}` — tile `t` is assigned to set `s`
- `h[t] ∈ {0,1}` — tile `t` remains in hand (only for rack tiles)
- `y[s] ∈ {0,1}` — set `s` is active (has ≥3 tiles)

**Objective:** Minimize Σ h[t] for t ∈ R (equivalently, maximize tiles placed)

**Constraints:**

- Each tile assigned to exactly one set or remains in hand
- Group constraints: same number, all different colors, size 3–4
- Run constraints: same color, consecutive numbers, size 3–13
- Joker constraints: can substitute for exactly one tile identity

The key insight from the reference materials is correct: **enumerate possible sets in advance.** Since runs are bounded (max length 13, 4 colors, various start points) and groups are bounded (13 numbers × C(4,3) + C(4,4) combinations), the total number of valid set *templates* is on the order of a few hundred. Each template either uses a given tile or doesn’t, so the ILP becomes a **set packing/covering** problem — a well-studied ILP structure that solvers handle extremely efficiently.

### 2.3 Comparison With Alternatives

|Method                             |Correctness                                   |Performance                                                          |Complexity                             |Verdict                                                                                                                                                 |
|-----------------------------------|----------------------------------------------|---------------------------------------------------------------------|---------------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------|
|**ILP**                            |Guaranteed optimal                            |Milliseconds for typical boards                                      |Moderate (formulation)                 |**Best choice**                                                                                                                                         |
|**Constraint Programming (CP-SAT)**|Guaranteed optimal                            |Comparable to ILP, sometimes faster for heavily constrained instances|Moderate                               |Strong alternative; Google OR-Tools CP-SAT is excellent                                                                                                 |
|**First-Order Logic / IDP**        |Guaranteed optimal                            |Slower (general-purpose reasoning)                                   |High (academic tool, limited ecosystem)|The Vandevelde approach is elegant but impractical for production                                                                                       |
|**Backtracking Search**            |Correct if exhaustive                         |Exponential worst-case, but prunable                                 |Low to implement                       |Viable for MVP only; doesn’t scale gracefully                                                                                                           |
|**Dynamic Programming**            |Difficult to formulate (state space too large)|Impractical                                                          |High                                   |Not suitable — state space is combinatorial, not sequential                                                                                             |
|**Reinforcement Learning**         |No correctness guarantee                      |Requires massive training; approximate                               |Very high                              |Wrong paradigm entirely. RL solves sequential decision problems under uncertainty. Rummikub solving is a single-step optimization with full information.|
|**Graph-based (matching)**         |Partial — handles groups well, runs poorly    |Fast for subproblems                                                 |Medium                                 |Useful as a preprocessor, not a standalone solver                                                                                                       |
|**SAT Solving**                    |Correct                                       |Competitive, but optimization requires iterative solving             |Medium                                 |ILP is more natural for optimization objectives                                                                                                         |
|**Greedy / Heuristic**             |No optimality guarantee                       |Very fast                                                            |Low                                    |Acceptable as a fallback if ILP times out (it won’t)                                                                                                    |

### 2.4 Why ILP Wins

1. **Guaranteed optimality.** For a game solver, approximate answers destroy trust. If the solver says “you can’t play any tiles” but the user later discovers they could have, the product is broken. ILP gives a mathematical proof of optimality.
1. **Performance at this scale.** Rummikub has at most 106 tiles and a few hundred possible sets. This is a *tiny* ILP. Modern solvers handle millions of variables; this problem is solved in single-digit milliseconds.
1. **Clean separation of concerns.** The ILP formulation cleanly separates *what a valid solution is* (constraints) from *how to find it* (solver). You can add new rule variants by adding constraints without rewriting the search algorithm.
1. **Mature ecosystem.** HiGHS (open-source, MIT-licensed, C++ with bindings everywhere) is production-ready and actively maintained. No exotic dependencies.
1. **Secondary objectives are trivial.** Adding “minimize board disruption” as a tiebreaker is one extra term in the objective function.

### 2.5 Recommended Solver: HiGHS via Python or Rust bindings

**Primary:** HiGHS — MIT-licensed, state-of-the-art open-source MIP solver, outperforms CBC on most benchmarks, has Python (`highspy`) and Rust bindings.

**Alternative:** Google OR-Tools CP-SAT — if you prefer a constraint programming formulation. Equally fast, excellent Python API, but the library is heavier.

**Do not use:** GLPK (slow), Gurobi/CPLEX (commercial licenses, unnecessary for this scale).

-----

## 3. Solver Architecture

### 3.1 Module Decomposition

```
solver/
├── models/
│   ├── tile.py          # Tile, Color, Number domain types
│   ├── tileset.py       # Run, Group, and set validation
│   └── board_state.py   # Full game state: board sets + rack
├── generator/
│   ├── set_enumerator.py    # Enumerate all valid set templates
│   └── move_generator.py    # Given state, produce candidate assignments
├── engine/
│   ├── ilp_formulation.py   # Build ILP model from game state
│   ├── solver.py            # Interface to HiGHS, solve + extract solution
│   └── objective.py         # Objective function composition (maximize placement, minimize disruption)
├── validator/
│   ├── rule_checker.py      # Validate that a board state satisfies all Rummikub rules
│   └── solution_verifier.py # Post-solve verification (defense-in-depth)
├── output/
│   ├── solution_formatter.py # Convert solver output → API response
│   ├── diff_calculator.py    # Compute visual diff (what moved where)
│   └── explanation.py        # Human-readable move instructions
└── config/
    └── rules.py             # Rule variant configuration (initial meld, joker rules, etc.)
```

### 3.2 Data Flow

```
User Input (board + rack)
    → Parse & validate tiles
    → Build BoardState
    → Enumerate valid set templates for available tiles
    → Construct ILP model
    → Solve (HiGHS)
    → Extract solution: tile → set assignments
    → Post-verify solution against rules
    → Compute diff (old board → new board)
    → Format response (new sets, tiles placed, tiles remaining, move instructions)
    → Return to API
```

### 3.3 Core Data Structures

```python
@dataclass(frozen=True)
class Tile:
    color: Color        # Enum: BLUE, RED, BLACK, YELLOW
    number: int         # 1-13
    copy_id: int        # 0 or 1 (distinguishes duplicate tiles)
    is_joker: bool = False

@dataclass
class TileSet:
    type: SetType       # Enum: RUN, GROUP
    tiles: list[Tile]   # Ordered: by number for runs, by color for groups

@dataclass
class BoardState:
    board_sets: list[TileSet]    # Current sets on the table
    rack: list[Tile]             # Player's rack
    all_tiles: list[Tile]        # board_tiles + rack (computed)

@dataclass
class Solution:
    new_sets: list[TileSet]      # Proposed new board arrangement
    placed_tiles: list[Tile]     # Tiles moved from rack to board
    remaining_rack: list[Tile]   # Tiles staying on rack
    moves: list[MoveInstruction] # Human-readable steps
    is_optimal: bool             # Did solver prove optimality?
    solve_time_ms: float
```

### 3.4 Set Enumeration Strategy

Pre-compute all valid set templates that could be formed from the available tiles (board + rack). This bounds the ILP size:

- **Runs:** For each color, for each start number `n` (1–11), for each length `l` (3–13-n+1), generate the run template. Only include templates where all required tiles exist in the available pool. ≈ 4 × ~66 = ~264 max templates.
- **Groups:** For each number (1–13), for each subset of colors with size 3 or 4, generate the group template. ≈ 13 × 5 = 65 max templates.
- **Joker expansion:** For each template, generate variants where one tile is replaced by a joker (if a joker is available).

Total candidate sets: typically 200–400. This is trivially small for an ILP.

-----

## 4. Product / App Architecture

### 4.1 High-Level Architecture

```
┌─────────────────────────────────────────────┐
│                   Client                     │
│  Next.js (React) PWA — mobile-first SPA     │
│  ┌─────────┐ ┌──────────┐ ┌──────────────┐  │
│  │ Tile    │ │ Board    │ │ Solution     │  │
│  │ Input   │ │ Viewer   │ │ Display      │  │
│  └────┬────┘ └────┬─────┘ └──────┬───────┘  │
│       └───────────┼──────────────┘           │
│                   │ REST/JSON                │
└───────────────────┼──────────────────────────┘
                    │
┌───────────────────┼──────────────────────────┐
│              API Gateway                      │
│  FastAPI (Python) — stateless                │
│  ┌────────────┐ ┌────────────┐               │
│  │ /solve     │ │ /validate  │               │
│  └─────┬──────┘ └─────┬──────┘               │
│        └──────────────┘                      │
│                │                              │
│  ┌─────────────────────────────┐             │
│  │      Solver Engine          │             │
│  │  (in-process Python + HiGHS)│             │
│  └─────────────────────────────┘             │
└──────────────────────────────────────────────┘
```

### 4.2 Component Responsibilities

**Frontend (Next.js / React)**

- Tile input UI (tap-based tile selector)
- Board state visualization (current sets)
- Solution display with animated diff
- PWA shell for offline capability and home-screen install
- Client-side input validation (duplicate checking, tile count limits)
- State management via React Context or Zustand (lightweight)

**Backend API (FastAPI)**

- Single `/api/solve` POST endpoint
- Request validation (Pydantic models)
- Rate limiting (per-IP, simple in-memory or Redis)
- Solve timeout enforcement (2s hard cap)
- CORS configuration for the frontend origin
- Health check endpoint

**Solver Engine (Python + HiGHS)**

- Runs in-process within the FastAPI worker (no IPC overhead)
- Stateless — each request is independent
- HiGHS via `highspy` binding (pip-installable, no system deps)
- Solution caching is unnecessary (solve time < 100ms)

**No database needed.** The application is stateless — there’s nothing to persist. If you later want solve history or user accounts, add a lightweight SQLite or Postgres instance, but the MVP needs zero storage.

### 4.3 API Design

```
POST /api/solve
Content-Type: application/json

{
  "board": [
    { "type": "run",   "tiles": [{"color": "red", "number": 4}, {"color": "red", "number": 5}, {"color": "red", "number": 6}] },
    { "type": "group", "tiles": [{"color": "red", "number": 1}, {"color": "blue", "number": 1}, {"color": "black", "number": 1}] }
  ],
  "rack": [
    {"color": "yellow", "number": 1},
    {"color": "red", "number": 7},
    {"joker": true}
  ],
  "rules": {
    "initial_meld_threshold": 30,
    "is_first_turn": false,
    "allow_wrap_runs": false
  }
}

→ 200 OK
{
  "status": "solved",
  "tiles_placed": 2,
  "tiles_remaining": 1,
  "solve_time_ms": 12,
  "is_optimal": true,
  "new_board": [
    { "type": "run", "tiles": [...], "new_tiles": [1] },
    ...
  ],
  "remaining_rack": [...],
  "moves": [
    { "action": "extend", "set_index": 0, "tile": {"color": "red", "number": 7}, "position": "end" },
    { "action": "create", "set": {...} }
  ]
}
```

### 4.4 Deployment / Infrastructure

|Layer               |Choice                            |Rationale                                                                               |
|--------------------|----------------------------------|----------------------------------------------------------------------------------------|
|**Frontend hosting**|Vercel (or Cloudflare Pages)      |Zero-config Next.js deployment, global CDN, free tier sufficient                        |
|**Backend hosting** |Railway, Fly.io, or a single VPS  |FastAPI + HiGHS is lightweight; a single $5/mo VPS handles hundreds of concurrent solves|
|**Container**       |Docker (single-stage Python image)|Reproducible builds; HiGHS installs cleanly via pip                                     |
|**SSL**             |Provided by hosting platform      |Mandatory for PWA                                                                       |
|**DNS**             |Cloudflare                        |Free, fast                                                                              |
|**CI/CD**           |GitHub Actions                    |Build → test → deploy on push to main                                                   |

For your existing home server setup, you could also self-host the backend behind your nginx reverse proxy alongside your other Docker services.

### 4.5 Observability

- **Error tracking:** Sentry (free tier) — both frontend (React) and backend (FastAPI)
- **Backend logging:** structlog (Python) → stdout → Docker logs
- **Metrics:** Log solve times, tile counts, and failure rates. For an MVP, structured logs are sufficient — no need for Prometheus/Grafana yet.
- **Uptime:** UptimeRobot or similar free ping monitor

### 4.6 Testing Strategy Overview

|Layer                |Tool            |Approach                                       |
|---------------------|----------------|-----------------------------------------------|
|Solver unit tests    |pytest          |Known board states → expected solutions        |
|Solver property tests|Hypothesis      |Random valid states → verify solution validity |
|API integration tests|pytest + httpx  |End-to-end request → response validation       |
|Frontend unit tests  |Vitest          |Component rendering and state logic            |
|Frontend E2E         |Playwright      |Critical user flows on mobile viewport         |
|Performance          |pytest-benchmark|Solver latency P50/P95/P99 across random inputs|

-----

## 5. Recommended Tech Stack

### 5.1 Final Stack

|Component             |Choice                                       |Justification                                                                                                                    |
|----------------------|---------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------|
|**Frontend framework**|**Next.js 15 (App Router)**                  |Best React meta-framework; SSG for the shell, client components for interactive UI; excellent mobile PWA support                 |
|**UI library**        |**Tailwind CSS + Radix UI primitives**       |Utility-first CSS for responsive design; Radix for accessible touch-friendly components; no heavy component library needed       |
|**State management**  |**Zustand**                                  |Minimal, performant, no boilerplate; perfect for managing tile selections and board state                                        |
|**Backend framework** |**FastAPI (Python)**                         |Async, fast, Pydantic validation, auto-generated OpenAPI docs; Python ecosystem gives direct access to HiGHS                     |
|**Solver language**   |**Python**                                   |HiGHS has first-class Python bindings (`highspy`); solve time is dominated by the C++ solver, not Python overhead                |
|**ILP solver**        |**HiGHS**                                    |MIT-licensed, state-of-the-art MIP performance, pip-installable, no system dependencies                                          |
|**API style**         |**REST + JSON**                              |Single endpoint, simple request/response; GraphQL is overkill; WebSockets unnecessary (solve is fast enough for request/response)|
|**Hosting (frontend)**|**Vercel**                                   |Native Next.js support, global edge network, free tier                                                                           |
|**Hosting (backend)** |**Fly.io or self-hosted Docker**             |Cheap, supports Docker; your home server is also a viable option                                                                 |
|**CI/CD**             |**GitHub Actions**                           |Free for public repos; matrix testing across Python versions                                                                     |
|**Error monitoring**  |**Sentry**                                   |Free tier, React + FastAPI integrations                                                                                          |
|**Testing**           |**pytest + Hypothesis + Vitest + Playwright**|Comprehensive coverage from unit to E2E                                                                                          |

### 5.2 Why Not [Alternative]?

- **Why not Rust for the solver?** Python is fast enough because HiGHS does the heavy lifting in C++. The Python-side overhead (building the model) is <5ms. Rust would add complexity for zero user-visible benefit.
- **Why not a SPA framework like Vite + React?** Next.js gives you SSG, PWA support, API routes (as a fallback), and better SEO for free. For a mobile-first app that should feel native, the PWA capabilities matter.
- **Why not Flask/Django?** FastAPI is faster, has better async support, auto-generates OpenAPI docs, and Pydantic validation eliminates an entire class of bugs.
- **Why not WebAssembly (solver in browser)?** Tempting but wrong. HiGHS has experimental WASM builds, but they’re less stable, harder to debug, and you lose server-side logging/monitoring. The network round-trip for a 1KB JSON payload is <50ms. Keep the solver server-side.

-----

## 6. UI / UX Recommendations

### 6.1 Tile Input — The Most Critical UX Decision

The #1 UX problem is fast, accurate tile entry on a phone screen. This is the make-or-break interaction.

**Recommended approach: Tile Grid Picker**

Display a 4×13 grid (colors as rows, numbers 1–13 as columns) + a joker button. Each cell shows availability (0, 1, or 2 remaining). Users tap to add tiles to their rack or to a board set. This is:

- **Fast:** One tap per tile, no typing
- **Error-proof:** Can’t input invalid tiles; grayed-out cells prevent over-selection
- **Scannable:** Users can visually compare the grid to their physical tiles
- **Compact:** Fits on an iPhone SE screen in landscape mode; scrollable in portrait

**Board set input:** A “New Set” button creates a slot. User taps tiles from the grid to add them to the current set. Sets are displayed as horizontal strips of colored tile chips. Real-time validation shows a checkmark or warning per set.

**Alternative considered and rejected:** Camera-based OCR. While appealing, Rummikub tiles have inconsistent fonts, angles, and lighting. OCR accuracy would be frustrating, and it adds enormous implementation complexity. Save it for a future version if at all.

### 6.2 Board Display

- **Sets as horizontal strips:** Each set is a row of colored tile chips, ordered by number. Runs and groups are visually distinguished (subtle icon or border style).
- **Scrollable board area:** Vertical scroll for many sets; each set is horizontally compact.
- **Color coding:** Use the actual Rummikub colors (blue, red, black/dark gray, yellow/orange) with high contrast on a neutral background.
- **Tile chip design:** Rounded rectangles, ~40×56px on mobile, showing number prominently with a colored background. Jokers use a distinct star/wild icon.

### 6.3 Solution Display

When a solution is returned:

1. **Summary bar:** “Place 4 tiles — 2 remain on rack” with a success color.
1. **Diff view:** Highlight newly placed tiles with a glow/pulse animation. Show “before → after” for rearranged sets using a subtle transition.
1. **Move instructions:** Ordered list: “Add red 7 to the end of Set 1”, “Create new group: blue 4, red 4, black 4”. Tapping a move highlights the relevant tiles and set.
1. **No solution state:** Clear message: “No tiles can be placed with the current board and rack.” Optionally suggest: “Try adding/removing tiles or checking your input.”

### 6.4 Touch and Mobile Specifics

- **Minimum tap target:** 44×44px (Apple HIG)
- **Haptic feedback:** On tile selection (if supported via Vibration API)
- **Swipe to remove:** Swipe a tile chip left to remove it from a set
- **Long press:** Show tile details or alternative placement
- **Landscape support:** Tile grid picker works best in landscape on phones; the app should handle both orientations gracefully
- **iPad:** Use the extra space for a side-by-side layout (board left, rack + input right)
- **Safe areas:** Respect notch/dynamic island/home indicator via `env(safe-area-inset-*)`

### 6.5 States

|State                |Display                                                         |
|---------------------|----------------------------------------------------------------|
|**Empty**            |Illustrated onboarding: “Tap tiles to build your board and rack”|
|**Input in progress**|Live validation badges on each set; tile count indicators       |
|**Solving**          |Subtle spinner or skeleton; should be <200ms so barely visible  |
|**Solution found**   |Animated reveal of new sets; summary + move list                |
|**No solution**      |Friendly message; suggest checking input                        |
|**Error**            |“Something went wrong. Try again.” + retry button; log to Sentry|

### 6.6 Accessibility

- Color is never the *only* indicator — tile numbers are always visible
- ARIA labels on tile buttons (“Add red 7 to rack”)
- Keyboard navigation for desktop use
- Reduced motion mode (disable animations via `prefers-reduced-motion`)
- Sufficient contrast ratios (WCAG AA minimum)

-----

## 7. Implementation Roadmap

### Phase 1: Solver Core (Week 1–2)

**Scope:** Build and validate the ILP solver in isolation.

- Define domain types (Tile, TileSet, BoardState, Solution)
- Implement set enumeration (all valid runs and groups for a tile pool)
- Build ILP formulation using `highspy`
- Extract and verify solutions
- Write comprehensive test suite (see §8)

**Milestone:** Given a JSON game state, the solver returns the optimal solution with proof of optimality. 100% of test cases pass.

**Risks:** HiGHS Python bindings may have rough edges on certain platforms. Mitigate by testing on Linux (Docker) early.

**Validation:** Run against all reference solver examples from the uploaded sources; compare results.

### Phase 2: API Layer (Week 2–3)

**Scope:** Wrap the solver in a FastAPI service.

- Define Pydantic request/response models
- Implement `/api/solve` endpoint
- Add input validation (tile count limits, duplicate checking)
- Add timeout enforcement (2s hard cap)
- Add rate limiting
- Dockerize the service

**Milestone:** `curl` a JSON payload and get back the correct solution with <200ms latency.

**Risks:** Minimal — FastAPI is straightforward.

### Phase 3: Frontend MVP (Week 3–5)

**Scope:** Build the mobile-first tile input UI and solution display.

- Scaffold Next.js project with Tailwind
- Build tile grid picker component
- Build board set input/display
- Build rack display
- Integrate with the solve API
- Build solution display with diff highlighting
- PWA configuration (manifest, service worker, icons)

**Milestone:** Fully functional app on iPhone Safari. User can input board + rack, solve, and see the result.

**Risks:** Tile grid sizing on small screens. Mitigate by testing on iPhone SE (smallest common viewport) from day one.

### Phase 4: Polish and Deploy (Week 5–6)

**Scope:** Production hardening.

- Error states and edge cases
- Loading/empty states
- Sentry integration (frontend + backend)
- Playwright E2E tests on mobile viewports
- Performance benchmarking (solver P99 latency)
- Deploy frontend to Vercel, backend to Fly.io (or home server)
- Domain setup, SSL

**Milestone:** Public URL, working on all modern mobile browsers, monitored.

### Phase 5: Refinement (Week 6–8)

**Scope:** UX improvements based on real usage.

- Animated solution transitions
- Move instruction improvements
- “Undo” / edit state
- History (local storage: last 10 solves)
- Share solution as image
- iPad layout optimization

-----

## 8. Testing Strategy

### 8.1 Solver Correctness (Most Critical)

**Unit tests (pytest):**

- Known-answer tests: hand-crafted board states with known optimal solutions
- Edge cases:
  - Empty board (first turn: rack-only play)
  - Empty rack (no moves possible)
  - All tiles placeable
  - Board requires complete rearrangement to place any rack tile
  - Multiple jokers
  - Duplicate tiles (both copies in play)
  - Maximum-size board (all 106 tiles)
  - Single set on board, single tile on rack

**Property-based tests (Hypothesis):**

- Generate random valid board states + random rack tiles
- Solve, then verify:
1. Every returned set is a valid run or group
1. Every board tile appears in exactly one set
1. Every placed rack tile appears in exactly one set
1. No tile appears more times than it exists
1. Remaining rack tiles + placed tiles = original rack
1. The number of tiles placed is actually maximal (by solving again with the solution as a constraint and verifying no better exists — expensive, but useful for CI)

**Regression tests:**

- Any bug found in production becomes a permanent test case
- Reference examples from all five solver projects in the uploaded document

### 8.2 Performance Tests

```python
@pytest.mark.benchmark
def test_solver_performance(benchmark):
    state = generate_random_board_state(num_board_tiles=80, num_rack_tiles=14)
    result = benchmark(solve, state)
    assert result.solve_time_ms < 500  # Hard ceiling
```

Run on CI with representative distributions:

- Small boards (10–20 tiles): P99 < 50ms
- Medium boards (40–60 tiles): P99 < 200ms
- Large boards (80–100 tiles): P99 < 1000ms

### 8.3 API Integration Tests

```python
async def test_solve_endpoint():
    async with AsyncClient(app=app) as client:
        response = await client.post("/api/solve", json=valid_payload)
        assert response.status_code == 200
        data = response.json()
        assert data["is_optimal"] is True
        assert data["tiles_placed"] >= 0
```

Test invalid inputs: missing fields, too many tiles, impossible tile references, malformed JSON.

### 8.4 Frontend Tests

- **Vitest:** Tile grid component renders correct availability counts; set builder validates correctly; solution display formats moves.
- **Playwright:** Full user flow on iPhone 14 viewport (390×844): add board sets → add rack tiles → solve → view solution. Test empty states, error states, and landscape orientation.

-----

## 9. Future Extensions

### 9.1 Puzzle Generation

**Feasibility:** High. This is the *inverse* of solving.

**Method:** Generate a random valid board. Remove a subset of tiles to form the “rack.” Solve to verify the rack tiles can be placed. Adjust until the puzzle has the desired difficulty.

**Difficulty control:**

- **Easy:** Rack tiles extend existing sets without rearrangement
- **Medium:** Rack tiles require splitting/rearranging 1–2 existing sets
- **Hard:** Rack tiles require rearranging 3+ sets; or the only solution uses joker reassignment

**Architecture impact:** Add a `generator/` module alongside the solver. The generator calls the solver internally and is exposed via a `/api/puzzle` endpoint.

### 9.2 Difficulty Levels

**Feasibility:** High, builds on puzzle generation.

**Method:** Define difficulty as a function of: (a) number of sets rearranged, (b) number of tiles moved, (c) whether jokers are involved, (d) whether the solution is unique. Generate puzzles, score them, filter by difficulty band.

### 9.3 Hint System

**Feasibility:** High.

**Method:** Solve the full problem but reveal the solution incrementally. Hint levels: (1) “You can place N tiles” → (2) “Try rearranging Set 3” → (3) “Add red 7 to Set 3” → (4) Full solution. This requires no new computation — just progressive disclosure of the existing solution.

### 9.4 Explainable Solutions

**Feasibility:** Medium. The diff-based move instructions from §3 provide basic explanations. Deeper explanations (“why this rearrangement is necessary”) would require analyzing the solver’s dual variables or doing counterfactual analysis (solve without each rearrangement and show it fails).

**Method:** For each move in the solution, attempt to solve without it. If the solve fails or places fewer tiles, the move is “necessary.” If it succeeds equally, the move is “optional.” Label moves accordingly.

### 9.5 Multiplayer / Training Mode

**Feasibility:** Medium-to-high.

**Method:** Implement a full game state manager that tracks turns, tile pools, and draws. The solver becomes an advisor that can play for a computer opponent or provide hints to the human player. This requires adding state persistence (game sessions) — the first time the app needs a database.

**Architectural impact:** Adds a game state machine, WebSocket support for real-time multiplayer, and a session store (Redis or Postgres).

### 9.6 Camera-Based Tile Input (OCR)

**Feasibility:** Medium-low. Rummikub tiles vary across editions (fonts, colors, materials). Lighting and angle add difficulty.

**Method:** Fine-tune a small object detection model (YOLOv8 or similar) on Rummikub tile images. Run inference client-side via ONNX Runtime Web or server-side. Requires collecting and labeling a training dataset of tile images.

**Recommendation:** Defer until after the core product has users. The tile grid picker is fast enough that OCR is a convenience, not a necessity.

-----

## 10. Summary and Final Recommendations

### 10.1 Final Architecture

```
                    ┌──────────────────┐
                    │   Vercel CDN     │
                    │  (Next.js PWA)   │
                    └────────┬─────────┘
                             │ HTTPS / JSON
                    ┌────────┴─────────┐
                    │    FastAPI        │
                    │  (Docker on Fly)  │
                    │  ┌─────────────┐  │
                    │  │  HiGHS ILP  │  │
                    │  │   Solver    │  │
                    │  └─────────────┘  │
                    └──────────────────┘
```

Stateless. No database. Two deployments: a static frontend and a single API container. Simple, cheap, fast.

### 10.2 Final Tech Stack

|Layer     |Technology                                                |
|----------|----------------------------------------------------------|
|Frontend  |Next.js 15, React, Tailwind CSS, Zustand, PWA             |
|Backend   |FastAPI, Python 3.12+, Pydantic                           |
|Solver    |HiGHS (`highspy`), Python formulation                     |
|Hosting   |Vercel (frontend) + Fly.io or Docker self-hosted (backend)|
|CI/CD     |GitHub Actions                                            |
|Monitoring|Sentry                                                    |
|Testing   |pytest, Hypothesis, Vitest, Playwright                    |

### 10.3 Best Algorithmic Approach

**Integer Linear Programming via HiGHS.** Pre-enumerate valid set templates, assign tiles to sets via binary variables, maximize rack tiles placed, verify solution post-solve. Guaranteed optimal, sub-second performance, clean implementation.

### 10.4 Top 5 Implementation Decisions That Matter Most

1. **Use ILP, not search/heuristics/RL.** This is the single most important decision. ILP gives correctness guarantees and millisecond solve times. Everything else is either slower, less reliable, or both. The reference materials confirm that every serious Rummikub solver uses LP/ILP or constraint programming — the Vandevelde IDP approach is the exception, and it’s less practical for production.
1. **Pre-enumerate valid set templates.** Don’t let the solver “discover” what runs and groups are possible — compute them upfront. This reduces the ILP to a set-covering problem, which is dramatically easier for solvers to handle. It also makes the formulation easier to debug and extend.
1. **Nail the tile input UX.** The solver will be fast and correct. The app’s success depends on whether users can input their game state quickly and without errors. The 4×13 tap grid is the right choice. Test it on the smallest iPhone screen from day one.
1. **Keep it stateless and simple.** No database, no user accounts, no session management for the MVP. A static frontend and a single API container. This eliminates entire categories of bugs, infrastructure costs, and operational complexity. Add state only when a feature (multiplayer, history) demands it.
1. **Post-solve verification is mandatory.** Even with a proven solver, always verify the solution against an independent rule checker before returning it to the user. This catches formulation bugs, solver edge cases, and gives you defense-in-depth. A solver that returns an invalid solution is worse than one that returns no solution.
