"use client";

import { useState } from "react";

export function ChatBubble({
  role,
  children,
  onPlay,
  playLabel,
}: {
  role: "assistant" | "user";
  children: React.ReactNode;
  onPlay?: () => void;
  playLabel?: string;
}) {
  const mine = role === "user";
  return (
    <div className={`flex items-end gap-1 ${mine ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[85%] whitespace-pre-wrap rounded-2xl px-4 py-3 text-[15px] leading-relaxed ${
          mine ? "rounded-br-md bg-brand text-white" : "rounded-bl-md border border-line bg-white text-ink"
        }`}
      >
        {children}
      </div>
      {onPlay && (
        <button
          type="button"
          onClick={onPlay}
          aria-label={playLabel}
          title={playLabel}
          data-testid="play-reply"
          className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full text-ink-2 hover:text-brand"
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
            <path d="M11 5 6 9H3v6h3l5 4V5z" strokeLinejoin="round" />
            <path d="M15.5 8.5a5 5 0 0 1 0 7M18.5 5.5a9 9 0 0 1 0 13" strokeLinecap="round" />
          </svg>
        </button>
      )}
    </div>
  );
}

export function TypingBubble({ label }: { label: string }) {
  return (
    <div className="flex justify-start" aria-live="polite">
      <div className="rounded-2xl rounded-bl-md border border-line bg-white px-4 py-3 text-sm text-muted">{label}</div>
    </div>
  );
}

export function QuickReplies({
  options,
  multi,
  doneLabel,
  disabled,
  onPick,
}: {
  options: string[];
  multi?: boolean;
  doneLabel?: string;
  disabled?: boolean;
  onPick: (value: string) => void;
}) {
  const [picked, setPicked] = useState<string[]>([]);
  if (!options.length) return null;
  const toggle = (o: string) => setPicked((p) => (p.includes(o) ? p.filter((x) => x !== o) : [...p, o]));
  return (
    <div className="flex flex-wrap gap-2" role="group">
      {options.map((o) => {
        const on = picked.includes(o);
        return (
          <button
            key={o}
            type="button"
            disabled={disabled}
            aria-pressed={multi ? on : undefined}
            onClick={() => (multi ? toggle(o) : onPick(o))}
            className={`min-h-[44px] rounded-full border px-4 text-sm font-medium transition-colors disabled:opacity-50 ${
              on ? "border-brand bg-brand text-white" : "border-line bg-white text-ink hover:border-brand"
            }`}
          >
            {multi && on ? "✓ " : ""}
            {o}
          </button>
        );
      })}
      {multi && (
        <button
          type="button"
          disabled={disabled}
          onClick={() => onPick(picked.length ? picked.join(", ") : doneLabel || "Done")}
          className="min-h-[44px] rounded-full bg-ink px-5 text-sm font-semibold text-white disabled:opacity-50"
        >
          {doneLabel || "Done"}
          {picked.length ? ` (${picked.length})` : ""}
        </button>
      )}
    </div>
  );
}

export function HumanBanner({ message }: { message: string }) {
  return (
    <div className="flex items-start gap-3 rounded-xl border border-brand/30 bg-brand-soft px-4 py-3 text-sm text-ink" role="status">
      <span aria-hidden className="mt-0.5 text-lg">
        ☎
      </span>
      <span>{message}</span>
    </div>
  );
}
