"use client";

import { useCallback, useEffect, useState } from "react";
import { api, errorText, type Tracker } from "@/lib/api";
import { stamp } from "@/lib/admin";
import { useI18n } from "@/lib/i18n";

type OrderRow = {
  order_id: string;
  display_id: string;
  state: string;
  business: string | null;
  state_due_at: string | null;
  expected_install_date: string | null;
  allowed_next: string[];
  escalation: { agent_name: string | null; message: string; trigger: string } | null;
};
type Ev = { from: string | null; to: string; actor: string; note: string | null; at: string };

export default function Simulator() {
  const { t } = useI18n();
  const [orders, setOrders] = useState<OrderRow[]>([]);
  const [sel, setSel] = useState<string | null>(null);
  const [events, setEvents] = useState<Ev[]>([]);
  const [trk, setTrk] = useState<Tracker | null>(null);
  const [hours, setHours] = useState(30);
  const [log, setLog] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const cur = orders.find((o) => o.order_id === sel) ?? null;

  const refresh = useCallback(async (id?: string | null) => {
    const r = await api.get<{ orders: OrderRow[] }>("/admin/orders");
    setOrders(r.orders);
    const pick = id ?? sel ?? r.orders[0]?.order_id ?? null;
    setSel(pick);
    if (pick) {
      const [ev, tr] = await Promise.all([api.get<{ events: Ev[] }>(`/admin/orders/${pick}/events`), api.tracker(pick, "en")]);
      setEvents(ev.events);
      setTrk(tr);
    }
  }, [sel]);

  useEffect(() => {
    refresh().catch((e) => setError(errorText(e, t)));
    const id = setInterval(() => refresh().catch(() => {}), 5000);
    return () => clearInterval(id);
  }, [refresh, t]);

  const note = (s: string) => setLog((l) => [`${new Date().toLocaleTimeString("en-IN")}  ${s}`, ...l].slice(0, 30));

  const advance = async (body: Record<string, unknown>) => {
    if (!sel) return;
    setError(null);
    try {
      const r = await api.post<{ state: string; state_due_at: string | null }>(`/admin/orders/${sel}/advance`, body);
      note(`${cur?.display_id}: ${body.to_state ? `→ ${r.state}` : ""}${body.delay_hours ? ` late by ${body.delay_hours} h (due ${stamp(r.state_due_at)})` : ""}`);
      await refresh(sel);
    } catch (e) {
      setError(errorText(e, t));
    }
  };

  const scan = async () => {
    try {
      const r = await api.post<{ actions: { display_id?: string; order_id: string; action: string; priority?: string }[] }>("/admin/sla/scan", {});
      note(r.actions.length ? r.actions.map((a) => `${a.display_id ?? a.order_id}: ${a.action}${a.priority ? ` ${a.priority}` : ""}`).join("; ") : "SLA scan: nothing overdue");
      await refresh(sel);
    } catch (e) {
      setError(errorText(e, t));
    }
  };

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-bold">Order simulator</h1>
        <p className="text-sm text-ink-2">Demo only. Move an order forward, or make its current step late and let the SLA job escalate it. The job also runs on its own every few minutes.</p>
      </div>
      {error && <p className="rounded-lg bg-brand-soft px-4 py-3 text-sm text-brand" role="alert">{error}</p>}
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)]">
        <section className="card max-h-[70vh] overflow-y-auto">
          <ul data-testid="sim-orders">
            {orders.map((o) => (
              <li key={o.order_id}>
                <button type="button" onClick={() => refresh(o.order_id)}
                  className={`flex w-full items-center justify-between gap-3 border-b border-line px-4 py-3 text-left text-sm ${o.order_id === sel ? "bg-brand-soft" : "hover:bg-canvas"}`}>
                  <span>
                    <b>{o.display_id}</b> <span className="text-ink-2">{o.business ?? ""}</span>
                  </span>
                  <span className="flex items-center gap-2">
                    {o.escalation && <span className="rounded bg-brand px-1.5 text-xs text-white">{o.escalation.agent_name ?? "queue"}</span>}
                    <span className="font-mono text-xs">{o.state}</span>
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </section>

        {cur && (
          <div className="space-y-4">
            <section className="card space-y-4 p-4" data-testid="sim-panel">
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <h2 className="text-lg font-bold">{cur.display_id}</h2>
                <span className="font-mono text-sm">{cur.state}</span>
              </div>
              <p className="text-sm text-ink-2">Due {stamp(cur.state_due_at)} · install {cur.expected_install_date ?? "—"}</p>
              <div>
                <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">Advance to</p>
                <div className="flex flex-wrap gap-2">
                  {cur.allowed_next.length === 0 && <span className="text-sm text-ink-2">Nothing left to do.</span>}
                  {cur.allowed_next.map((s) => (
                    <button key={s} type="button" className="btn-ghost font-mono" onClick={() => advance({ to_state: s })}>
                      {s === cur.state ? `${s} (rebook)` : s}
                    </button>
                  ))}
                </div>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <label htmlFor="late" className="text-sm">Make it late by</label>
                <input id="late" type="number" min={1} max={720} value={hours} onChange={(e) => setHours(Number(e.target.value))}
                  className="min-h-[44px] w-24 rounded-lg border border-line px-3" />
                <span className="text-sm">hours</span>
                <button type="button" className="btn-ghost" onClick={() => advance({ delay_hours: hours })} data-testid="make-late">Apply</button>
                <button type="button" className="btn-primary sm:ml-auto sm:w-auto" onClick={scan} data-testid="run-scan">Run SLA scan now</button>
              </div>
            </section>

            {trk && (
              <section className="card p-4" data-testid="sim-tracker">
                <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">What the customer sees</p>
                <p className="font-semibold">{trk.headline}</p>
                {trk.delayed && <p className="text-sm text-[#8a4f00]">⚠ {trk.delay_message}</p>}
                {trk.escalation && <p className="mt-1 text-sm font-medium">👤 {trk.escalation.message}</p>}
                <ul className="mt-2 text-sm text-ink-2">
                  {trk.steps.map((s) => (
                    <li key={s.key}>{s.status === "done" ? "✓" : s.status === "current" ? "●" : "○"} {s.label}{s.detail ? ` · ${s.detail}` : ""}</li>
                  ))}
                </ul>
              </section>
            )}

            <section className="card p-4">
              <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">Event log</p>
              <ol className="space-y-1 font-mono text-xs">
                {log.map((l, i) => <li key={`l${i}`} className="text-brand">{l}</li>)}
                {[...events].reverse().map((ev, i) => (
                  <li key={i}>{stamp(ev.at)} {ev.from ?? "∅"} → {ev.to} · {ev.actor.split(":")[0]}{ev.note ? ` · ${ev.note}` : ""}</li>
                ))}
              </ol>
            </section>
          </div>
        )}
      </div>
    </div>
  );
}
