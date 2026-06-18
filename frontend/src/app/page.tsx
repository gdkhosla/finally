"use client";

import { useCallback, useMemo, useState } from "react";
import { Header } from "@/components/Header";
import { Watchlist } from "@/components/Watchlist";
import { MainChart } from "@/components/MainChart";
import { Heatmap } from "@/components/Heatmap";
import { PnlChart } from "@/components/PnlChart";
import { PositionsTable } from "@/components/PositionsTable";
import { TradeBar } from "@/components/TradeBar";
import { ChatPanel } from "@/components/ChatPanel";
import { usePrices } from "@/lib/usePrices";
import { useAppData } from "@/lib/useAppData";
import { deriveLivePortfolio } from "@/lib/portfolio";
import { executeTrade, addWatchlist, removeWatchlist, sendChat } from "@/lib/api";
import type { ChatMessage } from "@/lib/types";

export default function Home() {
  const { prices, baselines, sparklines, status } = usePrices();
  const { portfolio, watchlist, history, refresh } = useAppData();

  const [selected, setSelected] = useState<string | null>(null);
  const [chatOpen, setChatOpen] = useState(true);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [chatBusy, setChatBusy] = useState(false);

  const live = useMemo(() => deriveLivePortfolio(portfolio, prices), [portfolio, prices]);
  const heldTickers = useMemo(
    () => new Set(portfolio.positions.map((p) => p.ticker)),
    [portfolio.positions],
  );

  // Default the selected ticker to the first watchlist entry once loaded.
  const effectiveSelected = selected ?? watchlist[0]?.ticker ?? null;

  const handleTrade = useCallback(
    async (ticker: string, side: "buy" | "sell", quantity: number) => {
      const result = await executeTrade(ticker, side, quantity);
      if (!result.ok) throw new Error(result.error ?? "Trade rejected");
      await refresh();
    },
    [refresh],
  );

  const handleAdd = useCallback(
    async (ticker: string) => {
      await addWatchlist(ticker);
      await refresh();
    },
    [refresh],
  );

  const handleRemove = useCallback(
    async (ticker: string) => {
      await removeWatchlist(ticker);
      await refresh();
    },
    [refresh],
  );

  const handleSend = useCallback(
    async (text: string) => {
      setMessages((m) => [...m, { role: "user", content: text }]);
      setChatBusy(true);
      try {
        const res = await sendChat(text);
        setMessages((m) => [
          ...m,
          {
            role: "assistant",
            content: res.message,
            trades: res.trades,
            watchlist_changes: res.watchlist_changes,
          },
        ]);
        // The assistant may have traded or edited the watchlist; resync.
        await refresh();
      } catch (err) {
        setMessages((m) => [
          ...m,
          {
            role: "assistant",
            content: err instanceof Error ? err.message : "Something went wrong.",
          },
        ]);
      } finally {
        setChatBusy(false);
      }
    },
    [refresh],
  );

  const selectedSeries = effectiveSelected ? sparklines[effectiveSelected] ?? [] : [];
  const selectedLive = effectiveSelected ? prices[effectiveSelected]?.price ?? null : null;

  return (
    <div className="flex h-screen flex-col bg-bg text-ink">
      <Header
        totalValue={live.total_value}
        cash={live.cash_balance}
        unrealizedPnl={live.unrealized_pnl}
        status={status}
      />

      <div className="flex min-h-0 flex-1">
        <main className="flex min-w-0 flex-1 flex-col">
          <div className="grid min-h-0 flex-1 grid-cols-12 gap-px overflow-hidden bg-border-soft">
            {/* Left: watchlist */}
            <div className="col-span-12 min-h-0 md:col-span-3">
              <Watchlist
                entries={watchlist}
                prices={prices}
                baselines={baselines}
                sparklines={sparklines}
                selected={effectiveSelected}
                heldTickers={heldTickers}
                onSelect={setSelected}
                onAdd={handleAdd}
                onRemove={handleRemove}
              />
            </div>

            {/* Center: chart + positions */}
            <div className="col-span-12 grid min-h-0 grid-rows-[3fr_2fr] gap-px md:col-span-6">
              <MainChart
                ticker={effectiveSelected}
                series={selectedSeries}
                baseline={effectiveSelected ? baselines[effectiveSelected] : undefined}
                livePrice={selectedLive}
              />
              <PositionsTable positions={live.positions} onSelect={setSelected} />
            </div>

            {/* Right: heatmap + P&L chart */}
            <div className="col-span-12 grid min-h-0 grid-rows-2 gap-px md:col-span-3">
              <Heatmap positions={live.positions} onSelect={setSelected} />
              <PnlChart snapshots={history} liveTotal={live.total_value} />
            </div>
          </div>

          <TradeBar selected={effectiveSelected} onTrade={handleTrade} />
        </main>

        <ChatPanel
          messages={messages}
          busy={chatBusy}
          open={chatOpen}
          onToggle={() => setChatOpen((o) => !o)}
          onSend={handleSend}
        />
      </div>
    </div>
  );
}
