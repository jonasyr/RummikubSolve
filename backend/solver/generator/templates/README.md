# Template Authoring Guide

Each template is a Python module in `solver/generator/templates/` that:

1. Defines a class subclassing `Template` with `template_id`, `template_version`, `tier`.
2. Implements `generate(rng) -> TemplateInstance` using only `rng` as a randomness source.
3. Decorates the class with `@register_template`.
4. Is imported in `templates/__init__.py` to trigger auto-registration.

## Required documentation per template

Every template must include a module docstring covering the following sections:

- **Structural invariants** — what the template guarantees by construction.
- **Chain construction** — how the intended ILP solution chain produces `chain_depth ≥ declared_chain_depth`.
- **Why the heuristic solver fails** — which heuristic rules cannot fire, and why.
- **Why the puzzle is unique** — why no shorter/alternative ILP solution exists.
- **Expected rejection rates** — measured over 100 seeds, 10 attempts each.
- **Known failure modes** — edge cases that can cause gate rejection.

## Code review checklist (new templates)

- [ ] Structural invariants declared in docstring and enforced by construction.
- [ ] "Why not trivial" section present in docstring.
- [ ] Uniqueness argument present in docstring.
- [ ] No hidden randomness — only `rng.*` calls inside `generate()`.
- [ ] Unit tests: determinism, structural invariants (no ILP), gate compliance (ILP), integration.
- [ ] At least one hand-verified fixture JSON in `tests/fixtures/golden_puzzles/`.
- [ ] `mypy --strict` and `ruff check` clean on the module.

---

## T1: Joker Displacement Chain

**File:** `t1_joker_displacement.py`  
**Class:** `T1JokerDisplacementV1`  
**Template ID:** `T1_joker_displacement_v1`  
**Tier:** `expert`  
**Declared chain depth:** 3  
**Declared disruption min:** 8

### Structural invariants

- Exactly 1 joker on the board, embedded in a 4-colour group (S0).
- Rack size is always 3: one trigger tile (Z(n+2)[0]) and two completer tiles.
- The trigger tile `Z(n+2)[0]` is unconditionally blocked from trivial extension: S0 is a 4-colour group at maximum capacity — appending any 5th tile is always invalid.
- The completer tiles `X(n+3)[0]` and `Y(n+3)[0]` are copy-blocked by their respective blocker runs (which contain copy_id=1 of those tiles).
- Each rack tile has ≥ 2 candidate homes in the full enumeration (single-home gate passes).

### Chain construction (chain_depth = 3)

Four colours: C (chain), X, Y, Z.

```
Board:
  S0  GRP  [C(n+2)[0], X(n+2)[0], Y(n+2)[0], JOKER(≡Z(n+2))]
  S1  RUN  [C(n+1)[0], C(n+2)[1],  C(n+3)[0]]
  Bx  RUN  [X(n+1)[0], X(n+2)[1],  X(n+3)[1]]   blocker run for X
  By  RUN  [Y(n+1)[0], Y(n+2)[1],  Y(n+3)[1]]   blocker run for Y
  D1  GRP  [C(1)[0],   X(1)[0],    Y(1)[0]]      distractor
  D2  RUN  [Z(1)[0],   Z(2)[0],    Z(3)[0]]      distractor
  D3  RUN  [Z(11)[0],  Z(12)[0],   Z(13)[0]]     distractor

Rack: [Z(n+2)[0], X(n+3)[0], Y(n+3)[0]]
```

Intended ILP path:
1. Place `Z(n+2)[0]` in S0 → `new_A = GROUP [C(n+2)[0], X(n+2)[0], Y(n+2)[0], Z(n+2)[0]]`. Joker freed.
2. Joker enters S1, replacing `C(n+3)[0]` → `new_B = RUN [C(n+1)[0], C(n+2)[1], JOKER(≡C(n+3))]`. `C(n+3)[0]` freed.
3. `C(n+3)[0] + X(n+3)[0] + Y(n+3)[0]` → `new_C = GROUP [C(n+3), X(n+3), Y(n+3)]`.

DAG edges (from `compute_chain_depth`):
- S0 disrupted → step-4 edge: `new_A → new_B`
- S1 disrupted → step-4 edge: `new_B → new_C`
- new_C has rack tiles + board tile from disrupted S1 → step-5 edge: `new_B → new_C` (reinforced)

Longest path: `new_A → new_B → new_C` = length 2 → **chain_depth = 3** ✓

### Why the heuristic solver fails

The heuristic solver (`HeuristicSolver`) applies four rules in order:

1. **Rule 1 (single-home):** The trigger `Z(n+2)[0]` has no trivial home — S0 is at 4-tile group capacity; no board set accepts a 5th tile. Does not fire.
2. **Rule 2 (stub completion):** No board stubs exist (all sets are valid ≥3-tile sets). Does not fire.
3. **Rules 3–4 (single-set break):** Breaking any set does not produce a placement for `Z(n+2)[0]` because the trigger's only valid slot is the joker position in S0. The heuristic never attempts joker displacement.
4. **Greedy fallback:** Even if the fallback fires, it cannot place the trigger because all candidate homes require the joker to be displaced first.

Result: `HeuristicSolver.solves() == False` for all valid instances. ✓

### Why the puzzle is unique

- `Z(n+2)[0]` (trigger) has only one valid placement: S0's joker slot. All other board sets either use a different colour or number, or have no Z(n+2) adjacency.
- Once S0 is fixed (`new_A`), the joker is free. Its only valid destination is S1 — the only set where substituting for `C(n+3)[0]` keeps the run valid.
- `C(n+3)[0]` freed from S1 forms the chain-colour member in `new_C`. The completers `X(n+3)[0]` and `Y(n+3)[0]` are copy-blocked from the blocker runs, so `new_C` is their only valid group home.

`check_uniqueness` gate enforces this at runtime. Seeds that happen to allow an alternative path (~5–15%) are rejected by the gate and retried.

### Expected rejection rates

Measured over 100 seeds, 10 attempts each:

| Gate | Rejection rate |
|---|---|
| `trivial_extension` | ~0 % |
| `single_home` | ~0 % |
| `not_solvable` | ~0 % |
| `not_unique` | ~5–15 % |
| `heuristic_solved` | ~0 % |
| **Overall success rate** | **≥ 80 %** |

### Known failure modes

- **n overflow:** `n` is clamped to `{3..8}` to ensure `n+3 ≤ 11`. Values outside this range produce tile numbers > 13 (invalid).
- **Distractor collision:** If distractors accidentally use tiles adjacent in number to the chain, the trivial-extension gate can fire. The Z-colour distractors use the low (1–3) and high (11–13) ranges, always non-adjacent to the chain range n+1..n+3.
- **Uniqueness failures at low n:** When `n = 3` the chain tiles are closer to distractor low range. Tested; rejection rate is within bounds.
