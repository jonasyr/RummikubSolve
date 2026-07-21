# Golden Puzzle Fixtures

Hand-crafted puzzle fixtures used as regression anchors for the heuristic solver
and structural gates.  Each file is a JSON object matching the `PuzzleResponse`
API schema so it deserializes directly via Pydantic.

## File naming

| Prefix | Meaning | Expected `HeuristicSolver.solves()` |
|--------|---------|--------------------------------------|
| `trivial_NNN.json` | Phase 7 calibration puzzles (v2 lenient gate) | `True` — trivially solvable |
| `hard_NNN.json` | Hand-crafted positions beyond the 4-rule scope | `False` — not trivially solvable |

## JSON format

```json
{
  "board_sets": [
    {
      "type": "run",
      "tiles": [
        {"color": "blue", "number": 5, "joker": false},
        {"color": "blue", "number": 6, "joker": false},
        {"color": "blue", "number": 7, "joker": false}
      ]
    }
  ],
  "rack": [
    {"color": "blue", "number": 8, "joker": false}
  ],
  "difficulty": "hard",
  "seed": null,
  "tile_count": 1,
  "disruption_score": 0,
  "chain_depth": 0,
  "is_unique": true,
  "puzzle_id": "",
  "composite_score": 0.0,
  "branching_factor": 0.0,
  "deductive_depth": 0.0,
  "red_herring_density": 0.0,
  "working_memory_load": 0.0,
  "tile_ambiguity": 0.0,
  "solution_fragility": 0.0,
  "generator_version": "hand-crafted",
  "template_id": "legacy",
  "template_version": "0"
}
```

### Tile fields

| Field | Values | Notes |
|-------|--------|-------|
| `color` | `"blue"`, `"red"`, `"black"`, `"yellow"`, `null` | Omit or use `null` for jokers |
| `number` | `1`–`13`, `null` | Omit or use `null` for jokers |
| `joker` | `true` / `false` | Set `true` for joker tiles |

**`copy_id` is not stored in JSON.**  The deserialization helper `_assign_copy_ids`
(in `api/main.py`) derives it from the order of appearance: the first tile with a
given `(color, number)` pair gets `copy_id=0`, the second gets `copy_id=1`.  To
encode two physical copies of the same tile, list it twice in sequence.

### Set type

| Value | Rule |
|-------|------|
| `"run"` | ≥ 3 consecutive numbers, same colour |
| `"group"` | ≥ 3 same number, distinct colours (max 4) |

## Deserializing a fixture into `BoardState`

```python
from pathlib import Path
from api.main import _assign_copy_ids
from api.models import PuzzleResponse
from solver.models.board_state import BoardState
from solver.models.tileset import SetType, TileSet

_FIXTURES_DIR = Path("tests/fixtures/golden_puzzles")

def load_fixture(filename: str) -> BoardState:
    puzzle = PuzzleResponse.model_validate_json(
        (_FIXTURES_DIR / filename).read_text()
    )
    all_inputs = [t for bs in puzzle.board_sets for t in bs.tiles] + puzzle.rack
    all_tiles = _assign_copy_ids(all_inputs)
    board_tile_count = sum(len(bs.tiles) for bs in puzzle.board_sets)
    board_tiles = all_tiles[:board_tile_count]
    rack = all_tiles[board_tile_count:]
    board_sets, offset = [], 0
    for bs in puzzle.board_sets:
        n = len(bs.tiles)
        board_sets.append(
            TileSet(type=SetType(bs.type), tiles=board_tiles[offset : offset + n])
        )
        offset += n
    return BoardState(board_sets=board_sets, rack=rack)
```

## Adding a new fixture

1. Create `hard_NNN.json` (or `trivial_NNN.json`) with the JSON structure above.
2. Add a test in `tests/solver/gates/test_heuristic_solver.py` under
   `TestHardPuzzleJsonFixtures` (or the trivial counterpart).
3. Verify locally: `pytest tests/solver/gates/test_heuristic_solver.py -k "fixture" -v`.

## Existing hard fixtures

| File | Scenario | Why `solves() == False` |
|------|----------|------------------------|
| `hard_001.json` | Redundant tile | Greedy places B8 in run(B5-7); Y8(cp1) has 0 homes (group already contains Y8(cp0)) |
| `hard_002.json` | Greedy trap | Rule 1 places B8, stranding R8 with no home |
| `hard_003.json` | Wrong colour | R5 cannot extend or break into the blue run |
| `hard_004.json` | Unresolvable stub | K7 completes group(B7,R7) but group(B9,R9) stays invalid |
| `hard_005.json` | Joker + incompatible rack | B3 cannot extend the red-joker run (wrong colour) |
| `hard_006.json` | Forced placement strands tile | Rule 1 forces K8 into group(B8,Y8); R9 then has 0 homes (not consecutive with run(R5-7)) |
