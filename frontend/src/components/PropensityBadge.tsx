import type { Propensity } from "@/lib/admin";

const TONE = { High: "bg-brand text-white", Medium: "bg-[#fff1dc] text-[#8a4f00]", Low: "bg-canvas text-ink-2 border border-line" };

export function PropensityBadge({ p, showReasons = false }: { p: Propensity; showReasons?: boolean }) {
  if (!p) return <span className="text-xs text-muted">not scored</span>;
  const title = p.reasons.join("\n");
  return (
    <span className="inline-flex flex-col gap-1" title={title}>
      <span className="inline-flex items-center gap-2">
        <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${TONE[p.bucket]}`} data-testid="bucket">
          {p.bucket}
        </span>
        {p.bucket_conversion_pct !== null && <span className="text-xs text-ink-2">converts ~{p.bucket_conversion_pct}%</span>}
      </span>
      {showReasons && (
        <ul className="text-xs text-ink-2">
          {p.reasons.map((r) => (
            <li key={r} className={r.startsWith("+") ? "text-ok" : "text-brand-dark"}>
              {r}
            </li>
          ))}
        </ul>
      )}
    </span>
  );
}
