"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { Header } from "@/components/Header";
import { api, auth, errorText, type Accepted, type Quote, type QuoteItem } from "@/lib/api";
import { rupees } from "@/lib/format";
import { useI18n } from "@/lib/i18n";
import { addWouldBreak, applyLocal, localBlockReason } from "@/lib/quoteMath";

const SPEND_CHIPS = [500, 1000, 2500, 5000, 10000];

function Stepper({ item, onChange, disabled, label }: { item: QuoteItem; onChange: (n: number) => void; disabled: boolean; label: string }) {
  return (
    <div className="flex items-center gap-1" role="group" aria-label={`${label}: ${item.name}`}>
      <button
        type="button"
        className="h-11 w-11 rounded-lg border border-line bg-white text-lg disabled:opacity-30"
        onClick={() => onChange(item.qty - 1)}
        disabled={disabled || item.qty <= item.qty_min}
        aria-label="−"
      >
        −
      </button>
      <span className="w-8 text-center font-semibold" aria-live="polite">
        {item.qty}
      </span>
      <button
        type="button"
        className="h-11 w-11 rounded-lg border border-line bg-white text-lg disabled:opacity-30"
        onClick={() => onChange(item.qty + 1)}
        disabled={disabled || item.qty >= item.qty_max}
        aria-label="+"
      >
        +
      </button>
    </div>
  );
}

function Toggle({ on, onClick, disabled, label }: { on: boolean; onClick: () => void; disabled: boolean; label: string }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={on}
      aria-label={label}
      onClick={onClick}
      disabled={disabled}
      className={`relative h-11 w-[60px] shrink-0 rounded-full transition-colors disabled:opacity-40 ${on ? "bg-brand" : "bg-line"}`}
    >
      <span className={`absolute top-1.5 h-8 w-8 rounded-full bg-white shadow transition-all ${on ? "left-[24px]" : "left-1.5"}`} />
    </button>
  );
}

export default function QuotePage() {
  const { t, lang } = useI18n();
  const router = useRouter();
  const { id } = useParams<{ id: string }>();
  const [quote, setQuote] = useState<Quote | null>(null);
  const [pending, setPending] = useState(0);
  const [notice, setNotice] = useState<{ pid?: string; text: string } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [accepted, setAccepted] = useState<Accepted | null>(null);
  const [accepting, setAccepting] = useState(false);
  const [askSpend, setAskSpend] = useState(false);
  const [spendInput, setSpendInput] = useState("");
  const seq = useRef(0);

  useEffect(() => {
    if (!auth.token()) {
      router.replace("/login");
      return;
    }
    api
      .getQuote(id)
      .then((q) => {
        setQuote(q);
        setAskSpend(q.current_spend_inr == null);
        if (q.order_id) setAccepted({ quote_id: q.quote_id, status: q.status, order_id: q.order_id, display_id: q.order_display_id || "", state: "QUOTE_ACCEPTED", next_step: "consent", assisted: q.assisted });
      })
      .catch((e) => setError(errorText(e, t)));
  }, [id, router, t]);

  const change = async (item: QuoteItem, body: { selected?: boolean; qty?: number }) => {
    if (!quote) return;
    setNotice(null);
    if (body.selected === false) {
      const reason = localBlockReason(quote, item.product_id);
      if (reason) {
        setNotice({ pid: item.product_id, text: reason });
        return;
      }
    }
    if (body.selected === true && addWouldBreak(quote, item.product_id)) {
      setNotice({ pid: item.product_id, text: t("quote.e_INELIGIBLE") });
      return;
    }
    const before = quote;
    setQuote(applyLocal(quote, item.product_id, body));
    const mine = ++seq.current;
    setPending((n) => n + 1);
    try {
      const fresh = await api.updateItem(quote.quote_id, item.product_id, body);
      if (mine === seq.current) setQuote(fresh);
    } catch (e) {
      if (mine === seq.current) setQuote(before);
      const err = e as { details?: { reason?: string; reasons?: string[] } };
      setNotice({ pid: item.product_id, text: err.details?.reason || errorText(e, t) });
    } finally {
      setPending((n) => n - 1);
    }
  };

  const saveSpend = async (amount: number) => {
    if (!quote || !Number.isFinite(amount) || amount < 0) return;
    setQuote({ ...quote, current_spend_inr: amount, difference_inr: quote.monthly_total_inr - amount });
    setAskSpend(false);
    try {
      setQuote(await api.setSpend(quote.quote_id, Math.round(amount)));
    } catch (e) {
      setError(errorText(e, t));
    }
  };

  const accept = async () => {
    if (!quote) return;
    setAccepting(true);
    setError(null);
    try {
      setAccepted(await api.acceptQuote(quote.quote_id));
    } catch (e) {
      setError(errorText(e, t));
    } finally {
      setAccepting(false);
    }
  };

  const r = (n: number) => rupees(n, lang);
  const core = quote?.items.filter((i) => i.role === "core") ?? [];
  const addons = quote?.items.filter((i) => i.role === "addon") ?? [];
  const locked = Boolean(accepted) || quote?.status !== "draft";

  const row = (i: QuoteItem) => (
    <li key={i.product_id} className="py-3">
      <div className="flex items-center gap-3">
        <div className="min-w-0 flex-1">
          <p className={`font-semibold leading-snug ${i.selected ? "" : "text-ink-2"}`}>{i.name}</p>
          <p className="text-xs text-ink-2">{i.why}</p>
          <p className="mt-0.5 text-sm">
            <span className={i.selected ? "font-medium" : "text-muted"}>{r(i.line_monthly_inr)}</span>
            <span className="text-xs text-muted"> {t("quote.per_month")}</span>
            {i.qty > 1 && <span className="text-xs text-muted"> · {t("quote.each", { price: r(i.unit_price_inr) })}</span>}
            {i.line_setup_inr > 0 && <span className="text-xs text-muted"> · {t("quote.setup")} {r(i.line_setup_inr)}</span>}
          </p>
        </div>
        {i.locked && i.selected ? (
          <button
            type="button"
            className="inline-flex min-h-[44px] shrink-0 items-center gap-1 rounded-full bg-canvas px-3 text-xs font-medium text-ink-2"
            onClick={() => setNotice({ pid: i.product_id, text: i.lock_reason || "" })}
            aria-label={`${t("quote.locked")}: ${i.lock_reason}`}
          >
            🔒 {t("quote.locked")}
          </button>
        ) : (
          <Toggle on={i.selected} disabled={locked} label={`${i.selected ? t("quote.remove") : t("quote.add")} ${i.name}`} onClick={() => change(i, { selected: !i.selected })} />
        )}
      </div>
      {i.qty_editable && i.selected && (
        <div className="mt-2 flex items-center justify-between">
          <span className="text-xs text-ink-2">{t("quote.qty")}</span>
          <Stepper item={i} label={t("quote.qty")} disabled={locked} onChange={(n) => change(i, { qty: n })} />
        </div>
      )}
      {notice?.pid === i.product_id && (
        <p className="mt-2 rounded-lg bg-brand-soft px-3 py-2 text-sm text-brand-dark" role="alert">
          {notice.text}
        </p>
      )}
    </li>
  );

  return (
    <>
      <Header />
      <main className="flex flex-1 flex-col gap-4 px-4 pb-40 pt-5">
        <h1 className="text-xl font-bold">{t("quote.title")}</h1>
        {error && (
          <p className="rounded-xl bg-brand-soft px-4 py-3 text-sm text-brand-dark" role="alert">
            {error}
          </p>
        )}
        {!quote && !error && <div className="card h-48 animate-pulse" aria-busy />}
        {quote && (
          <>
            {quote.assisted && !accepted && <p className="rounded-xl border border-line bg-white px-4 py-3 text-sm">{t("quote.assisted")}</p>}
            <section className="card px-4 pt-3">
              <h2 className="text-sm font-semibold text-ink-2">{t("quote.included")}</h2>
              <ul className="divide-y divide-line">{core.map(row)}</ul>
            </section>
            {addons.length > 0 && (
              <section className="card px-4 pt-3">
                <h2 className="text-sm font-semibold text-ink-2">{t("quote.addons")}</h2>
                <ul className="divide-y divide-line">{addons.map(row)}</ul>
              </section>
            )}

            <section className="card p-4" aria-live="polite">
              <h2 className="text-sm font-semibold text-ink-2">{t("quote.compare_title")}</h2>
              {askSpend || quote.current_spend_inr == null ? (
                <div className="mt-2 space-y-3">
                  <p className="text-sm">{t("quote.compare_ask")}</p>
                  <div className="flex flex-wrap gap-2">
                    {SPEND_CHIPS.map((c) => (
                      <button key={c} type="button" className="btn-ghost rounded-full" onClick={() => saveSpend(c)} disabled={locked}>
                        {r(c)}
                      </button>
                    ))}
                  </div>
                  <form
                    className="flex gap-2"
                    onSubmit={(e) => {
                      e.preventDefault();
                      saveSpend(Number(spendInput.replace(/\D/g, "")));
                    }}
                  >
                    <input className="field" inputMode="numeric" placeholder={t("quote.compare_other")} value={spendInput} onChange={(e) => setSpendInput(e.target.value)} aria-label={t("quote.compare_other")} />
                    <button className="btn-ghost shrink-0" disabled={!spendInput.replace(/\D/g, "")}>
                      {t("quote.compare_save")}
                    </button>
                  </form>
                </div>
              ) : (
                <div className="mt-2 flex items-start justify-between gap-2">
                  <div>
                    <p className="font-semibold">
                      {quote.difference_inr! > 0
                        ? t("quote.compare_more", { diff: Math.abs(quote.difference_inr!).toLocaleString("en-IN"), now: quote.current_spend_inr.toLocaleString("en-IN") })
                        : quote.difference_inr! < 0
                          ? t("quote.compare_less", { diff: Math.abs(quote.difference_inr!).toLocaleString("en-IN"), now: quote.current_spend_inr.toLocaleString("en-IN") })
                          : t("quote.compare_same", { now: quote.current_spend_inr.toLocaleString("en-IN") })}
                    </p>
                    {quote.difference_inr! > 0 && <p className="text-xs text-ink-2">{t("quote.compare_note")}</p>}
                  </div>
                  {!locked && (
                    <button type="button" className="text-sm font-medium text-brand min-h-[44px]" onClick={() => setAskSpend(true)}>
                      {t("quote.edit")}
                    </button>
                  )}
                </div>
              )}
            </section>

            {accepted ? (
              <section className="card border-ok/40 p-4" role="status">
                <p className="text-lg font-bold text-ok">✓ {t("quote.accepted_title")}</p>
                <p className="mt-1">{t("quote.accepted_body", { id: accepted.display_id })}</p>
                <p className="mt-2 text-sm text-ink-2">{t("quote.accepted_next")}</p>
                {accepted.assisted && <p className="mt-2 text-sm text-ink-2">{t("quote.assisted")}</p>}
                <Link href={`/order/${accepted.order_id}/consent`} data-testid="continue-kyc" className="btn-primary mt-3 min-h-[48px]">
                  {t("quote.continue_kyc")}
                </Link>
              </section>
            ) : (
              <Link href="/advisor" className="btn-ghost w-full">
                {t("quote.back")}
              </Link>
            )}
          </>
        )}
      </main>

      {quote && (
        <div className="fixed inset-x-0 bottom-0 z-30 mx-auto w-full max-w-[480px] border-t border-line bg-white px-4 pb-4 pt-3 shadow-[0_-4px_16px_rgba(0,0,0,0.06)]">
          <div className="flex items-end justify-between gap-3">
            <div>
              <p className="text-2xl font-bold tracking-tight" data-testid="monthly-total">
                {r(quote.monthly_total_inr)}
                <span className="ml-1 text-sm font-medium text-ink-2">{t("quote.per_month")}</span>
              </p>
              <p className="text-xs text-ink-2">
                {t("quote.contract", { n: quote.contract_months })} · {t("quote.setup")} <span data-testid="setup-total">{r(quote.setup_total_inr)}</span>
              </p>
              <p className="text-xs text-muted">{pending > 0 ? t("quote.updating") : t("quote.live_in", { n: quote.live_in_days })}</p>
            </div>
          </div>
          {!accepted && (
            <button className="btn-primary mt-3" onClick={accept} disabled={accepting || pending > 0 || locked}>
              {accepting ? t("quote.accepting") : t("quote.accept")}
            </button>
          )}
        </div>
      )}
    </>
  );
}
