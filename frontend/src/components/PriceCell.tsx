"use client";

import { useEffect, useRef, useState } from "react";
import { money } from "@/lib/format";

interface PriceCellProps {
  price: number | null;
  className?: string;
}

/**
 * Renders a price and briefly flashes green (uptick) or red (downtick) when it
 * changes. The flash class is applied on change and cleared after the CSS
 * animation (~500ms) completes, so a fresh change always re-triggers it.
 */
export function PriceCell({ price, className }: PriceCellProps) {
  const prev = useRef<number | null>(null);
  const [flash, setFlash] = useState<"" | "flash-up" | "flash-down">("");

  useEffect(() => {
    if (price === null) return;
    const before = prev.current;
    if (before !== null && price !== before) {
      setFlash(price > before ? "flash-up" : "flash-down");
    }
    prev.current = price;
  }, [price]);

  return (
    <span
      data-testid="price-cell"
      className={`tnum inline-block rounded-sm px-1 ${flash} ${className ?? ""}`}
      onAnimationEnd={() => setFlash("")}
    >
      {money(price)}
    </span>
  );
}
