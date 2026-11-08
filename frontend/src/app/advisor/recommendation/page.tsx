"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { AddonList, BundleCard, PriceBar } from "@/components/Bundle";
import { HumanBanner } from "@/components/Chat";
import { Header } from "@/components/Header";
import { api, auth, errorText, type PlanOption, type Recommendation } from "@/lib/api";
import { rupees } from "@/lib/format";
import { useI18n } from "@/lib/i18n";
import { session } from "@/lib/store";

function RecommendationView() {
  const { t, lang } = useI18n();
  const router = useRouter();
  const cid = useSearchParams().get("c");
  const [rec, setRec] = useState<Recommendation | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [opening, setOpening] = useState(false);
  const [picked, setPicked] = useState<string>("recommended");

  // The plan on screen: the option the owner picked, or the main recommendation (older cached results have no options).
  const options: PlanOption[] = rec?.options ?? [];
  const current = options.find((o) => o.key === picked) ?? options.find((o) => o.recommended);
  const view = current ?? rec;

  const openQuote = async () => {
    if (!rec || !view) return;
    setOpening(true);
    setError(null);
    try {
      const q = await api.createQuote(view.recommendation_id);
      router.push(`/quote/${q.quote_id}`);
    } catch (e) {
      setError(errorText(e, t));
      setOpening(false);
    }
  };

  useEffect(() => {
    if (!auth.token()) {
      router.replace("/login");
      return;
    }
    if (!cid) {
      router.replace("/advisor");
      return;
    }
    const cached = session.get(`rec:${cid}`);
    if (cached) {
      try {
        setRec(JSON.parse(cached));
        return;
      } catch {}
    }
    api
      .recommend(cid)
      .then((r) => {
        session.set(`rec:${cid}`, JSON.stringify(r));
        setRec(r);
      })
      .catch((e) => setError(errorText(e, t)));
  }, [cid, router, t]);

  const qty = (n: number) => t("rec.qty", { n });

  return (
    <>
      <Header />
      <main className="flex flex-1 flex-col gap-4 px-4 py-5">
        <h1 className="text-xl font-bold">{t("rec.title")}</h1>
        {error && <HumanBanner message={error} />}
        {!rec && !error && <div className="card h-40 animate-pulse" aria-busy />}
        {rec && view && (
          <>
            <section className="card p-4">
              {current && !current.recommended ? (
                <>
                  <p className="text-xs font-semibold uppercase tracking-wide text-brand">{t(`rec.opt.${current.key}.name`)}</p>
                  <p className="mt-2 text-[15px] leading-relaxed">{t(`rec.opt.${current.key}.tagline`)}</p>
                </>
              ) : (
                <>
                  <p className="text-xs font-semibold uppercase tracking-wide text-brand">{rec.bundle_name}</p>
                  <p className="mt-2 text-[15px] leading-relaxed">{rec.explanation}</p>
                </>
              )}
            </section>

            {options.length > 1 && (
              <section aria-labelledby="choose-plan">
                <h2 id="choose-plan" className="text-sm font-semibold text-ink-2">
                  {t("rec.choose")}
                </h2>
                <div
                  role="radiogroup"
                  aria-labelledby="choose-plan"
                  data-testid="plan-options"
                  className="-mx-4 mt-2 flex snap-x gap-3 overflow-x-auto px-4 pb-2"
                >
                  {options.map((o) => {
                    const on = o.key === current?.key;
                    return (
                      <button
                        key={o.key}
                        type="button"
                        role="radio"
                        aria-checked={on}
                        data-testid={`plan-${o.key}`}
                        onClick={() => setPicked(o.key)}
                        className={`card w-44 shrink-0 snap-start p-3 text-left transition ${on ? "bg-brand-soft ring-2 ring-brand ring-inset" : ""}`}
                      >
                        {o.recommended && (
                          <span className="mb-1 inline-block rounded-full bg-brand px-2 py-0.5 text-[11px] font-semibold text-white">
                            {t("rec.recommended")}
                          </span>
                        )}
                        <span className="block text-sm font-semibold">{o.recommended ? rec.bundle_name : t(`rec.opt.${o.key}.name`)}</span>
                        <span className="mt-1 block text-xs leading-snug text-ink-2">{t(`rec.opt.${o.key}.tagline`)}</span>
                        <span className="mt-2 block text-base font-bold">
                          {rupees(o.monthly_total_inr, lang)}
                          <span className="ml-1 text-xs font-medium text-ink-2">{t("rec.per_month")}</span>
                        </span>
                        <span className="block text-xs text-muted">{t("rec.live_days", { n: o.max_install_days + 1 })}</span>
                      </button>
                    );
                  })}
                </div>
              </section>
            )}

            <section className="card px-4 pt-3">
              <h2 className="text-sm font-semibold text-ink-2">{t("rec.includes")}</h2>
              <BundleCard items={view.items} qtyLabel={qty} />
            </section>

            <section className="card p-4">
              <PriceBar
                total={view.monthly_total_inr}
                setup={view.setup_total_inr}
                lang={lang}
                labels={{
                  perMonth: t("rec.per_month"),
                  setup: t("rec.setup"),
                  contract: t("rec.contract", { n: view.contract_months }),
                  noHidden: t("rec.no_hidden"),
                }}
              />
              <p className="mt-3 text-sm text-ink-2">{t("rec.live_in", { n: view.max_install_days + 1 })}</p>
            </section>

            {view.addons.length > 0 && (
              <section className="card px-4 pt-3">
                <h2 className="text-sm font-semibold text-ink-2">{t("rec.addons")}</h2>
                <AddonList items={view.addons} lang={lang} qtyLabel={qty} perMonth={t("rec.per_month")} />
              </section>
            )}

            {rec.blocked.length > 0 && (
              <section className="card border-dashed p-4">
                <h2 className="text-sm font-semibold text-ink-2">{t("rec.not_available")}</h2>
                <ul className="mt-2 space-y-2">
                  {rec.blocked.map((b) => (
                    <li key={b.product_id} className="text-sm">
                      <span className="font-medium">{b.name}</span>
                      <span className="block text-ink-2">{b.unlock}</span>
                    </li>
                  ))}
                </ul>
              </section>
            )}

            <div className="mt-2 space-y-2">
              <button className="btn-primary" onClick={openQuote} disabled={opening}>
                {t("rec.next")}
              </button>
              <p className="text-center text-xs text-muted">{t("rec.next_soon")}</p>
              <Link href="/advisor" className="btn-ghost w-full" onClick={() => session.remove("conv")}>
                {t("rec.restart")}
              </Link>
            </div>
          </>
        )}
      </main>
    </>
  );
}

export default function RecommendationPage() {
  return (
    <Suspense>
      <RecommendationView />
    </Suspense>
  );
}
