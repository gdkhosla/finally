import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { ChatPanel } from "./ChatPanel";
import type { ChatMessage } from "@/lib/types";

const messages: ChatMessage[] = [
  { role: "user", content: "Buy 10 NVDA" },
  {
    role: "assistant",
    content: "Done. Bought 10 shares of NVDA.",
    trades: [{ ticker: "NVDA", side: "buy", quantity: 10, ok: true, fill_price: 870 }],
  },
];

function setup(extra?: Partial<React.ComponentProps<typeof ChatPanel>>) {
  const props = {
    messages,
    busy: false,
    open: true,
    onToggle: vi.fn(),
    onSend: vi.fn(),
    ...extra,
  } as React.ComponentProps<typeof ChatPanel>;
  render(<ChatPanel {...props} />);
  return props;
}

describe("ChatPanel", () => {
  it("renders user and assistant messages", () => {
    setup();
    expect(screen.getByText("Buy 10 NVDA")).toBeInTheDocument();
    expect(screen.getByText("Done. Bought 10 shares of NVDA.")).toBeInTheDocument();
  });

  it("renders an inline trade confirmation for executed trades", () => {
    setup();
    expect(screen.getByText(/Filled: BUY 10 NVDA/)).toBeInTheDocument();
  });

  it("renders a rejection for a failed trade", () => {
    setup({
      messages: [
        {
          role: "assistant",
          content: "Could not fill.",
          trades: [{ ticker: "AAPL", side: "buy", quantity: 999, ok: false, error: "Insufficient cash" }],
        },
      ],
    });
    expect(screen.getByText(/Rejected: BUY 999 AAPL/)).toBeInTheDocument();
    expect(screen.getByText(/Insufficient cash/)).toBeInTheDocument();
  });

  it("shows a loading indicator while busy", () => {
    setup({ busy: true });
    expect(screen.getByText(/FinAlly is thinking/)).toBeInTheDocument();
  });

  it("sends a message and clears the input", () => {
    const props = setup();
    const input = screen.getByLabelText("Message FinAlly") as HTMLInputElement;
    fireEvent.change(input, { target: { value: "How am I doing?" } });
    fireEvent.submit(input.closest("form")!);
    expect(props.onSend).toHaveBeenCalledWith("How am I doing?");
    expect(input.value).toBe("");
  });

  it("does not send while busy", () => {
    const props = setup({ busy: true });
    const input = screen.getByLabelText("Message FinAlly") as HTMLInputElement;
    fireEvent.change(input, { target: { value: "hi" } });
    fireEvent.submit(input.closest("form")!);
    expect(props.onSend).not.toHaveBeenCalled();
  });
});
