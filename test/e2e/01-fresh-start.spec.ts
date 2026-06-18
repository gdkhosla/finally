import { test, expect } from "@playwright/test";
import { DEFAULT_TICKERS, watchlistRow, waitForStreaming, PRICE_RE } from "./helpers";

test.describe("Fresh start", () => {
  test("default 10-ticker watchlist appears", async ({ page }) => {
    await page.goto("/");
    for (const ticker of DEFAULT_TICKERS) {
      await expect(watchlistRow(page, ticker)).toBeVisible({ timeout: 20_000 });
    }
  });

  test("$10,000 cash is shown", async ({ page }) => {
    await page.goto("/");
    const cash = page.locator("header").getByText("Cash", { exact: true });
    await expect(cash).toBeVisible();
    const value = cash.locator("xpath=following-sibling::*[1]");
    await expect(value).toContainText("10,000", { timeout: 20_000 });
  });

  test("prices are streaming (a watchlist price changes over time)", async ({ page }) => {
    await page.goto("/");
    await waitForStreaming(page);
    const aapl = watchlistRow(page, "AAPL");
    await expect(aapl).toHaveText(PRICE_RE, { timeout: 30_000 });
    const first = await aapl.innerText();
    await expect
      .poll(async () => await aapl.innerText(), { timeout: 30_000 })
      .not.toBe(first);
  });

  test("connection indicator shows connected", async ({ page }) => {
    await page.goto("/");
    await waitForStreaming(page);
  });
});
