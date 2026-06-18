"use client";

import {
  Area,
  AreaChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Panel } from "./Panel";
import { PriceCell } from "./PriceCell";
import { money, signedPct, tone } from "@/lib/format";

interface MainChartProps {
  ticker: string | null;
  series: number[];
  baseline?: number;
  livePrice: number | null;
}

export function MainChart({ ticker, series, baseline, livePrice }: MainChartProps) {
  const pct =
    livePrice !== null && baseline !== undefined && baseline > 0
      ? ((livePrice - baseline) / baseline) * 100
      : null;
  const up = pct === null || pct >= 0;
  const color = up ? "var(--color-up)" : "var(--color-down)";

  const data = series.map((price, i) => ({ i, price }));

  return (
    <Panel
      label={ticker ? `Chart — ${ticker}` : "Chart"}
      className="h-full"
      bodyClassName="p-3"
      aside={
        ticker && (
          <span className="flex items-baseline gap-2">
            <PriceCell price={livePrice} className="font-mono text-sm font-bold text-ink" />
            <span className={`tnum font-mono text-xs ${tone(pct)}`}>{signedPct(pct)}</span>
          </span>
        )
      }
    >
      {!ticker ? (
        <Empty>Select a ticker from the watchlist.</Empty>
      ) : data.length < 2 ? (
        <Empty>Accumulating price data for {ticker}...</Empty>
      ) : (
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
            <defs>
              <linearGradient id="chartFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={color} stopOpacity={0.35} />
                <stop offset="100%" stopColor={color} stopOpacity={0} />
              </linearGradient>
            </defs>
            <XAxis dataKey="i" hide />
            <YAxis
              domain={["auto", "auto"]}
              orientation="right"
              width={56}
              tick={{ fill: "var(--color-ink-faint)", fontSize: 10 }}
              tickFormatter={(v) => money(v)}
              axisLine={false}
              tickLine={false}
            />
            <Tooltip
              contentStyle={{
                background: "var(--color-panel-raised)",
                border: "1px solid var(--color-border)",
                fontSize: 12,
              }}
              labelFormatter={() => ""}
              formatter={(v) => [money(Number(v)), ticker]}
            />
            <Area
              type="monotone"
              dataKey="price"
              stroke={color}
              strokeWidth={1.5}
              fill="url(#chartFill)"
              isAnimationActive={false}
              dot={false}
            />
          </AreaChart>
        </ResponsiveContainer>
      )}
    </Panel>
  );
}

function Empty({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex h-full items-center justify-center text-xs text-ink-faint">{children}</div>
  );
}
