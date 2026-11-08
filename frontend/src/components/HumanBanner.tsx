"use client";

import type { Human } from "@/lib/api";

export function HumanBanner({ human, title }: { human: Human; title: string }) {
  const initial = human.agent_name?.[0] ?? "A";
  return (
    <div className="card flex items-start gap-3 border-brand/30 bg-white p-4" role="status" data-testid="human-banner">
      <span aria-hidden className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-brand text-lg font-bold text-white">
        {initial}
      </span>
      <div className="min-w-0">
        <p className="text-sm text-ink-2">{title}</p>
        <p className="font-semibold leading-snug" data-testid="human-message">
          {human.message}
        </p>
      </div>
    </div>
  );
}
