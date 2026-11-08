"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { api, auth, errorText } from "@/lib/api";
import { countdown, LANG_NAME, TRIGGER, type Queue } from "@/lib/admin";
import { useI18n } from "@/lib/i18n";

type Tab = "mine" | "open" | "all";

export default function EscalationQueue() {
  const { t } = useI18n();
  const isAgent = auth.user()?.role === "agent";
  const [tab, setTab] = useState<Tab>(isAgent ? "mine" : "open");
  const [data, setData] = useState<Queue | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [now, setNow] = useState(Date.now());

  const load = useCallback(async () => {
    const q = tab === "mine" ? "?mine=true" : tab === "all" ? "?status=all" : "";
    try {
      setData(await api.get<Queue>(`/escalations${q}`));
      setError(null);
    } catch (e) {
      setError(errorText(e, t));
    }
  }, [tab, t]);

  useEffect(() => {
    load();
    const a = setInterval(load, 15000);
    const b = setInterval(() => setNow(Date.now()), 30000);
    return () => {
      clearInterval(a);
      clearInterval(b);
    };
  }, [load]);

  const takeIt = async (id: string) => {
    try {
      await api.patch(`/escalations/${id}`, { action: "assign" });
      load();
    } catch (e) {
      setError(errorText(e, t));
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">Escalations</h1>
          <p className="text-sm text-ink-2">AI handles acquisition; you handle the exceptions. Breached cases are pinned to the top.</p>
        </div>
        {data && (
          <div className="flex gap-2 text-sm" data-testid="counts">
            <span className="rounded-lg border border-line bg-white px-3 py-2">
              <b>{data.counts.open}</b> unassigned
            </span>
            <span className="rounded-lg border border-line bg-white px-3 py-2">
              <b>{data.counts.assigned}</b> assigned
            </span>
            <span className={`rounded-lg border px-3 py-2 ${data.counts.breached ? "border-brand/40 bg-brand-soft text-brand" : "border-line bg-white"}`}>
              <b>{data.counts.breached}</b> past SLA
            </span>
          </div>
        )}
      </div>

      <div className="flex gap-1" role="tablist">
        {(["mine", "open", "all"] as Tab[]).map((x) => (
          <button key={x} role="tab" aria-selected={tab === x} type="button" onClick={() => setTab(x)}
            className={`min-h-[44px] rounded-lg px-4 text-sm ${tab === x ? "bg-ink font-semibold text-white" : "border border-line bg-white"}`}>
            {x === "mine" ? "Mine" : x === "open" ? "Open" : "All"}
          </button>
        ))}
      </div>

      {error && <p className="rounded-lg bg-brand-soft px-4 py-3 text-sm text-brand" role="alert">{error}</p>}

      {data && data.items.length === 0 && <div className="card p-8 text-center text-ink-2">No open escalations. That’s a good state.</div>}

      {data && data.items.length > 0 && (
        <div className="card overflow-x-auto">
          <table className="w-full min-w-[820px] text-left text-sm" data-testid="queue">
            <thead className="border-b border-line text-xs uppercase tracking-wide text-muted">
              <tr>
                <th className="px-4 py-3">Priority</th>
                <th className="px-4 py-3">Case</th>
                <th className="px-4 py-3">Business</th>
                <th className="px-4 py-3">SLA</th>
                <th className="px-4 py-3">Agent</th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody>
              {data.items.map((r) => {
                const c = countdown(r.sla_due_at, now);
                return (
                  <tr key={r.escalation_id} className={`border-b border-line last:border-0 ${r.breached ? "bg-brand-soft/40" : ""}`}>
                    <td className="px-4 py-3 align-top">
                      <span className={`inline-block rounded px-2 py-0.5 text-xs font-bold ${r.priority === "P1" ? "bg-brand text-white" : r.priority === "P2" ? "bg-[#fff1df] text-[#8a4f00]" : "bg-canvas text-ink-2"}`}>
                        {r.priority}
                      </span>
                    </td>
                    <td className="max-w-[340px] px-4 py-3 align-top">
                      <Link href={`/admin/escalations/${r.escalation_id}`} className="font-semibold text-ink hover:text-brand">
                        {TRIGGER[r.trigger] ?? r.trigger}
                        {r.order_display_id ? ` · ${r.order_display_id}` : ""}
                      </Link>
                      <p className="line-clamp-2 text-ink-2">{r.reason}</p>
                    </td>
                    <td className="px-4 py-3 align-top">
                      <p>{r.business ?? "—"}</p>
                      <p className="text-xs text-muted">
                        {[r.city, r.language ? LANG_NAME[r.language] : null].filter(Boolean).join(" · ")}
                      </p>
                    </td>
                    <td className={`whitespace-nowrap px-4 py-3 align-top font-medium ${c.late ? "text-brand" : "text-ink-2"}`}>{c.text}</td>
                    <td className="px-4 py-3 align-top">{r.agent ?? <span className="text-brand">Unassigned</span>}</td>
                    <td className="px-4 py-3 text-right align-top">
                      {r.status === "open" ? (
                        <button type="button" className="btn-ghost" onClick={() => takeIt(r.escalation_id)}>Assign to me</button>
                      ) : (
                        <Link href={`/admin/escalations/${r.escalation_id}`} className="btn-ghost">Open</Link>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
