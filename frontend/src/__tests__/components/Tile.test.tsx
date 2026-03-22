import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import Tile from "../../components/Tile";

// next-intl requires a provider in tests — mock useTranslations to return a
// simple function that echoes the key (enough for aria-label assertions).
vi.mock("next-intl", () => ({
  useTranslations: () => (key: string) => key,
}));

describe("Tile", () => {
  it("renders the tile number", () => {
    render(<Tile color="red" number={7} />);
    expect(screen.getByText("7")).toBeInTheDocument();
  });

  it("renders the joker star symbol", () => {
    render(<Tile isJoker />);
    expect(screen.getByText("★")).toBeInTheDocument();
  });

  it("renders '?' when no color or number provided", () => {
    render(<Tile />);
    expect(screen.getByText("?")).toBeInTheDocument();
  });

  it("applies xs size classes", () => {
    const { container } = render(<Tile color="blue" number={1} size="xs" />);
    const tileDiv = container.querySelector(".w-5");
    expect(tileDiv).toBeInTheDocument();
  });

  it("applies sm size classes", () => {
    const { container } = render(<Tile color="blue" number={1} size="sm" />);
    const tileDiv = container.querySelector(".w-7");
    expect(tileDiv).toBeInTheDocument();
  });

  it("applies md size classes by default", () => {
    const { container } = render(<Tile color="blue" number={1} />);
    const tileDiv = container.querySelector(".w-9");
    expect(tileDiv).toBeInTheDocument();
  });

  it("shows remove button when onRemove is provided", () => {
    const onRemove = vi.fn();
    render(<Tile color="red" number={5} onRemove={onRemove} />);
    expect(screen.getByRole("button")).toBeInTheDocument();
  });

  it("calls onRemove when remove button is clicked", async () => {
    const onRemove = vi.fn();
    render(<Tile color="red" number={5} onRemove={onRemove} />);
    await userEvent.click(screen.getByRole("button"));
    expect(onRemove).toHaveBeenCalledOnce();
  });

  it("does not show remove button without onRemove", () => {
    render(<Tile color="red" number={5} />);
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it("applies highlight ring when highlighted=true", () => {
    const { container } = render(<Tile color="red" number={5} highlighted />);
    const tileDiv = container.querySelector(".ring-2");
    expect(tileDiv).toBeInTheDocument();
  });

  it("does not apply highlight ring by default", () => {
    const { container } = render(<Tile color="red" number={5} />);
    const tileDiv = container.querySelector(".ring-2");
    expect(tileDiv).not.toBeInTheDocument();
  });
});
