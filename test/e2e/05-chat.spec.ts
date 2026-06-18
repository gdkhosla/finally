import { test, expect } from "@playwright/test";
import { waitForStreaming, watchlistRow } from "./helpers";

/**
 * Chat runs with LLM_MOCK=true. Keying rules (TEAM_NOTES.md):
 *   "buy"    -> trade buy 1 AAPL
 *   "add"    -> watchlist add TSLA
 * Mock returns the {message, trades, watchlist_changes} schema; the frontend
 * renders an inline confirmation chip per executed action.
 */
test.describe("AI chat (mocked)", () => {
  test("a buy request renders a response and an inline trade confirmation", async ({ page }) => {
    await page.goto("/");
    await waitForStreaming(page);

    const input = page.getByLabel("Message FinAlly");
    await input.fill("please buy AAPL");
    await page.getByRole("button", { name: "Send", exact: true }).click();

    // The user message echoes, and an assistant message arrives.
    await expect(page.getByText("please buy AAPL")).toBeVisible({ timeout: 15_000 });

    // Inline trade confirmation chip: "Filled: BUY 1 AAPL @ $..." (or Rejected).
    await expect(
      page.getByText(/(Filled|Rejected):\s*BUY\s*1\s*AAPL/i),
    ).toBeVisible({ timeout: 20_000 });
  });

  test("an add request shows an inline watchlist confirmation", async ({ page }) => {
    await page.goto("/");
    await waitForStreaming(page);

    // TSLA is a default ticker; the mock issues watchlist add TSLA which is
    // idempotent. The confirmation chip "Watchlist add TSLA" should render.
    const input = page.getByLabel("Message FinAlly");
    await input.fill("please add a stock");
    await page.getByRole("button", { name: "Send", exact: true }).click();

    await expect(page.getByText(/Watchlist\s+add\s+TSLA/i)).toBeVisible({ timeout: 20_000 });
    await expect(watchlistRow(page, "TSLA")).toBeVisible({ timeout: 15_000 });
  });
});
