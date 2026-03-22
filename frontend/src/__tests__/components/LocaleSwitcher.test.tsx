import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import LocaleSwitcher from "../../components/LocaleSwitcher";

// Mock next-intl locale hook
vi.mock("next-intl", () => ({
  useLocale: () => "en",
}));

// Mock next-intl navigation (createNavigation output)
const mockReplace = vi.fn();
vi.mock("../../i18n/navigation", () => ({
  useRouter: () => ({ replace: mockReplace }),
  usePathname: () => "/",
}));

describe("LocaleSwitcher", () => {
  it("renders EN and DE buttons", () => {
    render(<LocaleSwitcher />);
    expect(screen.getByRole("button", { name: "EN" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "DE" })).toBeInTheDocument();
  });

  it("active locale button has bg-blue-600 class", () => {
    render(<LocaleSwitcher />);
    const enBtn = screen.getByRole("button", { name: "EN" });
    expect(enBtn.className).toContain("bg-blue-600");
  });

  it("inactive locale button does not have bg-blue-600", () => {
    render(<LocaleSwitcher />);
    const deBtn = screen.getByRole("button", { name: "DE" });
    expect(deBtn.className).not.toContain("bg-blue-600");
  });

  it("clicking active locale does not call router.replace", async () => {
    render(<LocaleSwitcher />);
    await userEvent.click(screen.getByRole("button", { name: "EN" }));
    expect(mockReplace).not.toHaveBeenCalled();
  });

  it("clicking inactive locale calls router.replace", async () => {
    render(<LocaleSwitcher />);
    await userEvent.click(screen.getByRole("button", { name: "DE" }));
    expect(mockReplace).toHaveBeenCalledWith("/", { locale: "de" });
  });

  it("active locale button has aria-current=true", () => {
    render(<LocaleSwitcher />);
    expect(screen.getByRole("button", { name: "EN" })).toHaveAttribute(
      "aria-current",
      "true",
    );
  });

  it("inactive locale button has no aria-current", () => {
    render(<LocaleSwitcher />);
    expect(screen.getByRole("button", { name: "DE" })).not.toHaveAttribute(
      "aria-current",
    );
  });
});
