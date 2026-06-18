"use client";

import {
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Panel } from "./Panel";
import { money, usd } from "@/lib/format";
import type { Snapshot } from "@/lib/types";

interface PnlChartProps {
  snapshots: Snapshot[];
  /** Live total appended as the trailing point so the line tracks current value. */
  liveTotal: number;
}

export function PnlChart({ snapshots, liveTotal }: PnlChartProps) {
  const data = snapshots.map((s, i) => ({ i, value: s.total_value }));
  data.push({ i: data.length, value: liveTotal });

  const first = data[0]?.value ?? liveTotal;
  const up = liveTotal >= first;
  const color = up ? "var(--color-up)" : "var(--color-down)";

  return (
    <Panel
      label="Portfolio Value"
      className="h-full"
      bodyClassName="p-3"
      aside={<span className="tnum font-mono text-sm font-bold text-ink">{usd(liveTotal)}</span>}
    >
      {data.length < 2 ? (
        <div className="flex h-full items-center justify-center text-xs text-ink-faint">
          Tracking portfolio value...
        </div>
      ) : (
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
            <XAxis dataKey="i" hide />
            <YAxis
              domain={["auto", "auto"]}
              orientation="right"
              width={60}
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
              formatter={(v) => [usd(Number(v)), "Total"]}
            />
            <Line
              type="monotone"
              dataKey="value"
              stroke={color}
              strokeWidth={1.5}
              dot={false}
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      )}
    </Panel>
  );
}
