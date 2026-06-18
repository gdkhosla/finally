import { test, expect } from "@playwright/test";
import { watchlistRow, waitForStreaming, cashValue, PRICE_RE } from "./helpers";

const TICKER = "MSFT";

/** A positions-table row: a table row containing a cell equal to the ticker. */
function positionRow(page: import("@playwright/test").Page, ticker: string) {
  return page
    .getByRole("row")
    .filter({ has: page.getByRole("cell", { name: ticker, exact: true }) })
    .first();
}

test.describe("Trading", () => {
  test("buy shares: cash decreases and a position appears", async ({ page }) => {
    await page.goto("/");
    await waitForStreaming(page);
    // Make sure the watchlist row shows a live price before trading.
    await expect(watchlistRow(page, TICKER)).toHaveText(PRICE_RE, { timeout: 30_000 });

    const cashBefore = await cashValue(page);

    await page.getByLabel("Trade ticker").fill(TICKER);
    await page.getByLabel("Trade quantity").fill("2");
    await page.getByRole("button", { name: "Buy", exact: true }).click();

    // Inline confirmation from the trade bar.
    await expect(page.getByRole("status")).toContainText(/Bought 2 MSFT/i, { timeout: 15_000 });

    // Position appears in the positions table.
    await expect(positionRow(page, TICKER)).toBeVisible({ timeout: 15_000 });

    // Cash decreased.
    await expect
      .poll(async () => await cashValue(page), { timeout: 15_000 })
      .toBeLessThan(cashBefore);
  });

  test("sell shares: full sell removes the position row", async ({ page }) => {
    await page.goto("/");
    await waitForStreaming(page);

    // Buy a known quantity first so the test is independent.
    await page.getByLabel("Trade ticker").fill(TICKER);
    await page.getByLabel("Trade quantity").fill("3");
    await page.getByRole("button", { name: "Buy", exact: true }).click();
    await expect(page.getByRole("status")).toContainText(/Bought 3 MSFT/i, { timeout: 15_000 });
    await expect(positionRow(page, TICKER)).toBeVisible({ timeout: 15_000 });

    // Read current held quantity from the positions row (2nd cell).
    const qtyCell = positionRow(page, TICKER).getByRole("cell").nth(1);
    const heldQty = Number((await qtyCell.innerText()).replace(/[^0-9.]/g, ""));
    expect(heldQty).toBeGreaterThan(0);

    const cashBefore = await cashValue(page);

    // Sell the entire holding.
    await page.getByLabel("Trade ticker").fill(TICKER);
    await page.getByLabel("Trade quantity").fill(String(heldQty));
    await page.getByRole("button", { name: "Sell", exact: true }).click();
    await expect(page.getByRole("status")).toContainText(/Sold/i, { timeout: 15_000 });

    // Cash increased after the sell.
    await expect
      .poll(async () => await cashValue(page), { timeout: 15_000 })
      .toBeGreaterThan(cashBefore);

    // Row disappears on full sell (no zero-qty rows).
    await expect(positionRow(page, TICKER)).toHaveCount(0, { timeout: 15_000 });
  });
});
