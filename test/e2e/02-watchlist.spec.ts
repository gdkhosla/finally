import { test, expect } from "@playwright/test";
import { watchlistRow, waitForStreaming } from "./helpers";

test.describe("Watchlist add/remove", () => {
  test("add a ticker then remove it", async ({ page }) => {
    await page.goto("/");
    await waitForStreaming(page);

    const symbol = "PYPL";
    // Ensure clean state: if already present (from a prior run on a persisted
    // volume), remove it first.
    if (await watchlistRow(page, symbol).count()) {
      await removeRow(page, symbol);
    }

    await page.getByLabel("Add ticker").fill(symbol);
    await page.getByRole("button", { name: "Add", exact: true }).click();

    await expect(watchlistRow(page, symbol)).toBeVisible({ timeout: 15_000 });

    await removeRow(page, symbol);
    await expect(watchlistRow(page, symbol)).toHaveCount(0, { timeout: 15_000 });
  });
});

/** Hover the row to reveal the "remove" affordance, then click it. */
async function removeRow(page: import("@playwright/test").Page, symbol: string) {
  const row = watchlistRow(page, symbol);
  await row.hover();
  await page.getByRole("button", { name: `Remove ${symbol}`, exact: true }).click();
}
