"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { CallPanel } from "@/components/CallPanel";
import { PropensityBadge } from "@/components/PropensityBadge";
import { api, ApiError } from "@/lib/api";
import { ADVISOR_OUTCOME, CALL_OUTCOMES, stamp, type LeadRow, type Propensity } from "@/lib/admin";

type Detail = {
  lead: LeadRow & Record<string, unknown> & { dates: Record<string, string | null>; products_of_interest: string[]; whatsapp_opt_in: boolean; can_dial: boolean };
  propensity: Propensity;
  conversation_summary: string | null;
  conversation: { status: string; messages: { role: string; content: string; at: string }[] } | null;
  quote: { status: string; monthly_total_inr: number; items: string[]; order: { display_id: string; state: string } | null } | null;
  calls: { call_id: string; provider: string; outcome: string | null; duration_s: number | null; at: string; agent: string }[];
  notes: { note_id: string; body: string; at: string; agent: string }[];
};

const FIELDS: [string, string][] = [
  ["business_type", "Business type"], ["segment", "Segment"], ["city", "City"], ["state", "State"], ["city_tier", "City tier"],
  ["employees", "Employees"], ["sites", "Sites"], ["turnover_band", "Turnover"], ["gstin_masked", "GSTIN"], ["udyam_masked", "Udyam"],
  ["current_internet", "Internet today"], ["current_provider", "Provider"], ["monthly_telecom_spend_inr", "Telecom spend / mo"],
  ["preferred_language", "Language"], ["contact_role", "Contact role"], ["lead_source", "Source"],
];

export default function LeadDetail() {
  const { id } = useParams<{ id: string }>();
  const [d, setD] = useState<Detail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [calling, setCalling] = useState(false);
  const [note, setNote] = useState("");

  const load = useCallback(async () => {
    try {
      setD(await api.get<Detail>(`/admin/leads/${id}`));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Couldn't load the lead.");
    }
  }, [id]);
  useEffect(() => {
    load();
  }, [load]);

  const addNote = async () => {
    if (!note.trim()) return;
    await api.post(`/admin/leads/${id}/notes`, { body: note });
    setNote("");
    load();
  };

  if (error) return <p className="rounded-lg bg-brand-soft px-3 py-2 text-sm text-brand-dark">{error}</p>;
  if (!d) return <p className="text-sm text-ink-2">Loading…</p>;
  const l = d.lead;
  const recent = l.last_call && Date.now() - new Date(l.last_call.at).getTime() < 24 * 3600 * 1000;

  return (
    <div className="space-y-4">
      <Link href="/admin/leads" className="inline-flex min-h-[44px] items-center text-sm text-ink-2 hover:text-brand">
        ← All leads
      </Link>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">{l.business_name}</h1>
          <p className="text-sm text-ink-2">
            {l.lead_id} · {l.contact ?? "no contact"} · {l.origin === "app" ? "App lead" : "Imported lead"} · {l.lead_status}
          </p>
        </div>
        <div className="text-right">
          <button className="btn-primary w-auto px-6" onClick={() => setCalling(true)} data-testid="call">
            ☎ Call
          </button>
          {recent && (
            <p className="mt-1 text-xs text-ink-2">
              Called {stamp(l.last_call!.at)} by {l.last_call!.agent ?? "Admin"}
            </p>
          )}
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <section className="card p-4 md:col-span-2">
          <h2 className="mb-2 font-semibold">Profile</h2>
          <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm sm:grid-cols-3">
            {FIELDS.map(([k, label]) => (
              <div key={k}>
                <dt className="text-xs text-ink-2">{label}</dt>
                <dd>{l[k] === null || l[k] === undefined || l[k] === "" ? "—" : String(l[k])}</dd>
              </div>
            ))}
          </dl>
          <p className="mt-3 text-sm">
            <span className="text-ink-2">Stage:</span> {l.stage_reached}
            {l.drop_reason && <> · <span className="text-ink-2">dropped:</span> {l.drop_reason}</>}
            {l.origin === "app" && <> · <span className="text-ink-2">advisor:</span> {ADVISOR_OUTCOME[l.advisor_outcome]}</>}
          </p>
          {l.origin === "app" && <p className="mt-1 text-xs text-ink-2">WhatsApp updates: {l.whatsapp_opt_in ? "opted in" : "not opted in"}</p>}
        </section>
        <section className="card p-4">
          <h2 className="mb-2 font-semibold">Propensity</h2>
          <PropensityBadge p={d.propensity} showReasons />
          {d.propensity && <p className="mt-2 text-xs text-ink-2">score {d.propensity.score.toFixed(2)}</p>}
        </section>
      </div>

      <section className="card p-4">
        <h2 className="mb-2 font-semibold">Advisor and quote</h2>
        {!d.conversation && !d.quote && <p className="text-sm text-ink-2">Imported lead, no app activity.</p>}
        {d.conversation_summary && <p className="text-sm">{d.conversation_summary}</p>}
        {d.conversation && (
          <details className="mt-2 text-sm">
            <summary className="min-h-[44px] cursor-pointer py-2 text-ink-2">Last {d.conversation.messages.length} messages ({d.conversation.status})</summary>
            <ul className="space-y-1">
              {d.conversation.messages.map((m, i) => (
                <li key={i}>
                  <b className="text-xs uppercase text-ink-2">{m.role}</b> {m.content}
                </li>
              ))}
            </ul>
          </details>
        )}
        {d.quote && (
          <p className="mt-2 text-sm">
            Quote ({d.quote.status}): Rs {d.quote.monthly_total_inr.toLocaleString("en-IN")}/mo, {d.quote.items.join(", ")}
            {d.quote.order && <> · order {d.quote.order.display_id} is {d.quote.order.state}</>}
          </p>
        )}
      </section>

      <div className="grid gap-4 md:grid-cols-2">
        <section className="card p-4" data-testid="calls">
          <h2 className="mb-2 font-semibold">Calls</h2>
          {!d.calls.length && <p className="text-sm text-ink-2">No calls yet.</p>}
          <ul className="space-y-2 text-sm">
            {d.calls.map((c) => (
              <li key={c.call_id}>
                {stamp(c.at)} · {c.agent} · <b>{c.outcome ? CALL_OUTCOMES[c.outcome] : "no outcome yet"}</b>
                {c.duration_s ? ` · ${Math.round(c.duration_s / 60)} min` : ""} <span className="text-xs text-muted">({c.provider})</span>
              </li>
            ))}
          </ul>
        </section>
        <section className="card p-4">
          <h2 className="mb-2 font-semibold">Notes</h2>
          <div className="mb-3 flex gap-2">
            <input className="field" value={note} onChange={(e) => setNote(e.target.value)} placeholder="Add a note" aria-label="Add a note" />
            <button className="btn-ghost" onClick={addNote} disabled={!note.trim()}>
              Add
            </button>
          </div>
          <ul className="space-y-2 text-sm">
            {d.notes.map((n) => (
              <li key={n.note_id}>
                {n.body} <span className="text-xs text-muted">· {n.agent}, {stamp(n.at)}</span>
              </li>
            ))}
          </ul>
        </section>
      </div>

      {calling && <CallPanel leadId={l.lead_id} label={`${l.business_name} · ${l.contact ?? l.lead_id}`} onClose={() => (setCalling(false), load())} onSaved={load} />}
    </div>
  );
}
