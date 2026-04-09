import { describe, it, expect, vi, beforeEach } from "vitest";
import { usePlayStore } from "../../store/play";
import { useGameStore } from "../../store/game";
import type { TileInput } from "../../types/api";

// ---------------------------------------------------------------------------
// Mock the API module so loadPuzzle doesn't make real HTTP calls.
// ---------------------------------------------------------------------------
vi.mock("../../lib/api", () => ({
  fetchPuzzle: vi.fn(),
  solvePuzzle: vi.fn(),
}));

// Import after vi.mock so we get the mocked version.
const { fetchPuzzle } = await import("../../lib/api");
const mockFetchPuzzle = fetchPuzzle as ReturnType<typeof vi.fn>;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const store = () => usePlayStore.getState();
const gameStore = () => useGameStore.getState();

const redTile = (n: number): TileInput => ({ color: "red", number: n, joker: false });
const blueTile = (n: number): TileInput => ({ color: "blue", number: n, joker: false });

const makePuzzleResponse = (
  boardTiles: TileInput[][] = [],
  rack: TileInput[] = [],
) => ({
  board_sets: boardTiles.map((tiles) => ({ type: "run" as const, tiles })),
  rack,
  difficulty: "easy" as const,
  tile_count: 0,
  disruption_score: 0,
  chain_depth: 0,
  is_unique: false,
  puzzle_id: "",
});

beforeEach(() => {
  store().reset();
  gameStore().reset();
  mockFetchPuzzle.mockReset();
});

// ---------------------------------------------------------------------------
// Phase 0 — initial state
// ---------------------------------------------------------------------------

describe("initial state", () => {
  it("happy path: all fields match expected defaults", () => {
    const s = store();
    expect(s.puzzle).toBeNull();
    expect(s.grid.size).toBe(0);
    expect(s.gridRows).toBe(6);
    expect(s.gridCols).toBe(16);
    expect(s.rack).toHaveLength(0);
    expect(s.detectedSets).toHaveLength(0);
    expect(s.isSolved).toBe(false);
    expect(s.past).toHaveLength(0);
    expect(s.future).toHaveLength(0);
    expect(s.selectedTile).toBeNull();
    expect(s.interactionMode).toBe("tap");
    expect(s.showValidation).toBe(true);
    expect(s.isPuzzleLoading).toBe(false);
    expect(s.error).toBeNull();
    expect(s.solveStartTime).toBeNull();
    expect(s.solveEndTime).toBeNull();
  });

  it("play store is isolated from game store", () => {
    // Mutate game store
    gameStore().setError("game error");
    gameStore().setLoading(true);
    gameStore().addRackTile(redTile(5));

    // Play store must be unaffected
    expect(store().error).toBeNull();
    expect(store().isPuzzleLoading).toBe(false);
    expect(store().rack).toHaveLength(0);

    // Mutate play store
    store().setInteractionMode("drag");

    // Game store must be unaffected
    expect(gameStore().isLoading).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// Phase 0 — loadPuzzle
// ---------------------------------------------------------------------------

describe("loadPuzzle", () => {
  it("happy path: populates grid from puzzle board_sets", async () => {
    mockFetchPuzzle.mockResolvedValueOnce(
      makePuzzleResponse([[redTile(5), redTile(6), redTile(7)]]),
    );
    await store().loadPuzzle({ difficulty: "easy" });
    expect(store().grid.size).toBe(3);
    expect(store().grid.get("0:0")?.tile.number).toBe(5);
    expect(store().grid.get("0:1")?.tile.number).toBe(6);
    expect(store().grid.get("0:2")?.tile.number).toBe(7);
  });

  it("populates rack from puzzle.rack", async () => {
    mockFetchPuzzle.mockResolvedValueOnce(
      makePuzzleResponse([], [redTile(1), blueTile(2)]),
    );
    await store().loadPuzzle({ difficulty: "easy" });
    expect(store().rack).toHaveLength(2);
    expect(store().rack[0].color).toBe("red");
    expect(store().rack[1].color).toBe("blue");
  });

  it("sets committedSnapshot equal to initial grid+rack after load", async () => {
    mockFetchPuzzle.mockResolvedValueOnce(
      makePuzzleResponse([[redTile(5), redTile(6), redTile(7)]], [redTile(8)]),
    );
    await store().loadPuzzle({ difficulty: "easy" });
    const { committedSnapshot, grid, rack } = store();
    expect(committedSnapshot.cells.size).toBe(grid.size);
    expect(committedSnapshot.rack).toHaveLength(rack.length);
    // Snapshot is a separate Map reference (not the same object)
    expect(committedSnapshot.cells).not.toBe(grid);
  });

  it("isPuzzleLoading guard prevents concurrent calls", async () => {
    let resolve!: (v: unknown) => void;
    mockFetchPuzzle.mockReturnValueOnce(new Promise((r) => { resolve = r; }));

    // Start first call — store enters loading state
    const first = store().loadPuzzle({ difficulty: "easy" });
    expect(store().isPuzzleLoading).toBe(true);

    // Second call should be a no-op while first is in flight
    await store().loadPuzzle({ difficulty: "easy" });
    expect(mockFetchPuzzle).toHaveBeenCalledTimes(1);

    // Finish first call
    resolve(makePuzzleResponse([]));
    await first;
  });

  it("sets detectedSets after loading a puzzle with board tiles", async () => {
    mockFetchPuzzle.mockResolvedValueOnce(
      makePuzzleResponse([[redTile(5), redTile(6), redTile(7)]]),
    );
    await store().loadPuzzle({ difficulty: "easy" });
    expect(store().detectedSets).toHaveLength(1);
    expect(store().detectedSets[0].tiles).toHaveLength(3);
  });

  it("resets past/future/selectedTile on new puzzle load", async () => {
    mockFetchPuzzle.mockResolvedValueOnce(makePuzzleResponse([]));
    await store().loadPuzzle({ difficulty: "easy" });
    expect(store().past).toHaveLength(0);
    expect(store().future).toHaveLength(0);
    expect(store().selectedTile).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// Phase 0 — loadPuzzle error handling
// ---------------------------------------------------------------------------

describe("loadPuzzle error handling", () => {
  it("network error stores message in state.error", async () => {
    mockFetchPuzzle.mockRejectedValueOnce(new Error("Network failure"));
    await store().loadPuzzle({ difficulty: "easy" });
    expect(store().error).toBe("Network failure");
    expect(store().isPuzzleLoading).toBe(false);
  });

  it("AbortError sets isPuzzleLoading false but does not set error", async () => {
    const abort = Object.assign(new Error("Aborted"), { name: "AbortError" });
    mockFetchPuzzle.mockRejectedValueOnce(abort);
    await store().loadPuzzle({ difficulty: "easy" });
    expect(store().error).toBeNull();
    expect(store().isPuzzleLoading).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// Phase 0 — simple actions
// ---------------------------------------------------------------------------

describe("setInteractionMode", () => {
  it("switches mode to drag", () => {
    store().setInteractionMode("drag");
    expect(store().interactionMode).toBe("drag");
  });

  it("switches mode back to tap", () => {
    store().setInteractionMode("drag");
    store().setInteractionMode("tap");
    expect(store().interactionMode).toBe("tap");
  });
});

describe("toggleValidation", () => {
  it("toggles showValidation from true to false", () => {
    expect(store().showValidation).toBe(true);
    store().toggleValidation();
    expect(store().showValidation).toBe(false);
  });

  it("toggles showValidation back to true", () => {
    store().toggleValidation();
    store().toggleValidation();
    expect(store().showValidation).toBe(true);
  });
});

describe("reset", () => {
  it("clears all fields back to initial values", async () => {
    mockFetchPuzzle.mockResolvedValueOnce(
      makePuzzleResponse([[redTile(5), redTile(6), redTile(7)]], [redTile(8)]),
    );
    await store().loadPuzzle({ difficulty: "easy" });
    store().setInteractionMode("drag");
    store().toggleValidation(); // false

    store().reset();
    const s = store();
    expect(s.puzzle).toBeNull();
    expect(s.grid.size).toBe(0);
    expect(s.rack).toHaveLength(0);
    expect(s.detectedSets).toHaveLength(0);
    expect(s.isSolved).toBe(false);
    expect(s.past).toHaveLength(0);
    expect(s.future).toHaveLength(0);
    expect(s.selectedTile).toBeNull();
    expect(s.interactionMode).toBe("tap");
    expect(s.showValidation).toBe(true);
    expect(s.error).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// Phase 2 — tap / undo / redo
// ---------------------------------------------------------------------------

// Shared puzzle setup for all Phase 2 tests:
//   Board row 0: red 5, red 6, red 7  (source: "board")
//   Rack:        red 1, blue 2

const setupPuzzle = async () => {
  mockFetchPuzzle.mockResolvedValueOnce(
    makePuzzleResponse(
      [[redTile(5), redTile(6), redTile(7)]],
      [redTile(1), blueTile(2)],
    ),
  );
  await store().loadPuzzle({ difficulty: "easy" });
};

describe("tapRackTile — Phase 2", () => {
  beforeEach(setupPuzzle);

  it("selects tile (sets selectedTile to { source: 'rack', index })", () => {
    store().tapRackTile(0);
    expect(store().selectedTile).toEqual({ source: "rack", index: 0 });
  });

  it("tapping already-selected tile deselects it", () => {
    store().tapRackTile(0);
    store().tapRackTile(0);
    expect(store().selectedTile).toBeNull();
  });

  it("tapping a different rack tile switches selection", () => {
    store().tapRackTile(0);
    store().tapRackTile(1);
    expect(store().selectedTile).toEqual({ source: "rack", index: 1 });
  });
});

describe("tapCell — Phase 2", () => {
  beforeEach(setupPuzzle);

  it("happy path: places selected rack tile onto empty cell", () => {
    store().tapRackTile(0);          // select red 1
    store().tapCell(1, 0);           // row 1 is empty
    expect(store().grid.get("1:0")?.tile.number).toBe(1);
  });

  it("removes placed tile from rack array", () => {
    store().tapRackTile(0);
    store().tapCell(1, 0);
    expect(store().rack).toHaveLength(1);
    expect(store().rack[0].color).toBe("blue"); // only blue 2 remains
  });

  it("placed tile appears in grid at correct cellKey", () => {
    store().tapRackTile(0);
    store().tapCell(1, 0);
    const placed = store().grid.get("1:0");
    expect(placed).toBeDefined();
    expect(placed?.source).toBe("rack");
    expect(placed?.tile.number).toBe(1);
  });

  it("tapping occupied cell with no selection picks it up", () => {
    // Row 0 has board tiles from the puzzle
    store().tapCell(0, 0);
    expect(store().selectedTile).toEqual({ source: "grid", row: 0, col: 0 });
  });

  it("tapping a different occupied cell switches selection", () => {
    store().tapCell(0, 0); // pick up red 5
    store().tapCell(0, 1); // switch to red 6
    expect(store().selectedTile).toEqual({ source: "grid", row: 0, col: 1 });
  });

  it("moving a grid tile preserves its source property", () => {
    // Board tile starts as "board"; moving it must keep source "board"
    store().tapCell(0, 0);  // select board tile at (0,0)
    store().tapCell(2, 0);  // move to empty row 2
    const moved = store().grid.get("2:0");
    expect(moved?.source).toBe("board");
    expect(store().grid.has("0:0")).toBe(false);
  });

  it("board-source tile: returnToRack is a no-op", () => {
    store().tapCell(0, 0);   // select board tile (source: "board")
    store().returnToRack();  // should be blocked
    // Tile must still be on grid; rack unchanged (length 2)
    expect(store().grid.has("0:0")).toBe(true);
    expect(store().rack).toHaveLength(2);
  });
});

describe("returnToRack — Phase 2", () => {
  beforeEach(setupPuzzle);

  it("rack-source grid tile returns to rack", () => {
    store().tapRackTile(0);      // select red 1
    store().tapCell(1, 0);       // place on grid
    expect(store().rack).toHaveLength(1);

    store().tapCell(1, 0);       // pick it back up (grid selection)
    store().returnToRack();
    expect(store().rack).toHaveLength(2);
    expect(store().grid.has("1:0")).toBe(false);
  });

  it("board-source grid tile is a no-op", () => {
    store().tapCell(0, 0);  // select board tile
    const rackBefore = store().rack.length;
    store().returnToRack();
    expect(store().rack).toHaveLength(rackBefore);
    expect(store().grid.has("0:0")).toBe(true);
  });
});

describe("undo / redo — Phase 2", () => {
  beforeEach(setupPuzzle);

  it("undo reverses last tile placement (tile back in rack, cell empty)", () => {
    store().tapRackTile(0);
    store().tapCell(1, 0);
    expect(store().rack).toHaveLength(1);

    store().undo();
    expect(store().rack).toHaveLength(2);
    expect(store().grid.has("1:0")).toBe(false);
  });

  it("redo re-applies the undone placement", () => {
    store().tapRackTile(0);
    store().tapCell(1, 0);
    store().undo();
    expect(store().rack).toHaveLength(2);

    store().redo();
    expect(store().rack).toHaveLength(1);
    expect(store().grid.get("1:0")?.tile.number).toBe(1);
  });

  it("new action after undo clears the future stack", () => {
    store().tapRackTile(0);
    store().tapCell(1, 0);  // place red 1
    store().undo();
    expect(store().future).toHaveLength(1);

    // New action: place blue 2 instead
    store().tapRackTile(1);
    store().tapCell(1, 0);
    expect(store().future).toHaveLength(0);
  });

  it("undo is a no-op when past is empty", () => {
    expect(store().past).toHaveLength(0);
    store().undo();
    expect(store().grid.size).toBe(3);  // board tiles still there
    expect(store().rack).toHaveLength(2);
  });

  it("redo is a no-op when future is empty", () => {
    expect(store().future).toHaveLength(0);
    store().redo();
    expect(store().grid.size).toBe(3);
    expect(store().rack).toHaveLength(2);
  });
});

// ---------------------------------------------------------------------------
// Phase 3 — commit / revert scaffolds
// ---------------------------------------------------------------------------

describe("commit / revert — Phase 3", () => {
  it.todo("commit with all valid ≥3-tile sets returns { ok: true }");
  it.todo("commit blocked when any set is invalid: returns { ok: false, reason: 'invalid_sets' }");
  it.todo("commit blocked when any set has <3 tiles: returns { ok: false, reason: 'incomplete_sets' }");
  it.todo("commit runs validateTileConservation and blocks if tiles are missing");
  it.todo("revert restores grid and rack to the last committedSnapshot");
  it.todo("isSolved becomes true when rack empty and all sets valid after placement");
});
