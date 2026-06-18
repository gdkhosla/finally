import type { ReactNode } from "react";

interface PanelProps {
  label: string;
  children: ReactNode;
  /** Optional right-aligned content in the header (e.g. a live figure). */
  aside?: ReactNode;
  className?: string;
  bodyClassName?: string;
}

/** A hairline-ruled terminal panel with an eyebrow header. */
export function Panel({ label, children, aside, className, bodyClassName }: PanelProps) {
  return (
    <section
      className={`flex min-h-0 flex-col border border-border-soft bg-panel ${className ?? ""}`}
    >
      <header className="flex items-center justify-between border-b border-border-soft px-3 py-2">
        <span className="eyebrow">{label}</span>
        {aside}
      </header>
      <div className={`min-h-0 flex-1 ${bodyClassName ?? ""}`}>{children}</div>
    </section>
  );
}
