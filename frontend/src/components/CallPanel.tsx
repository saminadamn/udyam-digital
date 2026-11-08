"use client";

import { useEffect, useRef, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { CALL_OUTCOMES, type CallStart } from "@/lib/admin";

/** A3 "Call" + outcome picker. Starting the panel logs the call (Twilio when configured, otherwise a mock call the agent dials). */
export function CallPanel({ leadId, label, onClose, onSaved }: { leadId: string; label: string; onClose: () => void; onSaved: () => void }) {
  const [call, setCall] = useState<CallStart | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [outcome, setOutcome] = useState<string>("");
  const [minutes, setMinutes] = useState("");
  const [note, setNote] = useState("");
  const [saving, setSaving] = useState(false);
  const [result, setResult] = useState<string | null>(null);
  const started = useRef(false);

  useEffect(() => {
    if (started.current) return;
    started.current = true;
    (async () => {
      try {
        const h = await api.health().catch(() => null);
        const mode = h?.providers.messaging === "twilio" ? "twilio" : "mock";
        setCall(await api.post<CallStart>(`/admin/leads/${leadId}/call`, { mode }));
      } catch (e) {
        setError(e instanceof ApiError ? e.message : "Couldn't log the call.");
      }
    })();
  }, [leadId]);

  const save = async () => {
    if (!call || !outcome) return;
    setSaving(true);
    try {
      const r = await api.patch<{ lead_status: string; advisor_link_sent: boolean }>(`/admin/calls/${call.call_id}`, {
        outcome,
        duration_s: minutes ? Math.round(parseFloat(minutes) * 60) : null,
        note: note.trim() || null,
      });
      setResult(`Saved. Lead is now ${r.lead_status}.${r.advisor_link_sent ? " Advisor link sent on WhatsApp." : ""}`);
      onSaved();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Couldn't save the outcome.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/30 p-4 sm:items-center" role="dialog" aria-modal="true" aria-label={`Call ${label}`}>
      <div className="w-full max-w-md rounded-2xl bg-white p-5 shadow-xl" data-testid="call-panel" data-call={call?.call_id ?? ""}>
        <div className="mb-3 flex items-start justify-between gap-3">
          <div>
            <p className="text-xs uppercase tracking-wide text-ink-2">Follow-up call</p>
            <h2 className="text-lg font-bold">{label}</h2>
          </div>
          <button type="button" className="btn-ghost" onClick={onClose}>
            Close
          </button>
        </div>

        {error && (
          <p className="mb-3 rounded-lg bg-brand-soft px-3 py-2 text-sm text-brand-dark" role="alert" data-testid="call-error">
            {error}
          </p>
        )}
        {!call && !error && <p className="text-sm text-ink-2">Logging the call…</p>}
        {call && (
          <>
            <p className="mb-3 rounded-lg bg-canvas px-3 py-2 text-sm" data-testid="call-status">
              {call.status === "ringing" ? "☎ Ringing your phone now; you'll be connected to the lead." : "☎ Call logged. Dial the customer from your phone, then record how it went."}
              {call.notice && <span className="mt-1 block text-xs text-ink-2">{call.notice}</span>}
            </p>
            {result ? (
              <p className="rounded-lg bg-[#eef8f2] px-3 py-2 text-sm text-ok" role="status" data-testid="call-saved">
                {result}
              </p>
            ) : (
              <>
                <fieldset className="mb-3">
                  <legend className="mb-2 text-sm font-semibold">Outcome</legend>
                  <div className="flex flex-wrap gap-2">
                    {Object.entries(CALL_OUTCOMES).map(([k, v]) => (
                      <button
                        key={k}
                        type="button"
                        aria-pressed={outcome === k}
                        onClick={() => setOutcome(k)}
                        className={`min-h-[44px] rounded-full border px-3 text-sm ${outcome === k ? "border-brand bg-brand text-white" : "border-line bg-white hover:border-brand"}`}
                      >
                        {v}
                      </button>
                    ))}
                  </div>
                </fieldset>
                <div className="mb-3 grid grid-cols-3 gap-2">
                  <label className="col-span-1 text-sm">
                    <span className="mb-1 block text-xs text-ink-2">Minutes</span>
                    <input className="field" inputMode="decimal" value={minutes} onChange={(e) => setMinutes(e.target.value.replace(/[^\d.]/g, ""))} />
                  </label>
                  <label className="col-span-2 text-sm">
                    <span className="mb-1 block text-xs text-ink-2">Note (optional)</span>
                    <input className="field" value={note} onChange={(e) => setNote(e.target.value)} placeholder="e.g. call after 5 pm" />
                  </label>
                </div>
                <button type="button" className="btn-primary" disabled={!outcome || saving} onClick={save} data-testid="save-outcome">
                  {saving ? "Saving…" : "Save outcome"}
                </button>
              </>
            )}
          </>
        )}
      </div>
    </div>
  );
}
