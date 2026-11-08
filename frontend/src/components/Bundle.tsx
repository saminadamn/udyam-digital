"use client";

import type { BundleItem } from "@/lib/api";
import { rupees } from "@/lib/format";

const ICONS: Record<string, string> = {
  P01: "📶", P02: "📶", P03: "📶", P04: "📡", P05: "🔗", P06: "🔗", P07: "📱", P08: "📱", P09: "🔁", P10: "🕸️", P11: "📍",
  P12: "☎️", P13: "📞", P14: "✉️", P15: "💬", P16: "📧", P17: "💾", P18: "🌐", P19: "🧾", P20: "🛡️", P21: "🧱", P22: "📶",
  P23: "📹", P24: "⚙️", P25: "🚚",
};

export function BundleCard({ items, qtyLabel }: { items: BundleItem[]; qtyLabel: (n: number) => string }) {
  return (
    <ul className="divide-y divide-line">
      {items.map((i) => (
        <li key={i.product_id} className="flex gap-3 py-3">
          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-brand-soft text-lg" aria-hidden>
            {ICONS[i.product_id] ?? "•"}
          </span>
          <div className="min-w-0 flex-1">
            <div className="flex items-baseline justify-between gap-2">
              <p className="font-semibold leading-snug">{i.name}</p>
              {i.qty > 1 && <span className="shrink-0 text-sm text-ink-2">{qtyLabel(i.qty)}</span>}
            </div>
            <p className="text-sm text-ink-2">{i.why}</p>
            {i.what_it_does && i.what_it_does !== i.why && <p className="text-xs text-muted">{i.what_it_does}</p>}
          </div>
        </li>
      ))}
    </ul>
  );
}

export function AddonList({ items, lang, qtyLabel, perMonth }: { items: BundleItem[]; lang: string; qtyLabel: (n: number) => string; perMonth: string }) {
  return (
    <ul className="divide-y divide-line">
      {items.map((i) => (
        <li key={i.product_id} className="flex items-center gap-3 py-3">
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-canvas" aria-hidden>
            {ICONS[i.product_id] ?? "+"}
          </span>
          <div className="min-w-0 flex-1">
            <p className="text-sm font-medium">
              {i.name} {i.qty > 1 && <span className="text-ink-2">{qtyLabel(i.qty)}</span>}
            </p>
            <p className="text-xs text-ink-2">{i.why}</p>
          </div>
          {typeof i.monthly_inr === "number" && (
            <span className="shrink-0 text-sm text-ink-2">
              +{rupees(i.monthly_inr, lang)}
              <span className="text-xs"> {perMonth}</span>
            </span>
          )}
        </li>
      ))}
    </ul>
  );
}

export function PriceBar({
  total,
  setup,
  lang,
  labels,
}: {
  total: number;
  setup: number;
  lang: string;
  labels: { perMonth: string; setup: string; contract: string; noHidden: string };
}) {
  return (
    <div className="flex items-end justify-between gap-3">
      <div>
        <p className="text-3xl font-bold tracking-tight">
          {rupees(total, lang)}
          <span className="ml-1 text-base font-medium text-ink-2">{labels.perMonth}</span>
        </p>
        <p className="text-sm text-ink-2">
          {labels.contract} · {labels.noHidden}
        </p>
      </div>
      <div className="text-right text-sm text-ink-2">
        <p>{labels.setup}</p>
        <p className="font-semibold text-ink">{rupees(setup, lang)}</p>
      </div>
    </div>
  );
}
