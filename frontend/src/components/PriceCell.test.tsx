import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { PriceCell } from "./PriceCell";

describe("PriceCell", () => {
  it("renders the formatted price with no flash initially", () => {
    render(<PriceCell price={191.42} />);
    const cell = screen.getByTestId("price-cell");
    expect(cell.textContent).toBe("191.42");
    expect(cell.className).not.toMatch(/flash-up|flash-down/);
  });

  it("flashes green on an uptick", () => {
    const { rerender } = render(<PriceCell price={100} />);
    rerender(<PriceCell price={101} />);
    expect(screen.getByTestId("price-cell").className).toMatch(/flash-up/);
  });

  it("flashes red on a downtick", () => {
    const { rerender } = render(<PriceCell price={100} />);
    rerender(<PriceCell price={99} />);
    expect(screen.getByTestId("price-cell").className).toMatch(/flash-down/);
  });

  it("does not flash when the price is unchanged", () => {
    const { rerender } = render(<PriceCell price={100} />);
    rerender(<PriceCell price={100} />);
    expect(screen.getByTestId("price-cell").className).not.toMatch(/flash-up|flash-down/);
  });

  it("renders a placeholder when price is null", () => {
    render(<PriceCell price={null} />);
    expect(screen.getByTestId("price-cell").textContent).toBe("--");
  });
});
