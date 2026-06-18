"use client";

import { ResponsiveContainer, Treemap } from "recharts";
import { Panel } from "./Panel";
import { signedPct } from "@/lib/format";
import type { LivePosition } from "@/lib/portfolio";

interface HeatmapProps {
  positions: LivePosition[];
  onSelect: (ticker: string) => void;
}

/** Map P&L% to a green/red tint; deeper color = stronger move (clamped at +-5%). */
function pnlColor(pct: number): string {
  const mag = Math.min(Math.abs(pct) / 5, 1);
  const alpha = 0.18 + mag * 0.55;
  const base = pct >= 0 ? "46,204,113" : "255,95,109";
  return `rgba(${base},${alpha.toFixed(2)})`;
}

interface TreemapNode {
  name: string;
  size: number;
  pct: number;
  // Recharts injects layout fields and may add others; allow them.
  [key: string]: unknown;
}

// Recharts calls `content` with computed layout props merged onto each node.
interface CellProps {
  x?: number;
  y?: number;
  width?: number;
  height?: number;
  depth?: number;
  name?: string;
  pct?: number;
  onSelect: (t: string) => void;
}

function Cell(props: CellProps) {
  const { x = 0, y = 0, width = 0, height = 0, depth = 1, name = "", pct = 0, onSelect } = props;
  // Recharts wraps a flat data array in a root node (depth 0) that spans the
  // whole area; only draw the leaf position cells.
  if (depth < 1 || width <= 0 || height <= 0) return null;
  const showLabel = width > 44 && height > 28;
  return (
    <g
      onClick={() => onSelect(name)}
      style={{ cursor: "pointer" }}
    >
      <rect
        x={x}
        y={y}
        width={width}
        height={height}
        fill={pnlColor(pct)}
        stroke="var(--color-bg)"
        strokeWidth={2}
      />
      {showLabel && (
        <>
          <text
            x={x + 6}
            y={y + 16}
            fill="var(--color-ink)"
            fontSize={12}
            fontWeight={700}
            fontFamily="var(--font-mono)"
          >
            {name}
          </text>
          <text
            x={x + 6}
            y={y + 30}
            fill="var(--color-ink)"
            fontSize={10}
            fontFamily="var(--font-mono)"
            opacity={0.85}
          >
            {signedPct(pct)}
          </text>
        </>
      )}
    </g>
  );
}

export function Heatmap({ positions, onSelect }: HeatmapProps) {
  const data: TreemapNode[] = positions.map((p) => ({
    name: p.ticker,
    size: Math.max(p.quantity * p.live_price, 0.01),
    pct: p.live_pct_change,
  }));

  return (
    <Panel label="Positions Heatmap" className="h-full" bodyClassName="p-1">
      {data.length === 0 ? (
        <div className="flex h-full items-center justify-center text-xs text-ink-faint">
          No open positions.
        </div>
      ) : (
        <ResponsiveContainer width="100%" height="100%">
          <Treemap
            data={data}
            dataKey="size"
            isAnimationActive={false}
            content={<Cell onSelect={onSelect} />}
          />
        </ResponsiveContainer>
      )}
    </Panel>
  );
}
