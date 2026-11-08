"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { Header } from "@/components/Header";
import { HumanBanner } from "@/components/HumanBanner";
import { StepTimeline } from "@/components/StepTimeline";
import { TalkSheet } from "@/components/TalkSheet";
import { api, ApiError, auth, errorText, type NotificationRow, type Tracker } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { store } from "@/lib/store";

const POLL_MS = 60_000;

function clock(iso: string, lang: string) {
  return new Date(iso).toLocaleTimeString(lang === "en" ? "en-IN" : `${lang}-IN`, { hour: "numeric", minute: "2-digit" });
}

export default function TrackerPage() {
  const { t, lang } = useI18n();
  const router = useRouter();
  const { id } = useParams<{ id: string }>();
  const [data, setData] = useState<Tracker | null>(null);
  const [offline, setOffline] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sheet, setSheet] = useState(false);
  const [wa, setWa] = useState(false);
  const [updates, setUpdates] = useState<NotificationRow[]>([]);

  const load = useCallback(async () => {
    try {
      const d = await api.tracker(id, lang);
      setData(d);
      setOffline(false);
      store.set(`tracker:${id}`, JSON.stringify(d));
      api.notifications(`?order_id=${encodeURIComponent(id)}&limit=40`).then((r) => setUpdates(r.items)).catch(() => {});
    } catch (e) {
      if (e instanceof ApiError && e.code === "NETWORK") {
        const cached = store.get(`tracker:${id}`);
        if (cached) setData(JSON.parse(cached));
        setOffline(true);
      } else setError(errorText(e, t));
    }
  }, [id, lang, t]);

  useEffect(() => {
    if (!auth.token()) {
      router.replace("/login");
      return;
    }
    setWa(Boolean(auth.user()?.whatsapp_opt_in));
    load();
    const timer = setInterval(load, POLL_MS);
    const vis = () => document.visibilityState === "visible" && load();
    document.addEventListener("visibilitychange", vis);
    return () => {
      clearInterval(timer);
      document.removeEventListener("visibilitychange", vis);
    };
  }, [load, router]);

  const toggleWa = async () => {
    const next = !wa;
    setWa(next);
    try {
      const r = await api.patchMe({ whatsapp_opt_in: next });
      const u = auth.user();
      if (u && auth.token()) auth.set(auth.token()!, { ...u, whatsapp_opt_in: r.user.whatsapp_opt_in });
    } catch {
      setWa(!next);
    }
  };

  const active = data && !["LIVE", "CANCELLED"].includes(data.state);

  return (
    <>
      <Header />
      <main className="mx-auto w-full max-w-[480px] flex-1 space-y-4 px-4 pb-32 pt-4">
        {error && (
          <p className="rounded-xl bg-brand-soft px-4 py-3 text-sm text-brand" role="alert">
            {error}
          </p>
        )}
        {data && (
          <>
            <div>
              <p className="text-sm text-ink-2">
                {t("tracker.title")} · {data.display_id}
              </p>
              <h1 className="text-2xl font-bold leading-tight" data-testid="headline">
                {data.headline}
              </h1>
            </div>

            {offline && (
              <p className="rounded-xl border border-line bg-white px-4 py-3 text-sm" role="status">
                {t("tracker.offline", { time: clock(data.as_of, lang) })}
              </p>
            )}

            {data.delayed && data.delay_message && (
              <div className="rounded-xl border border-warn/40 bg-[#fff6ec] px-4 py-3" role="alert" data-testid="delay-banner">
                <p className="font-semibold text-[#8a4f00]">⚠ {data.delay_message}</p>
              </div>
            )}

            {data.escalation && <HumanBanner human={data.escalation} title={t("tracker.on_it")} />}

            {data.next_action && (
              <Link href={data.next_action === "consent" ? `/order/${id}/consent` : `/order/${id}/kyc`} className="btn-primary min-h-[48px]" data-testid="next-action">
                {data.next_action === "consent" ? t("tracker.give_consent") : t("tracker.continue_kyc")}
              </Link>
            )}

            <section className="card p-4">
              <StepTimeline steps={data.steps} lang={lang} />
            </section>

            <label className="card flex min-h-[56px] cursor-pointer items-center justify-between gap-3 px-4">
              <span className="text-sm font-medium">{t("tracker.whatsapp")}</span>
              <input type="checkbox" role="switch" checked={wa} onChange={toggleWa} className="h-6 w-6 accent-[var(--color-brand)]" />
            </label>

            {updates.some((u) => u.channel === "in_app") && (
              <section className="card p-4" data-testid="updates">
                <h2 className="mb-2 text-sm font-semibold text-ink-2">{t("tracker.updates")}</h2>
                <ul className="space-y-3">
                  {updates
                    .filter((u) => u.channel === "in_app")
                    .slice(0, 5)
                    .map((u) => {
                      const onWa = updates.some((w) => w.channel === "whatsapp" && w.template === u.template && ["sent", "delivered", "queued"].includes(w.status));
                      return (
                        <li key={u.id} className="text-sm leading-snug">
                          <p>{u.preview.replace(/^Accel Business:\s*/, "").replace(/\s*https?:\/\/\S+$/, "")}</p>
                          <p className="mt-0.5 text-xs text-muted">
                            {clock(u.created_at, lang)}
                            {onWa && <> · <span className="text-ok">{t("tracker.sent_whatsapp")}</span></>}
                          </p>
                        </li>
                      );
                    })}
                </ul>
              </section>
            )}

            <p className="text-center text-xs text-muted">{t("tracker.updated", { time: clock(data.as_of, lang) })}</p>
          </>
        )}
      </main>

      {active && (
        <div className="fixed inset-x-0 bottom-0 z-30 mx-auto w-full max-w-[480px] border-t border-line bg-white px-4 pb-4 pt-3">
          <button type="button" className={data?.escalation ? "btn-ghost min-h-[48px] w-full" : "btn-primary min-h-[48px]"} onClick={() => setSheet(true)} data-testid="talk">
            {t("tracker.talk")}
          </button>
        </div>
      )}

      {sheet && data && (
        <TalkSheet
          orderId={id}
          delayed={data.delayed}
          onClose={() => setSheet(false)}
          onDone={(h) => {
            setSheet(false);
            setData({ ...data, escalation: h });
            load();
          }}
        />
      )}
    </>
  );
}
