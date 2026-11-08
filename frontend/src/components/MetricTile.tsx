import { fmtMetric, metricTone, type Metric } from "@/lib/admin";

const TONE = {
  ok: "border-ok/40 bg-[#eef8f2]",
  mid: "border-warn/40 bg-[#fff6ec]",
  bad: "border-brand/30 bg-brand-soft",
  none: "border-line bg-white",
};

export function MetricTile({ m }: { m: Metric }) {
  const tone = metricTone(m);
  return (
    <div className={`rounded-xl border px-4 py-3 ${TONE[tone]}`} data-testid={`metric-${m.key}`} data-tone={tone}>
      <p className="text-xs font-medium text-ink-2">{m.label}</p>
      <p className="mt-1 text-2xl font-bold tabular-nums" data-testid="current">
        {fmtMetric(m.current, m.unit)}
      </p>
      <p className="mt-1 text-xs tabular-nums text-ink-2">
        baseline {fmtMetric(m.baseline, m.unit)} → target {fmtMetric(m.target, m.unit)}
      </p>
      {m.note && <p className="mt-1 text-[11px] leading-snug text-muted">{m.note}</p>}
    </div>
  );
}

export function MetricStrip({ metrics, period }: { metrics: Metric[]; period: string }) {
  const strip = metrics.filter((m) => m.strip);
  return (
    <section aria-label="Pilot metrics">
      <div className="grid grid-cols-2 gap-2 md:grid-cols-5" data-testid="metric-strip">
        {strip.map((m) => (
          <MetricTile key={m.key} m={m} />
        ))}
      </div>
      <p className="mt-1 text-[11px] text-muted">Current: app leads and orders, computed live. Baseline: {period}.</p>
    </section>
  );
}
