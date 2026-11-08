"use client";

import { useState } from "react";
import { api, ApiError, errorText, type Human } from "@/lib/api";
import { useI18n } from "@/lib/i18n";

const REASONS = ["r_late", "r_date", "r_plan", "r_other"] as const;
const TIMES = ["morning", "afternoon", "evening"] as const;

export function TalkSheet({ orderId, delayed, onClose, onDone }: { orderId: string; delayed: boolean; onClose: () => void; onDone: (h: Human) => void }) {
  const { t } = useI18n();
  const [reason, setReason] = useState<(typeof REASONS)[number]>(delayed ? "r_late" : "r_date");
  const [time, setTime] = useState<(typeof TIMES)[number] | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const send = async () => {
    setBusy(true);
    setError(null);
    try {
      const reasonText = { r_late: "Installation is late", r_date: "Wants to change installation date", r_plan: "Question about the plan", r_other: "Other" }[reason];
      const h = await api.talkToPerson(orderId, reasonText, time);
      onDone(h);
    } catch (e) {
      if (e instanceof ApiError && e.code === "ESCALATION_EXISTS") onDone(e.details as unknown as Human);
      else setError(errorText(e, t));
    } finally {
      setBusy(false);
    }
  };

  const chip = (on: boolean) => `min-h-[44px] rounded-full border px-4 text-sm ${on ? "border-brand bg-brand-soft font-semibold text-brand" : "border-line bg-white"}`;

  return (
    <div className="fixed inset-0 z-40 flex items-end justify-center bg-black/40" role="dialog" aria-modal="true" aria-labelledby="talk-title" onClick={onClose}>
      <div className="w-full max-w-[480px] space-y-4 rounded-t-2xl bg-white px-4 pb-5 pt-4" onClick={(e) => e.stopPropagation()} data-testid="talk-sheet">
        <div className="mx-auto h-1 w-10 rounded-full bg-line" aria-hidden />
        <div>
          <h2 id="talk-title" className="text-lg font-bold">
            {t("sheet.title")}
          </h2>
          <p className="text-sm text-ink-2">{t("sheet.body")}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          {REASONS.map((r) => (
            <button key={r} type="button" className={chip(reason === r)} aria-pressed={reason === r} onClick={() => setReason(r)}>
              {t(`sheet.${r}`)}
            </button>
          ))}
        </div>
        <div>
          <p className="mb-2 text-sm font-medium">{t("sheet.when")}</p>
          <div className="flex flex-wrap gap-2">
            {TIMES.map((x) => (
              <button key={x} type="button" className={chip(time === x)} aria-pressed={time === x} onClick={() => setTime(time === x ? null : x)}>
                {t(`sheet.${x}`)}
              </button>
            ))}
          </div>
        </div>
        {error && (
          <p className="text-sm text-brand" role="alert">
            {error}
          </p>
        )}
        <div className="flex gap-2">
          <button type="button" className="btn-ghost min-h-[48px] shrink-0" onClick={onClose}>
            {t("sheet.cancel")}
          </button>
          <button type="button" className="btn-primary min-h-[48px]" disabled={busy} onClick={send} data-testid="talk-send">
            {t("sheet.send")}
          </button>
        </div>
      </div>
    </div>
  );
}
