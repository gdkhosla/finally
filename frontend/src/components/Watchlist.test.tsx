import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { Watchlist } from "./Watchlist";
import type { PriceMap, WatchlistEntry } from "@/lib/types";

const entries: WatchlistEntry[] = [
  { ticker: "AAPL", price: 190, previous_price: 189, change: 1, change_percent: 0.5, direction: "up" },
  { ticker: "MSFT", price: 420, previous_price: 421, change: -1, change_percent: -0.2, direction: "down" },
];

const prices: PriceMap = {
  AAPL: { ticker: "AAPL", price: 200, previous_price: 199 }, // up 5.26% vs baseline 190
  MSFT: { ticker: "MSFT", price: 420, previous_price: 421 },
};

function setup(extra?: Partial<React.ComponentProps<typeof Watchlist>>) {
  const props = {
    entries,
    prices,
    baselines: { AAPL: 190, MSFT: 420 },
    sparklines: { AAPL: [190, 195, 200], MSFT: [420, 419, 420] },
    selected: "AAPL",
    heldTickers: new Set<string>(["MSFT"]),
    onSelect: vi.fn(),
    onAdd: vi.fn().mockResolvedValue(undefined),
    onRemove: vi.fn().mockResolvedValue(undefined),
    ...extra,
  } as React.ComponentProps<typeof Watchlist>;
  render(<Watchlist {...props} />);
  return props;
}

describe("Watchlist", () => {
  it("renders all watchlist tickers", () => {
    setup();
    expect(screen.getByText("AAPL")).toBeInTheDocument();
    expect(screen.getByText("MSFT")).toBeInTheDocument();
  });

  it("shows the live price from the SSE map over the seed entry price", () => {
    setup();
    expect(screen.getAllByTestId("price-cell")[0].textContent).toBe("200.00");
  });

  it("computes change since session baseline, not previous tick", () => {
    setup();
    // AAPL: (200-190)/190 = +5.26%
    expect(screen.getByText("+5.26%")).toBeInTheDocument();
  });

  it("marks held positions and hides their remove control", () => {
    setup();
    expect(screen.getByText("Held")).toBeInTheDocument();
    expect(screen.queryByLabelText("Remove MSFT")).not.toBeInTheDocument();
    expect(screen.getByLabelText("Remove AAPL")).toBeInTheDocument();
  });

  it("calls onSelect when a row is clicked", () => {
    const props = setup();
    fireEvent.click(screen.getByText("MSFT"));
    expect(props.onSelect).toHaveBeenCalledWith("MSFT");
  });

  it("submits a new ticker via the add form", () => {
    const props = setup();
    fireEvent.change(screen.getByLabelText("Add ticker"), { target: { value: "nvda" } });
    fireEvent.submit(screen.getByLabelText("Add ticker").closest("form")!);
    expect(props.onAdd).toHaveBeenCalledWith("NVDA");
  });
});
