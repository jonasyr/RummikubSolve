import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import PuzzleControls from "../../components/PuzzleControls";

vi.mock("next-intl", () => ({
  useTranslations: () => (key: string) => key,
}));

// Allow tests to control these values before each render.
const mockLoadPuzzle = vi.fn();
let mockIsPuzzleLoading = false;

vi.mock("../../store/game", () => ({
  useGameStore: (selector: (s: object) => unknown) =>
    selector({ isPuzzleLoading: mockIsPuzzleLoading, loadPuzzle: mockLoadPuzzle }),
}));

describe("PuzzleControls", () => {
  beforeEach(() => {
    mockLoadPuzzle.mockReset();
    mockIsPuzzleLoading = false;
  });

  it("renders Easy, Medium, and Hard difficulty buttons", () => {
    render(<PuzzleControls />);
    expect(screen.getByRole("button", { name: "easy" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "medium" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "hard" })).toBeInTheDocument();
  });

  it("medium is selected by default (has bg-blue-600 class)", () => {
    render(<PuzzleControls />);
    expect(screen.getByRole("button", { name: "medium" }).className).toContain(
      "bg-blue-600",
    );
  });

  it("unselected difficulty buttons do not have bg-blue-600", () => {
    render(<PuzzleControls />);
    expect(screen.getByRole("button", { name: "easy" }).className).not.toContain(
      "bg-blue-600",
    );
    expect(screen.getByRole("button", { name: "hard" }).className).not.toContain(
      "bg-blue-600",
    );
  });

  it("clicking a difficulty button selects it", async () => {
    render(<PuzzleControls />);
    await userEvent.click(screen.getByRole("button", { name: "hard" }));
    expect(screen.getByRole("button", { name: "hard" }).className).toContain(
      "bg-blue-600",
    );
    expect(screen.getByRole("button", { name: "medium" }).className).not.toContain(
      "bg-blue-600",
    );
  });

  it("Get Puzzle button is disabled while isPuzzleLoading is true", () => {
    mockIsPuzzleLoading = true;
    render(<PuzzleControls />);
    // When loading, the button renders "⟳ loading" (spinner + translated key).
    // Match via accessible-name substring so the test is independent of the
    // spinner character.
    expect(screen.getByRole("button", { name: /loading/i })).toBeDisabled();
  });

  it("Get Puzzle button calls loadPuzzle with selected difficulty", async () => {
    render(<PuzzleControls />);
    await userEvent.click(screen.getByRole("button", { name: "getButton" }));
    expect(mockLoadPuzzle).toHaveBeenCalledOnce();
    expect(mockLoadPuzzle).toHaveBeenCalledWith(
      "medium",
      expect.any(AbortSignal),
    );
  });

  it("clicking Easy then Get Puzzle calls loadPuzzle with 'easy'", async () => {
    render(<PuzzleControls />);
    await userEvent.click(screen.getByRole("button", { name: "easy" }));
    await userEvent.click(screen.getByRole("button", { name: "getButton" }));
    expect(mockLoadPuzzle).toHaveBeenCalledWith(
      "easy",
      expect.any(AbortSignal),
    );
  });
});
