interface SparklineProps {
  data: number[];
  width?: number;
  height?: number;
  /** Tone: positive (up) or negative (down) vs the first point. */
  baseline?: number;
}

/**
 * Minimal inline SVG sparkline. Colors against the session baseline so the
 * line reads green when up since load, red when down.
 */
export function Sparkline({ data, width = 72, height = 22, baseline }: SparklineProps) {
  if (data.length < 2) {
    return <svg width={width} height={height} aria-hidden="true" />;
  }

  const min = Math.min(...data);
  const max = Math.max(...data);
  const span = max - min || 1;
  const stepX = width / (data.length - 1);

  const points = data
    .map((v, i) => {
      const x = i * stepX;
      const y = height - ((v - min) / span) * height;
      return `${x.toFixed(2)},${y.toFixed(2)}`;
    })
    .join(" ");

  const ref = baseline ?? data[0];
  const last = data[data.length - 1];
  const color = last >= ref ? "var(--color-up)" : "var(--color-down)";

  return (
    <svg width={width} height={height} aria-hidden="true" className="overflow-visible">
      <polyline
        points={points}
        fill="none"
        stroke={color}
        strokeWidth={1.25}
        strokeLinejoin="round"
        strokeLinecap="round"
      />
    </svg>
  );
}
