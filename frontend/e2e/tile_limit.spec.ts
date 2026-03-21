import { test, expect } from "@playwright/test";

test("tile picker disables a tile after 2 copies are added to the rack", async ({
  page,
}) => {
  await page.goto("/");

  // Use a regex so the locator matches across all label states:
  // "red 7" → "red 7 (1 in rack)" → "red 7 (max 2)"
  const btn = page.getByRole("button", { name: /^red 7/i });

  // First click: 1 copy in rack — button still enabled.
  await btn.click();
  await expect(btn).not.toBeDisabled();

  // Second click: 2 copies in rack — button is now at the maximum.
  await btn.click();
  await expect(btn).toBeDisabled();
});
