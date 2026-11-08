"use client";

import type { Step } from "@/lib/api";

function when(iso: string, lang: string) {
  return new Date(iso).toLocaleString(lang === "en" ? "en-IN" : `${lang}-IN`, { day: "numeric", month: "short", hour: "numeric", minute: "2-digit" });
}

export function StepTimeline({ steps, lang }: { steps: Step[]; lang: string }) {
  return (
    <ol className="relative" data-testid="timeline">
      {steps.map((s, i) => {
        const last = i === steps.length - 1;
        const dot =
          s.status === "done"
            ? "bg-ok text-white"
            : s.status === "current"
              ? s.late
                ? "bg-warn text-white ring-4 ring-warn/20"
                : "bg-brand text-white ring-4 ring-brand/15"
              : s.late
                ? "border-2 border-warn bg-white text-warn"
                : "border-2 border-line bg-white text-muted";
        return (
          <li key={s.key} className="relative flex gap-3 pb-6 last:pb-0" data-testid={`step-${s.key}`} data-status={s.status} aria-current={s.status === "current" ? "step" : undefined}>
            {!last && <span aria-hidden className={`absolute left-[13px] top-7 h-[calc(100%-28px)] w-0.5 ${s.status === "done" ? "bg-ok" : "bg-line"}`} />}
            <span aria-hidden className={`relative z-10 flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-sm font-bold ${dot}`}>
              {s.status === "done" ? "✓" : i + 1}
            </span>
            <div className="min-w-0 pt-0.5">
              <p className={`font-semibold leading-tight ${s.status === "upcoming" ? "text-ink-2" : ""}`}>{s.label}</p>
              {s.detail && <p className={`mt-0.5 text-sm ${s.late ? "font-medium text-[#9a5b00]" : "text-ink-2"}`}>{s.detail}</p>}
              {s.status === "done" && s.at && s.key !== "KYC_VERIFIED" && s.key !== "INSTALLED" && s.key !== "LIVE" && (
                <p className="text-xs text-muted">{when(s.at, lang)}</p>
              )}
            </div>
          </li>
        );
      })}
    </ol>
  );
}
