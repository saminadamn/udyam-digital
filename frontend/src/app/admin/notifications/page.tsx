"use client";

import { useCallback, useEffect, useState } from "react";
import { DataTable, type Column } from "@/components/DataTable";
import { api, ApiError, type NotificationRow } from "@/lib/api";
import { LANG_NAME, stamp } from "@/lib/admin";

const STATUS: Record<string, string> = {
  sent: "bg-[#eef8f2] text-ok",
  delivered: "bg-[#eef8f2] text-ok",
  queued: "bg-[#fff6ec] text-[#8a4f00]",
  failed: "bg-brand-soft text-brand-dark",
  skipped_no_optin: "bg-canvas text-ink-2",
};

export default function Outbox() {
  const [channel, setChannel] = useState("whatsapp");
  const [rows, setRows] = useState<NotificationRow[]>([]);
  const [provider, setProvider] = useState<string | undefined>();
  const [msg, setMsg] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const r = await api.notifications(`?scope=all&limit=200${channel ? `&channel=${channel}` : ""}`);
      setRows(r.items);
      setProvider(r.provider);
    } catch (e) {
      setMsg(e instanceof ApiError ? e.message : "Couldn't load the outbox.");
    }
  }, [channel]);
  useEffect(() => {
    load();
    const t = setInterval(load, 5000);
    return () => clearInterval(t);
  }, [load]);

  const resend = async (n: NotificationRow) => {
    try {
      const r = await api.post<{ status: string }>("/notifications/whatsapp", {
        user_id: n.user_id, order_id: n.order_id, template: n.template, language: n.language, params: n.params ?? {},
      });
      setMsg(`Resent: ${r.status}`);
      load();
    } catch (e) {
      setMsg(e instanceof ApiError ? e.message : "Resend failed.");
    }
  };

  const columns: Column<NotificationRow>[] = [
    { key: "time", label: "Time", render: (n) => <span className="whitespace-nowrap text-xs">{stamp(n.created_at)}</span> },
    { key: "to", label: "To", render: (n) => <span className="tabular-nums">{n.to ?? "—"}</span> },
    { key: "ch", label: "Channel", render: (n) => (n.channel === "whatsapp" ? "WhatsApp" : n.channel === "in_app" ? "In app" : n.channel) },
    { key: "tpl", label: "Template", render: (n) => <code className="text-xs">{n.template}</code> },
    {
      key: "status",
      label: "Status",
      render: (n) => (
        <span>
          <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${STATUS[n.status] ?? ""}`} data-testid="status">
            {n.status === "skipped_no_optin" ? "not opted in" : n.status}
          </span>
          {n.error && <span className="mt-1 block text-xs text-brand-dark">{n.error}</span>}
        </span>
      ),
    },
    {
      key: "preview",
      label: "Message",
      className: "max-w-[420px]",
      render: (n) => (
        <span className="block text-sm leading-snug [overflow-wrap:anywhere]" data-testid="preview">
          {n.preview}
          <span className="block text-xs text-muted">
            {LANG_NAME[n.language] ?? n.language}
            {n.display_id ? ` · ${n.display_id}` : ""}
            {n.provider_ref ? ` · ${n.provider_ref}` : ""}
          </span>
        </span>
      ),
    },
    {
      key: "act",
      label: "",
      render: (n) =>
        n.channel === "whatsapp" && n.user_id ? (
          <button className="btn-ghost" onClick={() => resend(n)}>
            Resend
          </button>
        ) : null,
    },
  ];

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">Outbox</h1>
          <p className="text-sm text-ink-2">Every update sent to customers. Messages go out only to owners who opted in at login.</p>
        </div>
        <span className="rounded-lg border border-line bg-white px-3 py-2 text-sm" data-testid="provider">
          Sending via <b>{provider === "twilio" ? "Twilio WhatsApp sandbox" : provider ? `mock outbox${provider.includes("(") ? " (Twilio not configured)" : ""}` : "…"}</b>
        </span>
      </div>
      <div className="flex gap-2" role="tablist">
        {[["whatsapp", "WhatsApp"], ["in_app", "In app"], ["", "All"]].map(([k, v]) => (
          <button key={k || "all"} role="tab" aria-selected={channel === k} onClick={() => setChannel(k)}
            className={`min-h-[44px] rounded-full border px-4 text-sm ${channel === k ? "border-brand bg-brand-soft font-semibold text-brand" : "border-line bg-white"}`}>
            {v}
          </button>
        ))}
      </div>
      {msg && <p className="rounded-lg bg-canvas px-3 py-2 text-sm" role="status">{msg}</p>}
      <DataTable testId="outbox" columns={columns} rows={rows} rowKey={(n) => n.id} empty="No messages yet." />
    </div>
  );
}
