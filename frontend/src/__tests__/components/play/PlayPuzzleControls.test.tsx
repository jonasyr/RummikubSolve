import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import PlayPuzzleControls from "../../../components/play/PlayPuzzleControls";
import { usePlayStore } from "../../../store/play";

vi.mock("next-intl", () => ({
  useLocale: () => "en",
  useTranslations: () => (key: string) => key,
}));

vi.mock("next/link", () => ({
  default: ({
    children,
    href,
    className,
  }: {
    children: React.ReactNode;
    href: string;
    className?: string;
  }) => (
    <a href={href} className={className}>
      {children}
    </a>
  ),
}));

describe("PlayPuzzleControls", () => {
  const loadPuzzle = vi.fn();

  beforeEach(() => {
    usePlayStore.getState().reset();
    loadPuzzle.mockReset();
    loadPuzzle.mockResolvedValue(undefined);
    usePlayStore.setState({ loadPuzzle });
  });

  it("loads the selected standard difficulty", async () => {
    render(<PlayPuzzleControls />);

    await userEvent.click(screen.getByRole("button", { name: "expert" }));
    await userEvent.click(screen.getByRole("button", { name: "getPuzzle" }));

    expect(loadPuzzle).toHaveBeenCalledWith(
      { difficulty: "expert" },
      expect.any(AbortSignal),
    );
  });

  it("loads the T1 template with the chosen seed", async () => {
    render(<PlayPuzzleControls />);

    const seedInput = screen.getByLabelText("T1 seed");
    await userEvent.clear(seedInput);
    await userEvent.type(seedInput, "15");
    await userEvent.click(screen.getByRole("button", { name: "T1 test" }));

    expect(loadPuzzle).toHaveBeenCalledWith(
      {
        difficulty: "expert",
        seed: 15,
        template_id: "T1_joker_displacement_v1",
      },
      expect.any(AbortSignal),
    );
  });
});
