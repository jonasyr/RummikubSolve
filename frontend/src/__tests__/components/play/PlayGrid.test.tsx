import { describe, it, expect, vi } from "vitest";
import { render } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import PlayGrid from "../../../components/play/PlayGrid";
import { cellKey } from "../../../types/play";
import type { CellKey, DetectedSet, PlacedTile } from "../../../types/play";
import type { TileInput } from "../../../types/api";

// SetOverlay uses useTranslations — mock next-intl for the whole tree.
vi.mock("next-intl", () => ({
  useTranslations: () => (key: string) => key,
}));

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const ROWS = 2;
const COLS = 3;

const redTile = (n: number): TileInput => ({ color: "red", number: n, joker: false });
const placed = (t: TileInput): PlacedTile => ({ tile: t, source: "board" });

const singleTileGrid = () =>
  new Map([[cellKey(0, 0), placed(redTile(5))]]);

const defaultProps = {
  grid: new Map<CellKey, PlacedTile>(),
  rows: ROWS,
  cols: COLS,
  detectedSets: [] as DetectedSet[],
  selectedTile: null,
  showValidation: false,
  onCellClick: vi.fn(),
};

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("PlayGrid", () => {
  it("happy path: renders correct total number of cells (rows × cols)", () => {
    const { container } = render(<PlayGrid {...defaultProps} />);
    expect(container.querySelectorAll("[data-slot-cell]")).toHaveLength(
      ROWS * COLS,
    );
  });

  it("occupied cells render Tile content (tile number visible)", () => {
    const { container } = render(
      <PlayGrid {...defaultProps} grid={singleTileGrid()} />,
    );
    // The first cell (0,0) has the tile — its text should contain the number
    const firstCell = container.querySelector("[data-slot-cell]");
    expect(firstCell?.textContent).toContain("5");
  });

  it("empty cells render as empty divs (no text content)", () => {
    const { container } = render(<PlayGrid {...defaultProps} />);
    const cells = container.querySelectorAll("[data-slot-cell]");
    cells.forEach((cell) => expect(cell.textContent).toBe(""));
  });

  it("selected grid cell has ring-blue-500 class", () => {
    const { container } = render(
      <PlayGrid
        {...defaultProps}
        grid={singleTileGrid()}
        selectedTile={{ source: "grid", row: 0, col: 0 }}
      />,
    );
    const firstCell = container.querySelector("[data-slot-cell]");
    expect(firstCell?.className).toContain("ring-blue-500");
  });

  it("empty cells get border-dashed class when a tile is selected", () => {
    const { container } = render(
      <PlayGrid
        {...defaultProps}
        selectedTile={{ source: "rack", index: 0 }}
      />,
    );
    const cells = container.querySelectorAll("[data-slot-cell]");
    // All cells are empty and selection is active → all are drop-targets
    cells.forEach((cell) =>
      expect(cell.className).toContain("border-dashed"),
    );
  });

  it("cells have no drop-target styling when selectedTile is null", () => {
    const { container } = render(<PlayGrid {...defaultProps} selectedTile={null} />);
    const cells = container.querySelectorAll("[data-slot-cell]");
    cells.forEach((cell) =>
      expect(cell.className).not.toContain("border-dashed"),
    );
  });

  it("clicking a cell calls onCellClick with correct row and col", async () => {
    const onCellClick = vi.fn();
    const { container } = render(
      <PlayGrid {...defaultProps} onCellClick={onCellClick} />,
    );
    // 2×3 grid: index 5 = row 1, col 2 (last cell)
    const cells = container.querySelectorAll("[data-slot-cell]");
    await userEvent.click(cells[5] as HTMLElement);
    expect(onCellClick).toHaveBeenCalledWith(1, 2);
  });

  it("grid container has play-surface class (touch hardening applied)", () => {
    const { container } = render(<PlayGrid {...defaultProps} />);
    expect(container.querySelector(".play-surface")).not.toBeNull();
  });
});
