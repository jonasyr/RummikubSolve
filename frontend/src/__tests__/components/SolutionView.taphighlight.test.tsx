import { describe, it, expect, vi } from "vitest";
import { render } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import SolutionView from "../../components/SolutionView";
import type { SolveResponse, SetChange, TileWithOrigin } from "../../types/api";

vi.mock("next-intl", () => ({
  useTranslations: () => (key: string, params?: Record<string, unknown>) =>
    params ? `${key}:${JSON.stringify(params)}` : key,
}));

// ---------------------------------------------------------------------------
// Factories
// ---------------------------------------------------------------------------

function makeTile(
  origin: "hand" | number,
  color: TileWithOrigin["color"] = "red",
  number: number | null = 5,
): TileWithOrigin {
  return { color, number, joker: false, copy_id: 0, origin };
}

function makeJokerTile(origin: "hand" | number): TileWithOrigin {
  return { color: null, number: null, joker: true, copy_id: 0, origin };
}

function makeSetChange(
  action: SetChange["action"],
  tiles: TileWithOrigin[],
  overrides: Partial<SetChange> = {},
): SetChange {
  return {
    action,
    result_set: { type: "run", tiles },
    source_set_indices: null,
    source_description: null,
    ...overrides,
  };
}

function makeSolution(overrides: Partial<SolveResponse> = {}): SolveResponse {
  return {
    status: "solved",
    tiles_placed: 3,
    tiles_remaining: 0,
    solve_time_ms: 42,
    is_optimal: false,
    is_first_turn: false,
    new_board: [],
    remaining_rack: [],
    moves: [],
    set_changes: [],
    ...overrides,
  };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("SolutionView – tap-to-highlight", () => {
  // ── Single-tile selection ─────────────────────────────────────────────────

  it("clicking_a_tile_applies_blue_ring", async () => {
    const set_changes = [makeSetChange("new", [makeTile("hand")])];
    const { container } = render(
      <SolutionView solution={makeSolution({ set_changes })} />,
    );
    const tileEl = container.querySelector(".cursor-pointer") as HTMLElement;
    await userEvent.click(tileEl);
    expect(container.querySelector(".ring-blue-400")).toBeInTheDocument();
  });

  it("clicking_selected_tile_deselects_it", async () => {
    const set_changes = [makeSetChange("new", [makeTile("hand")])];
    const { container } = render(
      <SolutionView solution={makeSolution({ set_changes })} />,
    );
    const tileEl = container.querySelector(".cursor-pointer") as HTMLElement;
    await userEvent.click(tileEl); // select
    await userEvent.click(tileEl); // deselect
    expect(container.querySelector(".ring-blue-400")).not.toBeInTheDocument();
  });

  it("clicking_different_tile_switches_selection", async () => {
    const set_changes = [
      makeSetChange("new", [makeTile("hand", "red", 5), makeTile("hand", "blue", 7)]),
    ];
    const { container } = render(
      <SolutionView solution={makeSolution({ set_changes })} />,
    );
    const [tile1, tile2] = Array.from(
      container.querySelectorAll(".cursor-pointer"),
    ) as HTMLElement[];
    await userEvent.click(tile1);
    await userEvent.click(tile2);
    // Only the second tile's key is active → exactly one blue ring
    const blueRings = container.querySelectorAll(".ring-blue-400");
    expect(blueRings).toHaveLength(1);
  });

  // ── Cross-card highlight ──────────────────────────────────────────────────

  it("all_matching_tiles_highlighted_across_cards", async () => {
    // Two cards each containing a red 5 — clicking one should select both.
    const set_changes = [
      makeSetChange("new",      [makeTile("hand", "red", 5)]),
      makeSetChange("extended", [makeTile(0,      "red", 5)]),
    ];
    const { container } = render(
      <SolutionView solution={makeSolution({ set_changes })} />,
    );
    const firstTile = container.querySelector(".cursor-pointer") as HTMLElement;
    await userEvent.click(firstTile);
    // Both red 5 tiles should now carry .ring-blue-400
    expect(container.querySelectorAll(".ring-blue-400")).toHaveLength(2);
  });

  it("tiles_with_different_key_not_highlighted", async () => {
    const set_changes = [
      makeSetChange("new", [
        makeTile("hand", "red", 5),
        makeTile("hand", "blue", 7),
      ]),
    ];
    const { container } = render(
      <SolutionView solution={makeSolution({ set_changes })} />,
    );
    // Click the red 5 (first tile)
    const firstTile = container.querySelector(".cursor-pointer") as HTMLElement;
    await userEvent.click(firstTile);
    // Only one tile should be selected (blue 7 has a different key)
    expect(container.querySelectorAll(".ring-blue-400")).toHaveLength(1);
  });

  it("joker_tiles_all_highlighted_when_one_joker_selected", async () => {
    const set_changes = [
      makeSetChange("new",      [makeJokerTile("hand")]),
      makeSetChange("extended", [makeJokerTile(0)]),
    ];
    const { container } = render(
      <SolutionView solution={makeSolution({ set_changes })} />,
    );
    const firstTile = container.querySelector(".cursor-pointer") as HTMLElement;
    await userEvent.click(firstTile);
    expect(container.querySelectorAll(".ring-blue-400")).toHaveLength(2);
  });

  // ── State reset ───────────────────────────────────────────────────────────

  it("selection_clears_on_new_solution", async () => {
    const set_changes = [makeSetChange("new", [makeTile("hand")])];
    const sol1 = makeSolution({ set_changes });
    const sol2 = makeSolution({ set_changes });
    const { container, rerender } = render(<SolutionView solution={sol1} />);
    const tileEl = container.querySelector(".cursor-pointer") as HTMLElement;
    await userEvent.click(tileEl);
    expect(container.querySelector(".ring-blue-400")).toBeInTheDocument();
    rerender(<SolutionView solution={sol2} />);
    expect(container.querySelector(".ring-blue-400")).not.toBeInTheDocument();
  });
});
