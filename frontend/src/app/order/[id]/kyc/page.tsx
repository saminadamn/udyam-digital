"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { Header } from "@/components/Header";
import { api, auth, DOC_TYPES, errorText, type DocType, type GstinOut, type InstantCheck, type KycResult, type OrderDetail } from "@/lib/api";
import { cleanGstin, gstinState, maskGstin } from "@/lib/gstin";
import { useI18n } from "@/lib/i18n";

type Tile = { state: "empty" | "busy" | "ok" | "problem"; problems: InstantCheck[]; name?: string };
type Step = 1 | 2 | 3;

const blank = (): Record<DocType, Tile> =>
  Object.fromEntries(DOC_TYPES.map((d) => [d, { state: "empty", problems: [] }])) as unknown as Record<DocType, Tile>;

function hhmm(iso: string) {
  return new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function Stepper({ step, t }: { step: Step; t: (k: string) => string }) {
  return (
    <ol className="flex items-center gap-2" aria-label="steps">
      {[1, 2, 3].map((n) => (
        <li key={n} className="flex flex-1 items-center gap-2" aria-current={step === n ? "step" : undefined}>
          <span
            className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-sm font-bold ${step >= n ? "bg-brand text-white" : "bg-line text-ink-2"}`}
          >
            {step > n ? "✓" : n}
          </span>
          <span className={`truncate text-sm ${step === n ? "font-semibold" : "text-ink-2"}`}>{t(`kyc.step${n}`)}</span>
        </li>
      ))}
    </ol>
  );
}

export default function KycPage() {
  const { t, lang } = useI18n();
  const router = useRouter();
  const { id } = useParams<{ id: string }>();
  const [order, setOrder] = useState<OrderDetail | null>(null);
  const [step, setStep] = useState<Step>(1);
  const [gstin, setGstin] = useState("");
  const [found, setFound] = useState<GstinOut | null>(null);
  const [udyam, setUdyam] = useState("");
  const [udyamOk, setUdyamOk] = useState<string | null>(null);
  const [tiles, setTiles] = useState<Record<DocType, Tile>>(blank);
  const [focus, setFocus] = useState<DocType | null>(null);
  const [result, setResult] = useState<KycResult | null>(null);
  const [checking, setChecking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showAll, setShowAll] = useState(false);
  const [withdrawn, setWithdrawn] = useState(false);
  const inputs = useRef<Partial<Record<DocType, HTMLInputElement | null>>>({});
  const caseId = order?.kyc_case_id ?? "";

  const poll = useCallback(
    async (cid: string) => {
      setChecking(true);
      for (let i = 0; i < 40; i++) {
        const r = await api.kycResult(cid);
        if (r.status !== "submitted") {
          setResult(r);
          setChecking(false);
          return r;
        }
        await new Promise((ok) => setTimeout(ok, 1500));
      }
      setChecking(false);
      return null;
    },
    [],
  );

  useEffect(() => {
    if (!auth.token()) {
      router.replace("/login");
      return;
    }
    api
      .getOrder(id)
      .then(async (o) => {
        if (!o.kyc_case_id || o.state === "CANCELLED") {
          router.replace(`/order/${id}/consent`);
          return;
        }
        setOrder(o);
        const r = await api.kycResult(o.kyc_case_id);
        const next = blank();
        for (const d of r.documents) next[d.doc_type] = { state: d.readable ? "ok" : "problem", problems: [] };
        setTiles(next);
        if (r.status === "submitted") {
          setStep(3);
          poll(o.kyc_case_id);
        } else if (r.verdict) {
          setResult(r);
          setStep(3);
        } else if (r.documents.length) setStep(2);
      })
      .catch((e) => setError(errorText(e, t)));
  }, [id, router, t, poll]);

  const g = gstinState(gstin);

  const checkGstin = async () => {
    setError(null);
    try {
      setFound(await api.lookupGstin(gstin, id));
    } catch (e) {
      setFound(null);
      setError(errorText(e, t));
    }
  };

  const checkUdyam = async () => {
    setError(null);
    try {
      const u = await api.lookupUdyam(udyam.trim().toUpperCase(), id);
      setUdyamOk(`${u.udyam_masked} · ${u.enterprise_name}`);
    } catch (e) {
      setUdyamOk(null);
      setError(errorText(e, t));
    }
  };

  const pick = async (doc: DocType, file: File | undefined) => {
    if (!file || !caseId) return;
    setError(null);
    setTiles((s) => ({ ...s, [doc]: { state: "busy", problems: [], name: file.name } }));
    try {
      const r = await api.upload(caseId, doc, file, lang);
      const problems = r.instant_checks.filter((c) => c.result === "fail");
      setTiles((s) => ({ ...s, [doc]: { state: problems.length ? "problem" : "ok", problems, name: file.name } }));
      if (focus === doc && !problems.length) setFocus(null);
    } catch (e) {
      setTiles((s) => ({ ...s, [doc]: { state: "problem", problems: [{ check_code: "UPLOAD", result: "fail", severity: null, message: errorText(e, t) }] } }));
      if ((e as { code?: string }).code === "CONSENT_REQUIRED") router.replace(`/order/${id}/consent`);
    }
  };

  const submit = async () => {
    if (!caseId) return;
    setError(null);
    setStep(3);
    setResult(null);
    try {
      await api.patchMe({ language: lang }).catch(() => {});
      await api.submitKyc(caseId);
      await poll(caseId);
    } catch (e) {
      setError(errorText(e, t));
      setStep(2);
    }
  };

  const reupload = (doc: DocType) => {
    setFocus(doc);
    setTiles((s) => ({ ...s, [doc]: { state: "empty", problems: [] } }));
    setStep(2);
    setTimeout(() => inputs.current[doc]?.click(), 50);
  };

  const withdraw = async () => {
    if (!order?.consent_id) return;
    try {
      await api.withdrawConsent(order.consent_id);
      setWithdrawn(true);
    } catch (e) {
      setError(errorText(e, t));
    }
  };

  const ready = DOC_TYPES.every((d) => tiles[d].state === "ok" || tiles[d].state === "problem");
  const anyBusy = DOC_TYPES.some((d) => tiles[d].state === "busy");
  const passed = result?.checks.filter((c) => c.result === "pass").length ?? 0;

  if (withdrawn)
    return (
      <>
        <Header />
        <main className="mx-auto w-full max-w-[480px] px-4 pt-6">
          <p className="card p-4" role="status">
            {t("consent.withdrawn")}
          </p>
        </main>
      </>
    );

  return (
    <>
      <Header />
      <main className="mx-auto w-full max-w-[480px] flex-1 space-y-4 px-4 pb-36 pt-4">
        <div className="space-y-1">
          {order && <p className="text-sm text-ink-2">{t("consent.order", { id: order.display_id })}</p>}
          <h1 className="text-2xl font-bold">{t("kyc.title")}</h1>
        </div>
        <Stepper step={step} t={t} />

        {error && (
          <p className="rounded-xl border border-brand/30 bg-brand-soft px-4 py-3 text-sm text-brand" role="alert">
            {error}
          </p>
        )}

        {step === 1 && (
          <section className="space-y-4">
            <div className="card space-y-3 p-4">
              <label htmlFor="gstin" className="block font-semibold">
                {t("kyc.gstin_label")}
              </label>
              <div className="flex gap-2">
                <input
                  id="gstin"
                  data-testid="gstin"
                  inputMode="text"
                  autoCapitalize="characters"
                  autoComplete="off"
                  spellCheck={false}
                  value={gstin}
                  onChange={(e) => {
                    setGstin(cleanGstin(e.target.value));
                    setFound(null);
                  }}
                  placeholder="27ABCDE1234F1Z5"
                  className="min-h-[48px] w-full min-w-0 rounded-xl border border-line px-3 font-mono text-base tracking-wider focus:border-brand focus:outline-none"
                />
                <button type="button" className="btn-ghost min-h-[48px] shrink-0" disabled={g !== "ok"} onClick={checkGstin}>
                  {t("kyc.check")}
                </button>
              </div>
              <p className={`text-sm ${g === "format" || g === "checksum" ? "text-brand" : g === "ok" ? "text-ok" : "text-ink-2"}`} aria-live="polite">
                {g === "short" ? t("kyc.gstin_hint") : g === "format" ? t("kyc.gstin_bad_format") : g === "checksum" ? t("kyc.gstin_bad_checksum") : t("kyc.gstin_ok")}
              </p>
              {found && (
                <div className={`rounded-xl border p-3 ${found.status === "Active" ? "border-ok/40" : "border-warn/50 bg-[#fff6ec]"}`} data-testid="gstin-card">
                  <p className="text-sm font-semibold">
                    {found.status === "Active" ? "✓ " : "⚠ "}
                    {t("kyc.found")}
                  </p>
                  <p className="mt-1 font-mono text-sm">{found.gstin_masked || maskGstin(gstin)}</p>
                  <p className="text-sm text-ink-2">{t("kyc.status_line", { name: found.trade_name, state: found.state, status: found.status })}</p>
                  {found.status !== "Active" && (
                    <p className="mt-2 text-sm">
                      {t("kyc.inactive", { status: found.status, items: found.effects.removed_products.map((p) => p.name).join(", ") || "—" })}
                    </p>
                  )}
                </div>
              )}
            </div>
            <div className="card space-y-3 p-4">
              <label htmlFor="udyam" className="block font-semibold">
                {t("kyc.udyam_label")}
              </label>
              <div className="flex gap-2">
                <input
                  id="udyam"
                  value={udyam}
                  autoCapitalize="characters"
                  autoComplete="off"
                  onChange={(e) => {
                    setUdyam(e.target.value.toUpperCase().slice(0, 19));
                    setUdyamOk(null);
                  }}
                  placeholder="UDYAM-DL-00-1234567"
                  className="min-h-[48px] w-full min-w-0 rounded-xl border border-line px-3 font-mono text-base focus:border-brand focus:outline-none"
                />
                <button type="button" className="btn-ghost min-h-[48px] shrink-0" disabled={udyam.length < 19} onClick={checkUdyam}>
                  {t("kyc.check")}
                </button>
              </div>
              {udyamOk && <p className="text-sm text-ok">✓ {udyamOk}</p>}
            </div>
            <button type="button" className="btn-ghost min-h-[44px] w-full" onClick={() => setStep(2)}>
              {t("kyc.no_gst")}
            </button>
          </section>
        )}

        {step === 2 && (
          <section className="space-y-3">
            <div>
              <h2 className="font-semibold">{t("kyc.upload_title")}</h2>
              <p className="text-sm text-ink-2">{t("kyc.upload_hint")}</p>
            </div>
            {DOC_TYPES.map((doc) => {
              const tile = tiles[doc];
              return (
                <div
                  key={doc}
                  data-testid={`tile-${doc}`}
                  data-state={tile.state}
                  className={`card p-4 ${focus === doc ? "ring-2 ring-brand" : ""} ${tile.state === "problem" ? "border-brand/40" : tile.state === "ok" ? "border-ok/40" : ""}`}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="font-semibold">
                        {tile.state === "ok" && <span className="text-ok">✓ </span>}
                        {tile.state === "problem" && <span className="text-brand">! </span>}
                        {t(`kyc.doc_${doc}`)}
                      </p>
                      <p className="text-sm text-ink-2">{tile.state === "busy" ? t("kyc.reading") : t(`kyc.hint_${doc}`)}</p>
                    </div>
                    {tile.state === "busy" && <span className="mt-1 h-5 w-5 shrink-0 animate-spin rounded-full border-2 border-line border-t-brand" aria-hidden />}
                  </div>
                  {tile.problems.map((p) => (
                    <p key={p.check_code} className="mt-2 text-sm text-brand">
                      {p.message}
                    </p>
                  ))}
                  <input
                    ref={(el) => {
                      inputs.current[doc] = el;
                    }}
                    data-testid={`file-${doc}`}
                    type="file"
                    accept="image/png,image/jpeg"
                    className="sr-only"
                    onChange={(e) => {
                      pick(doc, e.target.files?.[0]);
                      e.target.value = "";
                    }}
                  />
                  {tile.state !== "busy" && (
                    <button type="button" className="btn-ghost mt-3 min-h-[44px] w-full" onClick={() => inputs.current[doc]?.click()}>
                      {tile.state === "empty" ? t("kyc.pick") : t("kyc.again")}
                    </button>
                  )}
                </div>
              );
            })}
          </section>
        )}

        {step === 3 && (
          <section className="space-y-3" data-testid="kyc-result" data-verdict={result?.verdict ?? ""}>
            {(checking || !result) && (
              <div className="card flex items-center gap-3 p-4" role="status">
                <span className="h-5 w-5 shrink-0 animate-spin rounded-full border-2 border-line border-t-brand" aria-hidden />
                <span>{t("kyc.checking")}</span>
              </div>
            )}
            {result?.verdict === "verified" && (
              <div className="card border-ok/50 bg-[#eef8f2] p-5 text-center" role="status">
                <p className="text-3xl" aria-hidden>
                  ✓
                </p>
                <p className="text-xl font-bold text-ok">{t("kyc.verified_title")}</p>
                <p className="mt-1 text-sm">{t("kyc.verified_body")}</p>
                <Link href={`/order/${id}`} className="btn-primary mt-4 min-h-[48px]" data-testid="track-order">
                  {t("tracker.track")}
                </Link>
              </div>
            )}
            {result?.verdict === "review" && (
              <div className="card border-warn/50 bg-[#fff6ec] p-4" role="status">
                <p className="font-bold">{t("kyc.review_title")}</p>
                <p className="mt-1 text-sm">
                  {result.escalation?.agent_name
                    ? t("kyc.review_agent", { name: result.escalation.agent_name, time: hhmm(result.escalation.sla_due_at) })
                    : t("kyc.review_queue", { time: result.escalation ? hhmm(result.escalation.sla_due_at) : "" })}
                </p>
              </div>
            )}
            {result?.verdict === "blocked" && (
              <div className="card border-brand/40 bg-brand-soft p-4" role="status">
                <p className="font-bold text-brand">{t("kyc.blocked_title")}</p>
                {result.blocked_items.length > 0 && <p className="mt-1 text-sm">{t("kyc.blocked_items", { items: result.blocked_items.map((i) => i.name).join(", ") })}</p>}
                <p className="mt-1 text-sm">{t("kyc.blocked_body")}</p>
              </div>
            )}
            {result && result.fix.length > 0 && (
              <div className="card p-4">
                <h2 className="font-semibold">{t("kyc.fix_title")}</h2>
                <ul className="mt-2 space-y-3" data-testid="fix-list">
                  {result.fix.map((c, i) => (
                    <li key={c.check_code + i} className="border-t border-line pt-3 first:border-0 first:pt-0">
                      <p className="text-sm">{c.message}</p>
                      {c.action?.type === "reupload" && c.action.doc_type && result.status === "flagged" && (
                        <button type="button" className="btn-ghost mt-2 min-h-[44px]" onClick={() => reupload(c.action!.doc_type!)}>
                          {t("kyc.reupload")} · {t(`kyc.doc_${c.action.doc_type}`)}
                        </button>
                      )}
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {result && result.checks.length > 0 && (
              <div className="card p-4">
                <button type="button" className="flex min-h-[44px] w-full items-center justify-between text-left" onClick={() => setShowAll((v) => !v)} aria-expanded={showAll}>
                  <span className="text-sm font-medium">{t("kyc.passed", { n: passed })}</span>
                  <span className="text-sm text-ink-2">{t("kyc.all_checks")} {showAll ? "▴" : "▾"}</span>
                </button>
                {showAll && (
                  <ul className="mt-2 space-y-1.5">
                    {result.checks.map((c, i) => (
                      <li key={c.check_code + i} className="flex gap-2 text-sm">
                        <span className={c.result === "pass" ? "text-ok" : "text-brand"} aria-label={c.result}>
                          {c.result === "pass" ? "✓" : "✕"}
                        </span>
                        <span className={c.result === "pass" ? "text-ink-2" : ""}>{c.message}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            )}
          </section>
        )}

        <p className="pt-2 text-xs text-muted">🔒 {t("kyc.privacy")}</p>
        {order?.consent_id && result?.verdict !== "verified" && (
          <button type="button" className="min-h-[44px] text-left text-xs text-ink-2 underline" onClick={withdraw}>
            {t("consent.withdraw")}
          </button>
        )}
      </main>

      {step === 1 && (
        <div className="fixed inset-x-0 bottom-0 z-30 mx-auto w-full max-w-[480px] border-t border-line bg-white px-4 pb-4 pt-3">
          <button type="button" className="btn-primary min-h-[48px]" data-testid="kyc-next" onClick={() => setStep(2)} disabled={gstin.length > 0 && !found}>
            {t("kyc.next")}
          </button>
        </div>
      )}
      {step === 2 && (
        <div className="fixed inset-x-0 bottom-0 z-30 mx-auto w-full max-w-[480px] space-y-2 border-t border-line bg-white px-4 pb-4 pt-3">
          {!ready && <p className="text-center text-xs text-ink-2">{t("kyc.need_all")}</p>}
          <button type="button" className="btn-primary min-h-[48px]" data-testid="kyc-submit" disabled={!ready || anyBusy} onClick={submit}>
            {result?.status === "flagged" ? t("kyc.recheck") : t("kyc.submit")}
          </button>
        </div>
      )}
    </>
  );
}
