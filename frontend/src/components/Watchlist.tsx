"use client";

import { useState } from "react";
import { Panel } from "./Panel";
import { PriceCell } from "./PriceCell";
import { Sparkline } from "./Sparkline";
import { signedPct, tone } from "@/lib/format";
import type { PriceMap, WatchlistEntry } from "@/lib/types";

interface WatchlistProps {
  entries: WatchlistEntry[];
  prices: PriceMap;
  baselines: Record<string, number>;
  sparklines: Record<string, number[]>;
  selected: string | null;
  heldTickers: Set<string>;
  onSelect: (ticker: string) => void;
  onAdd: (ticker: string) => Promise<void>;
  onRemove: (ticker: string) => Promise<void>;
}

/** Percent change of the live price vs the first price seen this session. */
function changeSinceLoad(live: number | null, baseline: number | undefined): number | null {
  if (live === null || baseline === undefined || baseline === 0) return null;
  return ((live - baseline) / baseline) * 100;
}

export function Watchlist({
  entries,
  prices,
  baselines,
  sparklines,
  selected,
  heldTickers,
  onSelect,
  onAdd,
  onRemove,
}: WatchlistProps) {
  const [draft, setDraft] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const ticker = draft.trim().toUpperCase();
    if (!ticker) return;
    setError(null);
    try {
      await onAdd(ticker);
      setDraft("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not add ticker");
    }
  }

  return (
    <Panel label="Watchlist" className="h-full">
      <div className="flex h-full flex-col">
        <form onSubmit={submit} className="flex gap-1 border-b border-border-soft p-2">
          <input
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder="Add ticker"
            aria-label="Add ticker"
            className="tnum w-full bg-panel-raised px-2 py-1 font-mono text-xs uppercase text-ink outline-none placeholder:text-ink-faint focus:ring-1 focus:ring-blue"
          />
          <button
            type="submit"
            className="border border-border px-2 py-1 text-xs text-ink-dim hover:border-blue hover:text-ink"
          >
            Add
          </button>
        </form>
        {error && <p className="px-2 py-1 text-xs text-down">{error}</p>}

        <div className="min-h-0 flex-1 overflow-y-auto">
          {entries.map((entry) => {
            const live = prices[entry.ticker]?.price ?? entry.price;
            const pct = changeSinceLoad(live, baselines[entry.ticker]);
            const isSelected = selected === entry.ticker;
            const held = heldTickers.has(entry.ticker);
            return (
              <div
                key={entry.ticker}
                role="button"
                tabIndex={0}
                onClick={() => onSelect(entry.ticker)}
                onKeyDown={(e) => e.key === "Enter" && onSelect(entry.ticker)}
                className={`group grid cursor-pointer grid-cols-[1fr_auto_auto] items-center gap-2 border-b border-border-soft px-3 py-1.5 text-sm hover:bg-panel-raised ${
                  isSelected ? "bg-panel-raised" : ""
                }`}
              >
                <div className="flex items-center gap-2 overflow-hidden">
                  <span className={`w-1 self-stretch ${isSelected ? "bg-accent" : "bg-transparent"}`} />
                  <span className="font-mono font-semibold text-ink">{entry.ticker}</span>
                  {held && (
                    <span className="rounded-sm bg-blue/15 px-1 text-[9px] font-semibold uppercase tracking-wide text-blue">
                      Held
                    </span>
                  )}
                </div>

                <Sparkline data={sparklines[entry.ticker] ?? []} baseline={baselines[entry.ticker]} />

                <div className="flex w-24 flex-col items-end leading-tight">
                  <PriceCell price={live} className="font-mono text-ink" />
                  <span className={`tnum font-mono text-xs ${tone(pct)}`}>{signedPct(pct)}</span>
                </div>

                {!held && (
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      onRemove(entry.ticker).catch(() => {});
                    }}
                    aria-label={`Remove ${entry.ticker}`}
                    className="col-start-3 hidden text-[10px] text-ink-faint hover:text-down group-hover:block"
                  >
                    remove
                  </button>
                )}
              </div>
            );
          })}
          {entries.length === 0 && (
            <p className="p-4 text-center text-xs text-ink-faint">
              Watchlist empty. Add a ticker to start streaming.
            </p>
          )}
        </div>
      </div>
    </Panel>
  );
}
