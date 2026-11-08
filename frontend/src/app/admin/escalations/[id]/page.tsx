"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { api, auth, errorText } from "@/lib/api";
import { countdown, LANG_NAME, RESOLUTION, stamp, TRIGGER, type Agent } from "@/lib/admin";
import { useI18n } from "@/lib/i18n";

type Detail = {
  escalation: {
    escalation_id: string;
    trigger: string;
    priority: string;
    status: string;
    reason: string;
    sla_due_at: string | null;
    breached: boolean;
    agent: string | null;
    agent_id: string | null;
    created_at: string;
    first_response_at: string | null;
    resolution: string | null;
    resolution_note: string | null;
    customer_was_told: string;
    resolutions: string[];
    language: string | null;
  };
  customer: { phone_masked: string; language: string; whatsapp_opt_in: boolean } | null;
  business: { name: string | null; type: string | null; segment: string; city: string | null; state: string | null; employees: number; sites: number;
    current_internet: string | null; monthly_spend_inr: number | null; gst_status: string; gstin_masked: string | null; has_udyam: boolean } | null;
  lead: { lead_id: string; source: string | null; propensity_bucket: string | null; propensity_score: number | null } | null;
  chat: { summary: string | null; failed_turns: number; status: string; language: string; messages: { role: string; content: string; at: string; flag: string }[] } | null;
  quote: { monthly_total_inr: number; setup_total_inr: number; contract_months: number; items: { product_id: string; name: string; qty: number; line_monthly_inr: number; install_days: number }[] } | null;
  order: { display_id: string; state: string; state_due_at: string | null; expected_install_date: string | null; visit: string | null; payment_status: string;
    events: { from: string | null; to: string; actor: string; note: string | null; at: string }[] } | null;
  kyc: { status: string; verdict: string | null; gstin_masked: string | null; udyam_masked: string | null;
    flags: { check_code: string; severity: string; detail: string }[]; checks: { check_code: string; result: string; severity: string | null; detail: string }[];
    documents: { document_id: string; doc_type: string; version: number; status: string; ocr_confidence: number; deleted_at: string | null }[] } | null;
  history: { escalation_id: string; trigger: string; priority: string; status: string; reason: string; resolution: string | null; created_at: string }[];
};

function Panel({ title, children, testid }: { title: string; children: React.ReactNode; testid?: string }) {
  return (
    <section className="card p-4" data-testid={testid}>
      <h2 className="mb-3 text-xs font-semibold uppercase tracking-wide text-muted">{title}</h2>
      {children}
    </section>
  );
}

function Row({ k, v }: { k: string; v: React.ReactNode }) {
  return (
    <div className="flex justify-between gap-4 border-b border-line py-1.5 text-sm last:border-0">
      <span className="text-ink-2">{k}</span>
      <span className="text-right font-medium">{v ?? "—"}</span>
    </div>
  );
}

export default function EscalationDetail() {
  const { t } = useI18n();
  const { id } = useParams<{ id: string }>();
  const me = auth.user();
  const [d, setD] = useState<Detail | null>(null);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [note, setNote] = useState("");
  const [pick, setPick] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setD(await api.get<Detail>(`/escalations/${id}`));
    } catch (e) {
      setError(errorText(e, t));
    }
  }, [id, t]);

  useEffect(() => {
    load();
    api.get<{ agents: Agent[] }>("/admin/agents").then((r) => setAgents(r.agents)).catch(() => {});
  }, [load]);

  const act = async (body: Record<string, unknown>) => {
    setBusy(true);
    setError(null);
    try {
      await api.patch(`/escalations/${id}`, body);
      setNote("");
      setPick(null);
      await load();
    } catch (e) {
      setError(errorText(e, t));
    } finally {
      setBusy(false);
    }
  };

  if (!d) return error ? <p className="text-brand">{error}</p> : <p className="text-ink-2">Loading…</p>;
  const e = d.escalation;
  const open = ["open", "assigned", "in_progress"].includes(e.status);
  const c = countdown(e.sla_due_at);

  return (
    <div className="space-y-4">
      <Link href="/admin/escalations" className="inline-flex min-h-[44px] items-center text-sm text-ink-2 hover:text-ink">← All escalations</Link>

      <section className={`card p-5 ${e.breached ? "border-brand/40" : ""}`} data-testid="case-header">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="min-w-0">
            <p className="text-sm text-ink-2">
              <span className={`mr-2 rounded px-2 py-0.5 text-xs font-bold ${e.priority === "P1" ? "bg-brand text-white" : "bg-[#fff1df] text-[#8a4f00]"}`}>{e.priority}</span>
              {TRIGGER[e.trigger] ?? e.trigger} · {e.status.replace("_", " ")}
            </p>
            <h1 className="mt-1 text-xl font-bold">{d.business?.name ?? "Customer"}{d.order ? ` · ${d.order.display_id}` : ""}</h1>
            <p className="mt-1 max-w-3xl text-sm">{e.reason}</p>
          </div>
          <div className="text-right text-sm">
            <p className={`text-lg font-bold ${c.late ? "text-brand" : ""}`}>{open ? c.text : e.resolution ? RESOLUTION[e.resolution] ?? e.resolution : e.status}</p>
            <p className="text-ink-2">Agent: {e.agent ?? "unassigned"}</p>
            <p className="text-ink-2">Opened {stamp(e.created_at)}</p>
          </div>
        </div>
        <p className="mt-3 rounded-lg bg-canvas px-3 py-2 text-sm">
          <span className="text-ink-2">Customer was told: </span>
          <span className="font-medium" data-testid="customer-told">“{e.customer_was_told}”</span>
        </p>
        {e.resolution_note && <p className="mt-2 text-sm text-ink-2">Note: {e.resolution_note}</p>}
      </section>

      {open && (
        <section className="card space-y-3 p-4" data-testid="actions">
          <div className="flex flex-wrap gap-2">
            {e.status === "assigned" && e.agent_id && (
              <button type="button" className="btn-ghost" disabled={busy} onClick={() => act({ action: "start" })}>I’m calling now</button>
            )}
            {e.resolutions.map((r) => (
              <button key={r} type="button" aria-pressed={pick === r} disabled={busy}
                className={`min-h-[44px] rounded-xl border px-4 text-sm font-medium ${pick === r ? "border-brand bg-brand text-white" : "border-line bg-white hover:border-brand"}`}
                onClick={() => setPick(r)}>
                {RESOLUTION[r] ?? r}
              </button>
            ))}
          </div>
          {pick && (
            <div className="flex flex-col gap-2 sm:flex-row">
              <input value={note} onChange={(ev) => setNote(ev.target.value)} placeholder="What happened? (required, the next person reads this)"
                className="field flex-1" aria-label="Resolution note" />
              <button type="button" className="btn-primary sm:w-auto" disabled={busy || note.trim().length < 5} onClick={() => act({ action: "resolve", resolution: pick, note })}>
                Resolve
              </button>
            </div>
          )}
          {me?.role === "admin" && agents.length > 0 && (
            <div className="flex flex-wrap items-center gap-2 text-sm">
              <label htmlFor="reassign" className="text-ink-2">Reassign to</label>
              <select id="reassign" className="min-h-[44px] rounded-lg border border-line bg-white px-2" defaultValue=""
                onChange={(ev) => ev.target.value && act({ action: "reassign", agent_id: ev.target.value })}>
                <option value="">Choose…</option>
                {agents.filter((a) => a.id !== e.agent_id).map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.name} ({a.languages.map((l) => LANG_NAME[l] ?? l).join(", ")}; {a.open_cases} open)
                  </option>
                ))}
              </select>
            </div>
          )}
          {error && <p className="text-sm text-brand" role="alert">{error}</p>}
        </section>
      )}

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="space-y-4">
          <Panel title="Customer and business" testid="panel-business">
            {d.business && (
              <>
                <Row k="Business" v={d.business.name} />
                <Row k="Type · segment" v={`${d.business.type ?? "—"} · ${d.business.segment}`} />
                <Row k="Where" v={[d.business.city, d.business.state].filter(Boolean).join(", ")} />
                <Row k="Team · sites" v={`${d.business.employees} people · ${d.business.sites} site${d.business.sites > 1 ? "s" : ""}`} />
                <Row k="Internet now" v={d.business.current_internet} />
                <Row k="GST" v={d.business.gstin_masked ? `${d.business.gstin_masked} (${d.business.gst_status})` : d.business.gst_status} />
              </>
            )}
            {d.customer && (
              <>
                <Row k="Phone" v={d.customer.phone_masked} />
                <Row k="Speaks" v={LANG_NAME[d.customer.language] ?? d.customer.language} />
                <Row k="WhatsApp updates" v={d.customer.whatsapp_opt_in ? "On" : "Off"} />
              </>
            )}
            {d.lead && <Row k="Lead" v={`${d.lead.source ?? "app"} · ${d.lead.propensity_bucket ?? "unscored"}`} />}
          </Panel>

          <Panel title="Advisor chat" testid="panel-chat">
            {!d.chat ? (
              <p className="text-sm text-ink-2">No chat on record.</p>
            ) : (
              <>
                <p className="mb-3 rounded-lg bg-canvas px-3 py-2 text-sm"><span className="text-ink-2">Summary: </span>{d.chat.summary ?? "—"}</p>
                <ul className="max-h-72 space-y-2 overflow-y-auto pr-1 text-sm">
                  {d.chat.messages.map((m, i) => (
                    <li key={i} className={`rounded-lg px-3 py-2 ${m.role === "user" ? "ml-8 bg-brand-soft" : "mr-8 bg-canvas"}`}>{m.content}</li>
                  ))}
                </ul>
                <p className="mt-2 text-xs text-muted">Failed turns: {d.chat.failed_turns} · {LANG_NAME[d.chat.language] ?? d.chat.language}</p>
              </>
            )}
          </Panel>
        </div>

        <div className="space-y-4">
          {d.quote && (
            <Panel title="Plan" testid="panel-quote">
              {d.quote.items.map((i) => (
                <Row key={i.product_id} k={`${i.name}${i.qty > 1 ? ` × ${i.qty}` : ""}`} v={`₹${i.line_monthly_inr.toLocaleString("en-IN")}/mo`} />
              ))}
              <Row k="Total" v={`₹${d.quote.monthly_total_inr.toLocaleString("en-IN")}/mo · ₹${d.quote.setup_total_inr.toLocaleString("en-IN")} setup · ${d.quote.contract_months} months`} />
            </Panel>
          )}

          {d.order && (
            <Panel title="Order timeline" testid="panel-order">
              <Row k="State" v={d.order.state} />
              {d.order.visit && <Row k="Visit" v={d.order.visit} />}
              <Row k="Payment" v={d.order.payment_status} />
              <ol className="mt-3 space-y-1.5 text-sm">
                {d.order.events.map((ev, i) => (
                  <li key={i} className="flex gap-3">
                    <span className="w-28 shrink-0 text-xs text-muted">{stamp(ev.at)}</span>
                    <span><b>{ev.to}</b> <span className="text-ink-2">· {ev.actor.split(":")[0]}{ev.note ? ` · ${ev.note}` : ""}</span></span>
                  </li>
                ))}
              </ol>
            </Panel>
          )}

          {d.kyc && (
            <Panel title="KYC" testid="panel-kyc">
              <Row k="Verdict" v={d.kyc.verdict ?? d.kyc.status} />
              <Row k="GSTIN · Udyam" v={`${d.kyc.gstin_masked ?? "—"} · ${d.kyc.udyam_masked ?? "—"}`} />
              {d.kyc.flags.length > 0 && (
                <ul className="mt-3 space-y-2">
                  {d.kyc.flags.map((f, i) => (
                    <li key={i} className="rounded-lg border border-brand/30 bg-brand-soft/50 px-3 py-2 text-sm">
                      <b>{f.check_code}</b> <span className="text-xs uppercase text-brand">{f.severity}</span>
                      <p className="mt-0.5">{f.detail}</p>
                    </li>
                  ))}
                </ul>
              )}
              <p className="mt-3 text-xs text-muted">
                {d.kyc.checks.filter((x) => x.result === "pass").length} checks passed ·{" "}
                {d.kyc.documents.map((doc) => `${doc.doc_type.replace("_", " ")} v${doc.version}${doc.deleted_at ? " (deleted)" : ""}`).join(", ")}
              </p>
            </Panel>
          )}

          {d.history.length > 0 && (
            <Panel title="Earlier escalations on this order">
              {d.history.map((h) => (
                <Row key={h.escalation_id} k={`${TRIGGER[h.trigger] ?? h.trigger} · ${stamp(h.created_at)}`} v={h.resolution ? RESOLUTION[h.resolution] ?? h.resolution : h.status} />
              ))}
            </Panel>
          )}
        </div>
      </div>
    </div>
  );
}
