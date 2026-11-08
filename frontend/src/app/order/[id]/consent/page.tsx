"use client";

import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Header } from "@/components/Header";
import { api, auth, errorText, type Notice, type OrderDetail } from "@/lib/api";
import { useI18n } from "@/lib/i18n";

const ICONS: Record<string, string> = { collect: "📄", why: "🎯", retention: "🗓️", access: "👤", rights: "↩️" };

export default function ConsentPage() {
  const { t, lang } = useI18n();
  const router = useRouter();
  const { id } = useParams<{ id: string }>();
  const [order, setOrder] = useState<OrderDetail | null>(null);
  const [notice, setNotice] = useState<Notice | null>(null);
  const [agree, setAgree] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [later, setLater] = useState(false);

  useEffect(() => {
    if (!auth.token()) {
      router.replace("/login");
      return;
    }
    api
      .getOrder(id)
      .then((o) => {
        if (o.kyc_case_id && o.state !== "CANCELLED") router.replace(`/order/${id}/kyc`);
        else setOrder(o);
      })
      .catch((e) => setError(errorText(e, t)));
  }, [id, router, t]);

  useEffect(() => {
    setNotice(null);
    api.notice(lang).then(setNotice).catch((e) => setError(errorText(e, t)));
  }, [lang, t]);

  const go = async () => {
    if (!notice) return;
    if (!agree) {
      setError(t("consent.need_agree"));
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await api.giveConsent(id, notice.notice_version, lang);
      router.push(`/order/${id}/kyc`);
    } catch (e) {
      if ((e as { code?: string }).code === "NOTICE_VERSION_OUTDATED") api.notice(lang).then(setNotice);
      setError(errorText(e, t));
      setBusy(false);
    }
  };

  return (
    <>
      <Header />
      <main className="mx-auto w-full max-w-[480px] flex-1 space-y-4 px-4 pb-40 pt-4">
        {order && <p className="text-sm text-ink-2">{t("consent.order", { id: order.display_id })}</p>}
        {!notice ? (
          <p className="text-ink-2" role="status">
            {t("consent.loading")}
          </p>
        ) : (
          <>
            <h1 className="text-2xl font-bold leading-tight">{notice.title}</h1>
            <ul className="space-y-3" data-testid="notice">
              {notice.sections.map((s) => (
                <li key={s.key} className="card flex gap-3 p-4">
                  <span aria-hidden className="text-xl leading-6">
                    {ICONS[s.key]}
                  </span>
                  <div>
                    <h2 className="font-semibold">{s.heading}</h2>
                    <p className="mt-1 text-sm leading-relaxed text-ink-2">{s.body}</p>
                  </div>
                </li>
              ))}
            </ul>
            <p className="text-xs text-muted">{t("consent.version", { v: notice.notice_version })}</p>
          </>
        )}
        {later && (
          <p className="rounded-xl border border-line bg-white px-4 py-3 text-sm" role="status">
            {t("consent.later")}
          </p>
        )}
      </main>

      {notice && (
        <div className="fixed inset-x-0 bottom-0 z-30 mx-auto w-full max-w-[480px] space-y-3 border-t border-line bg-white px-4 pb-4 pt-3 shadow-[0_-4px_16px_rgba(0,0,0,0.06)]">
          <label className="flex min-h-[44px] cursor-pointer items-start gap-3">
            <input
              type="checkbox"
              data-testid="agree"
              checked={agree}
              onChange={(e) => {
                setAgree(e.target.checked);
                setError(null);
              }}
              className="mt-0.5 h-6 w-6 shrink-0 accent-[var(--color-brand)]"
            />
            <span className="text-sm font-medium leading-snug">{notice.agree}</span>
          </label>
          {error && (
            <p className="text-sm text-brand" role="alert">
              {error}
            </p>
          )}
          <div className="flex gap-2">
            <button type="button" className="btn-ghost min-h-[48px] shrink-0" onClick={() => setLater(true)}>
              {t("consent.not_now")}
            </button>
            <button type="button" data-testid="consent-continue" className="btn-primary min-h-[48px]" disabled={busy} onClick={go}>
              {t("consent.continue")}
            </button>
          </div>
        </div>
      )}
    </>
  );
}
