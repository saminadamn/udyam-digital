"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { Header } from "@/components/Header";
import { api, auth, errorText } from "@/lib/api";
import { useI18n } from "@/lib/i18n";

const DEMO = process.env.NEXT_PUBLIC_DEMO_MODE !== "false";

export default function LoginPage() {
  const { t, lang } = useI18n();
  const router = useRouter();
  const [phone, setPhone] = useState("");
  const [requestId, setRequestId] = useState<string | null>(null);
  const [devCode, setDevCode] = useState<string | null>(null);
  const [code, setCode] = useState("");
  const [optIn, setOptIn] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const otpRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (auth.token()) router.replace("/advisor");
  }, [router]);
  useEffect(() => {
    if (requestId) otpRef.current?.focus();
  }, [requestId]);

  const send = async () => {
    setError(null);
    setBusy(true);
    try {
      const r = await api.otpRequest(phone);
      setRequestId(r.request_id);
      setDevCode(r.dev_code ?? null);
      setCode("");
    } catch (e) {
      setError(errorText(e, t));
    } finally {
      setBusy(false);
    }
  };

  const verify = async () => {
    if (!requestId) return;
    setError(null);
    setBusy(true);
    try {
      const r = await api.otpVerify(requestId, code, lang, optIn);
      auth.set(r.token, r.user);
      if (r.user.role !== "customer") {
        router.replace("/admin");
        return;
      }
      const live = await api.orders().then((o) => o.orders.find((x) => x.state !== "CANCELLED")).catch(() => undefined);
      router.replace(live ? `/order/${live.order_id}` : "/advisor");
    } catch (e) {
      setError(errorText(e, t));
    } finally {
      setBusy(false);
    }
  };

  const digits = phone.replace(/\D/g, "");
  return (
    <>
      <Header />
      <main className="flex flex-1 flex-col px-5 pb-6 pt-8">
        <h1 className="text-2xl font-bold">{t("login.title")}</h1>
        {!requestId ? (
          <form
            className="mt-6 space-y-4"
            onSubmit={(e) => {
              e.preventDefault();
              send();
            }}
          >
            <label className="block text-sm font-medium text-ink-2" htmlFor="phone">
              {t("login.phone_label")}
            </label>
            <div className="flex gap-2">
              <span className="field flex w-auto items-center text-ink-2">+91</span>
              <input
                id="phone"
                className="field"
                inputMode="numeric"
                autoComplete="tel-national"
                placeholder={t("login.phone_placeholder")}
                value={phone}
                maxLength={14}
                onChange={(e) => setPhone(e.target.value)}
              />
            </div>
            <label className="flex min-h-[44px] items-center gap-3 text-sm">
              <input type="checkbox" className="h-5 w-5 accent-[var(--color-brand)]" checked={optIn} onChange={(e) => setOptIn(e.target.checked)} />
              {t("login.whatsapp_optin")}
            </label>
            <button className="btn-primary" disabled={busy || digits.length < 10}>
              {t("login.send_otp")}
            </button>
          </form>
        ) : (
          <form
            className="mt-6 space-y-4"
            onSubmit={(e) => {
              e.preventDefault();
              verify();
            }}
          >
            {DEMO && devCode && (
              <div className="rounded-xl border border-warn/30 bg-[#fff6e8] px-4 py-3 text-sm" role="status">
                {t("login.dev_code", { code: devCode })}
              </div>
            )}
            <label className="block text-sm font-medium text-ink-2" htmlFor="otp">
              {t("login.otp_label", { phone: `••••••${digits.slice(-4)}` })}
            </label>
            <input
              id="otp"
              ref={otpRef}
              className="field text-center text-2xl tracking-[0.5em]"
              inputMode="numeric"
              autoComplete="one-time-code"
              maxLength={6}
              value={code}
              onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
            />
            <button className="btn-primary" disabled={busy || code.length !== 6}>
              {t("login.verify")}
            </button>
            <div className="flex justify-between gap-2">
              <button type="button" className="btn-ghost" onClick={send} disabled={busy}>
                {t("login.resend")}
              </button>
              <button type="button" className="btn-ghost" onClick={() => setRequestId(null)}>
                {t("login.change_number")}
              </button>
            </div>
          </form>
        )}
        {error && (
          <p className="mt-4 rounded-xl bg-brand-soft px-4 py-3 text-sm text-brand-dark" role="alert">
            {error}
          </p>
        )}
        <p className="mt-auto pt-8 text-xs text-muted">{t("login.privacy")}</p>
      </main>
    </>
  );
}
