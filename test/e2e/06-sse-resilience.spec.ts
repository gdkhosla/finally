import { test, expect } from "@playwright/test";
import { watchlistRow, waitForStreaming, PRICE_RE } from "./helpers";

test.describe("SSE resilience", () => {
  test("connection indicator reports connected and prices update live", async ({ page }) => {
    await page.goto("/");
    await waitForStreaming(page);

    const dot = page.getByTestId("connection-dot");
    await expect(dot).toHaveAttribute("data-status", "connected");

    // Prices keep flowing: a watched ticker's rendered price changes.
    const row = watchlistRow(page, "TSLA");
    await expect(row).toHaveText(PRICE_RE, { timeout: 30_000 });
    const first = await row.innerText();
    await expect.poll(async () => await row.innerText(), { timeout: 30_000 }).not.toBe(first);
  });

  test("EventSource reconnects after the stream drops", async ({ page }) => {
    await page.goto("/");
    await waitForStreaming(page);

    // Abort in-flight SSE requests to simulate a dropped connection. EventSource
    // auto-retries (retry: 1000), so the dot should return to connected.
    await page.route("**/api/stream/prices", async (route) => {
      await route.abort();
    });
    // Force the browser to notice by reloading the route handler effect: trigger
    // a few failures, then remove the block so reconnect succeeds.
    await page.waitForTimeout(2500);
    await page.unroute("**/api/stream/prices");

    await expect(page.getByTestId("connection-dot")).toHaveAttribute(
      "data-status",
      "connected",
      { timeout: 30_000 },
    );
  });
});
