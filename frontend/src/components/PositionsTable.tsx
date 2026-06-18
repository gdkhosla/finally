"use client";

import { Panel } from "./Panel";
import { PriceCell } from "./PriceCell";
import { usd, qty, signedUsd, signedPct, tone } from "@/lib/format";
import type { LivePosition } from "@/lib/portfolio";

interface PositionsTableProps {
  positions: LivePosition[];
  onSelect: (ticker: string) => void;
}

export function PositionsTable({ positions, onSelect }: PositionsTableProps) {
  return (
    <Panel label="Positions" className="h-full" bodyClassName="overflow-auto">
      {positions.length === 0 ? (
        <div className="flex h-full items-center justify-center p-4 text-xs text-ink-faint">
          No open positions. Use the trade bar below to buy.
        </div>
      ) : (
        <table className="w-full text-sm">
          <thead>
            <tr className="eyebrow border-b border-border-soft text-left">
              <Th className="text-left">Ticker</Th>
              <Th>Qty</Th>
              <Th>Avg Cost</Th>
              <Th>Price</Th>
              <Th>P&L</Th>
              <Th>% Chg</Th>
            </tr>
          </thead>
          <tbody>
            {positions.map((p) => (
              <tr
                key={p.ticker}
                onClick={() => onSelect(p.ticker)}
                className="cursor-pointer border-b border-border-soft hover:bg-panel-raised"
              >
                <td className="px-3 py-1.5 font-mono font-semibold text-ink">{p.ticker}</td>
                <Td>{qty(p.quantity)}</Td>
                <Td>{usd(p.avg_cost)}</Td>
                <td className="px-3 py-1.5 text-right">
                  <PriceCell price={p.live_price} className="font-mono text-ink" />
                </td>
                <Td className={tone(p.live_pnl)}>{signedUsd(p.live_pnl)}</Td>
                <Td className={tone(p.live_pct_change)}>{signedPct(p.live_pct_change)}</Td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </Panel>
  );
}

function Th({ children, className }: { children: React.ReactNode; className?: string }) {
  return <th className={`px-3 py-1.5 text-right font-semibold ${className ?? ""}`}>{children}</th>;
}

function Td({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <td className={`tnum px-3 py-1.5 text-right font-mono text-ink ${className ?? ""}`}>
      {children}
    </td>
  );
}
