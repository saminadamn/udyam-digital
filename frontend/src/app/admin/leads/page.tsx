"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { CallPanel } from "@/components/CallPanel";
import { DataTable, type Column } from "@/components/DataTable";
import { MetricStrip } from "@/components/MetricTile";
import { PropensityBadge } from "@/components/PropensityBadge";
import { api, ApiError } from "@/lib/api";
import { ADVISOR_OUTCOME, CALL_OUTCOMES, SEGMENTS, SOURCES, stamp, type LeadList, type LeadRow, type Metrics } from "@/lib/admin";

type Preset = "" | "not_closed" | "hot_uncontacted";
const PRESETS: { key: Preset; label: string; count: keyof LeadList["counts"] }[] = [
  { key: "", label: "All leads", count: "all" },
  { key: "not_closed", label: "Advisor could not close", count: "not_closed" },
  { key: "hot_uncontacted", label: "High propensity, not contacted", count: "hot_uncontacted" },
];

export default function LeadsPage() {
  const [preset, setPreset] = useState<Preset>("hot_uncontacted");
  const [bucket, setBucket] = useState("");
  const [segment, setSegment] = useState("");
  const [source, setSource] = useState("");
  const [origin, setOrigin] = useState("");
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const [data, setData] = useState<LeadList | null>(null);
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [calling, setCalling] = useState<LeadRow | null>(null);

  const load = useCallback(async () => {
    const p = new URLSearchParams({ page: String(page), page_size: "25" });
    if (preset) p.set("preset", preset);
    if (bucket) p.set("bucket", bucket);
    if (segment) p.set("segment", segment);
    if (source) p.set("source", source);
    if (origin) p.set("origin", origin);
    if (q.trim()) p.set("q", q.trim());
    try {
      setData(await api.get<LeadList>(`/admin/leads?${p}`));
      setError(null);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Couldn't load leads.");
    }
  }, [preset, bucket, segment, source, origin, q, page]);

  const loadMetrics = useCallback(() => api.get<Metrics>("/admin/metrics").then(setMetrics).catch(() => {}), []);

  useEffect(() => {
    const t = setTimeout(load, q ? 250 : 0);
    return () => clearTimeout(t);
  }, [load, q]);
  useEffect(() => {
    loadMetrics();
    const t = setInterval(loadMetrics, 30_000);
    return () => clearInterval(t);
  }, [loadMetrics]);

  const reset = () => {
    setPreset("");
    setBucket("");
    setSegment("");
    setSource("");
    setOrigin("");
    setQ("");
    setPage(1);
  };

  const columns: Column<LeadRow>[] = [
    {
      key: "lead",
      label: "Lead",
      render: (r) => (
        <Link href={`/admin/leads/${r.lead_id}`} className="block min-h-[44px] hover:text-brand">
          <span className="font-semibold">{r.business_name}</span>
          <span className="block text-xs text-ink-2">
            {r.lead_id} · {r.city ?? "—"} · {r.origin === "app" ? <b className="text-brand">App</b> : r.lead_source}
          </span>
        </Link>
      ),
    },
    { key: "contact", label: "Contact", render: (r) => <span className="tabular-nums">{r.contact ?? "—"}</span> },
    { key: "segment", label: "Segment", render: (r) => r.segment ?? <span className="text-muted">not yet known</span> },
    {
      key: "stage",
      label: "Stage",
      render: (r) => (
        <span>
          {r.stage_reached}
          {r.origin === "app" && <span className="block text-xs text-ink-2">{ADVISOR_OUTCOME[r.advisor_outcome] ?? r.advisor_outcome}</span>}
        </span>
      ),
    },
    { key: "drop", label: "Drop reason", className: "max-w-[180px]", render: (r) => r.drop_reason ?? <span className="text-muted">—</span> },
    { key: "prop", label: "Propensity", render: (r) => <PropensityBadge p={r.propensity} /> },
    {
      key: "reasons",
      label: "Top reasons",
      className: "max-w-[220px]",
      render: (r) => (
        <ul className="text-xs leading-snug">
          {(r.propensity?.reasons ?? []).map((x) => (
            <li key={x} className={x.startsWith("+") ? "text-ok" : "text-brand-dark"}>
              {x}
            </li>
          ))}
        </ul>
      ),
    },
    {
      key: "last",
      label: "Last contact",
      render: (r) =>
        r.last_call ? (
          <span className="text-xs">
            {stamp(r.last_call.at)}
            <span className="block text-ink-2">
              {r.last_call.agent ?? "Admin"} · {r.last_call.outcome ? CALL_OUTCOMES[r.last_call.outcome] : "no outcome yet"}
            </span>
          </span>
        ) : (
          <span className="text-xs text-muted">never</span>
        ),
    },
    {
      key: "act",
      label: "",
      render: (r) => (
        <button type="button" className="btn-ghost whitespace-nowrap" onClick={() => setCalling(r)} data-testid={`call-${r.lead_id}`}>
          ☎ Call
        </button>
      ),
    },
  ];

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-bold">Leads</h1>
        <p className="text-sm text-ink-2">Imported leads plus every app lead, highest propensity first. The top 20% hold 43% of activations.</p>
      </div>

      {metrics && <MetricStrip metrics={metrics.metrics} period={metrics.baseline_period} />}

      <div className="flex flex-wrap gap-2" role="tablist">
        {PRESETS.map((p) => (
          <button
            key={p.key || "all"}
            role="tab"
            aria-selected={preset === p.key}
            onClick={() => {
              setPreset(p.key);
              setPage(1);
            }}
            className={`min-h-[44px] rounded-full border px-4 text-sm ${preset === p.key ? "border-brand bg-brand-soft font-semibold text-brand" : "border-line bg-white"}`}
            data-testid={`preset-${p.key || "all"}`}
          >
            {p.label}
            {data && <span className="ml-2 tabular-nums text-ink-2">{data.counts[p.count].toLocaleString("en-IN")}</span>}
          </button>
        ))}
      </div>

      <div className="flex flex-wrap items-end gap-2 text-sm">
        <Select label="Bucket" value={bucket} onChange={(v) => (setBucket(v), setPage(1))} options={["High", "Medium", "Low"]} />
        <Select label="Segment" value={segment} onChange={(v) => (setSegment(v), setPage(1))} options={SEGMENTS} />
        <Select label="Source" value={source} onChange={(v) => (setSource(v), setPage(1))} options={SOURCES} />
        <Select label="Origin" value={origin} onChange={(v) => (setOrigin(v), setPage(1))} options={["import", "app"]} names={{ import: "Imported", app: "App" }} />
        <label className="min-w-[200px] flex-1">
          <span className="mb-1 block text-xs text-ink-2">Search</span>
          <input className="field" placeholder="Lead id, business or city" value={q} onChange={(e) => (setQ(e.target.value), setPage(1))} />
        </label>
      </div>

      {error && (
        <p className="rounded-lg bg-brand-soft px-3 py-2 text-sm text-brand-dark" role="alert">
          {error}
        </p>
      )}

      {data && (
        <>
          <DataTable
            testId="leads"
            columns={columns}
            rows={data.items}
            rowKey={(r) => r.lead_id}
            empty={
              <>
                No leads match these filters.{" "}
                <button className="font-semibold text-brand" onClick={reset}>
                  Reset filters
                </button>
              </>
            }
          />
          <div className="flex items-center justify-between text-sm text-ink-2">
            <span>
              {data.total.toLocaleString("en-IN")} leads · page {data.page} of {Math.max(1, Math.ceil(data.total / data.page_size))}
            </span>
            <div className="flex gap-2">
              <button className="btn-ghost" disabled={page <= 1} onClick={() => setPage(page - 1)}>
                Previous
              </button>
              <button className="btn-ghost" disabled={page * data.page_size >= data.total} onClick={() => setPage(page + 1)}>
                Next
              </button>
            </div>
          </div>
        </>
      )}

      {calling && (
        <CallPanel
          leadId={calling.lead_id}
          label={`${calling.business_name} · ${calling.contact ?? calling.lead_id}`}
          onClose={() => {
            setCalling(null);
            load();
          }}
          onSaved={() => {
            load();
            loadMetrics();
          }}
        />
      )}
    </div>
  );
}

function Select({ label, value, onChange, options, names }: { label: string; value: string; onChange: (v: string) => void; options: string[]; names?: Record<string, string> }) {
  return (
    <label>
      <span className="mb-1 block text-xs text-ink-2">{label}</span>
      <select className="field min-w-[140px] pr-8" value={value} onChange={(e) => onChange(e.target.value)} aria-label={label}>
        <option value="">Any</option>
        {options.map((o) => (
          <option key={o} value={o}>
            {names?.[o] ?? o}
          </option>
        ))}
      </select>
    </label>
  );
}
