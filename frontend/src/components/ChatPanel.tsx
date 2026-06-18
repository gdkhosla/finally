"use client";

import { useEffect, useRef, useState } from "react";
import { qty, usd } from "@/lib/format";
import type { ChatMessage, ChatTradeAction, ChatWatchlistAction } from "@/lib/types";

interface ChatPanelProps {
  messages: ChatMessage[];
  busy: boolean;
  open: boolean;
  onToggle: () => void;
  onSend: (message: string) => void;
}

export function ChatPanel({ messages, busy, open, onToggle, onSend }: ChatPanelProps) {
  const [draft, setDraft] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages, busy]);

  function submit(e: React.FormEvent) {
    e.preventDefault();
    const text = draft.trim();
    if (!text || busy) return;
    onSend(text);
    setDraft("");
  }

  if (!open) {
    return (
      <button
        onClick={onToggle}
        className="flex w-10 flex-col items-center justify-center gap-2 border-l border-border bg-panel text-ink-dim hover:text-accent"
        aria-label="Open AI assistant"
      >
        <span className="rotate-180 [writing-mode:vertical-rl] eyebrow">FinAlly AI</span>
      </button>
    );
  }

  return (
    <aside className="flex w-80 flex-col border-l border-border bg-panel lg:w-96">
      <header className="flex items-center justify-between border-b border-border px-3 py-2.5">
        <div className="flex items-center gap-2">
          <span className="h-2 w-2 rounded-full bg-accent" />
          <span className="font-mono text-sm font-semibold text-ink">FinAlly AI</span>
        </div>
        <button
          onClick={onToggle}
          className="text-ink-faint hover:text-ink"
          aria-label="Collapse assistant"
        >
          &times;
        </button>
      </header>

      <div ref={scrollRef} className="min-h-0 flex-1 space-y-3 overflow-y-auto p-3">
        {messages.length === 0 && (
          <p className="text-xs leading-relaxed text-ink-faint">
            Ask about your portfolio, request analysis, or have FinAlly execute trades and manage
            your watchlist. Try: &quot;Buy 10 shares of NVDA&quot; or &quot;How concentrated am
            I?&quot;
          </p>
        )}
        {messages.map((m, i) => (
          <MessageBubble key={i} message={m} />
        ))}
        {busy && (
          <div className="flex items-center gap-1.5 text-xs text-ink-faint" role="status">
            <Dot /> <Dot delay={0.15} /> <Dot delay={0.3} />
            <span className="ml-1">FinAlly is thinking</span>
          </div>
        )}
      </div>

      <form onSubmit={submit} className="border-t border-border p-2">
        <div className="flex gap-1">
          <input
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder="Message FinAlly"
            aria-label="Message FinAlly"
            disabled={busy}
            className="w-full bg-panel-raised px-2 py-2 text-sm text-ink outline-none placeholder:text-ink-faint focus:ring-1 focus:ring-purple disabled:opacity-60"
          />
          <button
            type="submit"
            disabled={busy || !draft.trim()}
            className="bg-purple px-3 py-2 text-sm font-semibold text-white hover:opacity-90 disabled:opacity-50"
          >
            Send
          </button>
        </div>
      </form>
    </aside>
  );
}

function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user";
  return (
    <div className={`flex flex-col ${isUser ? "items-end" : "items-start"}`}>
      <div
        className={`max-w-[88%] whitespace-pre-wrap rounded-md px-2.5 py-1.5 text-sm leading-relaxed ${
          isUser ? "bg-blue/15 text-ink" : "bg-panel-raised text-ink"
        }`}
      >
        {message.content}
      </div>
      {(message.trades?.length || message.watchlist_changes?.length) && (
        <div className="mt-1 flex max-w-[88%] flex-col gap-1">
          {message.trades?.map((t, i) => (
            <TradeConfirm key={`t${i}`} trade={t} />
          ))}
          {message.watchlist_changes?.map((w, i) => (
            <WatchlistConfirm key={`w${i}`} change={w} />
          ))}
        </div>
      )}
    </div>
  );
}

function TradeConfirm({ trade }: { trade: ChatTradeAction }) {
  const ok = trade.ok !== false && !trade.error;
  return (
    <span
      className={`tnum rounded-sm border px-2 py-1 font-mono text-xs ${
        ok ? "border-up/40 text-up" : "border-down/40 text-down"
      }`}
    >
      {ok ? "Filled" : "Rejected"}: {trade.side.toUpperCase()} {qty(trade.quantity)} {trade.ticker}
      {ok && trade.fill_price !== undefined && ` @ ${usd(trade.fill_price)}`}
      {!ok && trade.error && ` — ${trade.error}`}
    </span>
  );
}

function WatchlistConfirm({ change }: { change: ChatWatchlistAction }) {
  const ok = change.ok !== false && !change.error;
  return (
    <span
      className={`rounded-sm border px-2 py-1 font-mono text-xs ${
        ok ? "border-blue/40 text-blue" : "border-down/40 text-down"
      }`}
    >
      Watchlist {change.action} {change.ticker}
      {!ok && change.error && ` — ${change.error}`}
    </span>
  );
}

function Dot({ delay = 0 }: { delay?: number }) {
  return (
    <span
      className="pulse inline-block h-1.5 w-1.5 rounded-full bg-accent"
      style={{ animationDelay: `${delay}s` }}
    />
  );
}
