import { test, expect } from "@playwright/test";
import { watchlistRow, waitForStreaming, PRICE_RE } from "./helpers";

const TICKER = "NVDA";

test.describe("Portfolio visualization", () => {
  test("heatmap renders a position rectangle and P&L chart has a line", async ({ page }) => {
    await page.goto("/");
    await waitForStreaming(page);
    await expect(watchlistRow(page, TICKER)).toHaveText(PRICE_RE, { timeout: 30_000 });

    // Create a position so the heatmap has something to draw.
    await page.getByLabel("Trade ticker").fill(TICKER);
    await page.getByLabel("Trade quantity").fill("1");
    await page.getByRole("button", { name: "Buy", exact: true }).click();
    await expect(page.getByRole("status")).toContainText(/Bought 1 NVDA/i, { timeout: 15_000 });

    // Heatmap: the treemap draws an SVG <rect> per position and a <text> label
    // with the ticker. Scope to the heatmap panel by its label.
    const heatmap = page.locator("section").filter({ hasText: "Positions Heatmap" });
    await expect(heatmap.locator("svg rect").first()).toBeVisible({ timeout: 15_000 });
    await expect(heatmap.locator("svg text").filter({ hasText: TICKER }).first()).toBeVisible({
      timeout: 15_000,
    });

    // P&L chart: a recharts LineChart renders an SVG <path> for the line once it
    // has >= 2 data points (snapshots + live total). Snapshots are recorded on
    // each trade, so a path should appear.
    const pnl = page.locator("section").filter({ hasText: "Portfolio Value" });
    await expect(pnl.locator("svg path").first()).toBeVisible({ timeout: 20_000 });
  });
});
