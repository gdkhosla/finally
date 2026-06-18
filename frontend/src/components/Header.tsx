import { usd, signedUsd, signedPct, tone } from "@/lib/format";
import type { ConnectionStatus } from "@/lib/types";

const STATUS_META: Record<ConnectionStatus, { color: string; label: string; pulse: boolean }> = {
  connected: { color: "var(--color-up)", label: "Live", pulse: false },
  reconnecting: { color: "var(--color-accent)", label: "Reconnecting", pulse: true },
  disconnected: { color: "var(--color-down)", label: "Offline", pulse: false },
};

interface HeaderProps {
  totalValue: number;
  cash: number;
  unrealizedPnl: number;
  status: ConnectionStatus;
}

export function Header({ totalValue, cash, unrealizedPnl, status }: HeaderProps) {
  const meta = STATUS_META[status];
  const pnlPct = totalValue - unrealizedPnl > 0
    ? (unrealizedPnl / (totalValue - unrealizedPnl)) * 100
    : 0;

  return (
    <header className="flex items-center justify-between border-b border-border bg-panel px-4 py-2.5">
      <div className="flex items-baseline gap-2.5">
        <span className="font-mono text-lg font-bold tracking-tight text-accent">FinAlly</span>
        <span className="eyebrow hidden sm:inline">AI Trading Workstation</span>
      </div>

      <div className="flex items-center gap-5 sm:gap-8">
        <Metric label="Cash" value={usd(cash)} />
        <Metric
          label="Unrealized P&L"
          value={signedUsd(unrealizedPnl)}
          sub={signedPct(pnlPct)}
          toneClass={tone(unrealizedPnl)}
        />
        <Metric label="Total Value" value={usd(totalValue)} emphasize />

        <div className="flex items-center gap-1.5" title={meta.label}>
          <span
            className={`inline-block h-2 w-2 rounded-full ${meta.pulse ? "pulse" : ""}`}
            style={{ backgroundColor: meta.color }}
            data-testid="connection-dot"
            data-status={status}
          />
          <span className="eyebrow hidden md:inline">{meta.label}</span>
        </div>
      </div>
    </header>
  );
}

function Metric({
  label,
  value,
  sub,
  toneClass,
  emphasize,
}: {
  label: string;
  value: string;
  sub?: string;
  toneClass?: string;
  emphasize?: boolean;
}) {
  return (
    <div className="flex flex-col items-end leading-tight">
      <span className="eyebrow">{label}</span>
      <span
        className={`tnum font-mono ${emphasize ? "text-base font-bold text-ink" : "text-sm"} ${
          toneClass ?? "text-ink"
        }`}
      >
        {value}
        {sub && <span className="ml-1.5 text-xs opacity-80">{sub}</span>}
      </span>
    </div>
  );
}
