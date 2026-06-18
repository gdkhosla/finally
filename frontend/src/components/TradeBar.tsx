"use client";

import { useState } from "react";

interface TradeBarProps {
  selected: string | null;
  onTrade: (ticker: string, side: "buy" | "sell", quantity: number) => Promise<void>;
}

type Notice = { kind: "ok" | "err"; text: string } | null;

export function TradeBar({ selected, onTrade }: TradeBarProps) {
  const [ticker, setTicker] = useState("");
  const [quantity, setQuantity] = useState("");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<Notice>(null);

  // Follow the selected watchlist row, but keep the field editable. Adjusting
  // state during render on a changed input is React's recommended pattern over
  // a syncing effect (https://react.dev/learn/you-might-not-need-an-effect).
  const [lastSelected, setLastSelected] = useState<string | null>(null);
  if (selected && selected !== lastSelected) {
    setLastSelected(selected);
    setTicker(selected);
  }

  async function trade(side: "buy" | "sell") {
    const sym = ticker.trim().toUpperCase();
    const q = Number(quantity);
    if (!sym || !Number.isFinite(q) || q <= 0) {
      setNotice({ kind: "err", text: "Enter a ticker and a positive quantity." });
      return;
    }
    setBusy(true);
    setNotice(null);
    try {
      await onTrade(sym, side, q);
      setNotice({ kind: "ok", text: `${side === "buy" ? "Bought" : "Sold"} ${q} ${sym}.` });
      setQuantity("");
    } catch (err) {
      setNotice({ kind: "err", text: err instanceof Error ? err.message : "Trade failed." });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-wrap items-center gap-2 border-t border-border bg-panel px-3 py-2">
      <span className="eyebrow">Trade</span>
      <input
        value={ticker}
        onChange={(e) => setTicker(e.target.value)}
        placeholder="Ticker"
        aria-label="Trade ticker"
        className="tnum w-24 bg-panel-raised px-2 py-1.5 font-mono text-sm uppercase text-ink outline-none placeholder:text-ink-faint focus:ring-1 focus:ring-blue"
      />
      <input
        value={quantity}
        onChange={(e) => setQuantity(e.target.value)}
        placeholder="Qty"
        inputMode="decimal"
        aria-label="Trade quantity"
        className="tnum w-24 bg-panel-raised px-2 py-1.5 font-mono text-sm text-ink outline-none placeholder:text-ink-faint focus:ring-1 focus:ring-blue"
      />
      <button
        onClick={() => trade("buy")}
        disabled={busy}
        className="bg-blue px-4 py-1.5 text-sm font-semibold text-white hover:opacity-90 disabled:opacity-50"
      >
        Buy
      </button>
      <button
        onClick={() => trade("sell")}
        disabled={busy}
        className="border border-border px-4 py-1.5 text-sm font-semibold text-ink hover:border-down hover:text-down disabled:opacity-50"
      >
        Sell
      </button>

      {notice && (
        <span
          role="status"
          className={`text-xs ${notice.kind === "ok" ? "text-up" : "text-down"}`}
        >
          {notice.text}
        </span>
      )}
      <span className="ml-auto eyebrow hidden md:inline">Market order, instant fill</span>
    </div>
  );
}
