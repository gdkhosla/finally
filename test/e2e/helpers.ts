import { Page, expect } from "@playwright/test";

/** Default seed watchlist per PLAN.md Section 7. */
export const DEFAULT_TICKERS = [
  "AAPL", "GOOGL", "MSFT", "AMZN", "TSLA", "NVDA", "META", "JPM", "V", "NFLX",
];

/** A watchlist row is a role=button whose accessible name starts with the ticker,
 *  e.g. "AAPL 189.86 -0.04%" or "MSFT Held 407.42 +0.02%". */
export function watchlistRow(page: Page, ticker: string) {
  return page.getByRole("button", { name: new RegExp(`^${ticker}\\b`) }).first();
}

/** Matches a rendered price like "182.10" or "1,234.56" (watchlist uses no $). */
export const PRICE_RE = /\d[\d,]*\.\d{2}/;

/** Wait until the SSE stream is connected and a watchlist price has rendered. */
export async function waitForStreaming(page: Page) {
  // The connection dot reports status; "connected" means the EventSource is open.
  const dot = page.getByTestId("connection-dot");
  await expect(dot).toHaveAttribute("data-status", "connected", { timeout: 30_000 });
  // A watchlist row should show a numeric price once the first tick arrives.
  await expect(watchlistRow(page, "AAPL")).toHaveText(PRICE_RE, { timeout: 30_000 });
}

/** Read the header Total Value as a number (strips $ and commas). */
export async function totalValue(page: Page): Promise<number> {
  const text = await metricValue(page, "Total Value");
  return parseMoney(text);
}

export async function cashValue(page: Page): Promise<number> {
  const text = await metricValue(page, "Cash");
  return parseMoney(text);
}

/** Header metrics render label + value as siblings; find by the label text. */
async function metricValue(page: Page, label: string): Promise<string> {
  const labelEl = page.locator("header").getByText(label, { exact: true });
  const valueEl = labelEl.locator("xpath=following-sibling::*[1]");
  return (await valueEl.innerText()).trim();
}

export function parseMoney(s: string): number {
  const cleaned = s.replace(/[^0-9.-]/g, "");
  return Number(cleaned);
}

/** Wait until a numeric value read by `read` differs from `from`. */
export async function waitForChange(
  page: Page,
  read: () => Promise<number>,
  from: number,
  timeout = 30_000,
) {
  await expect
    .poll(async () => await read(), { timeout, intervals: [250, 500, 1000] })
    .not.toBe(from);
}
