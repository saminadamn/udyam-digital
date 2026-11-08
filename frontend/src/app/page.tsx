"use client";

import { useRouter } from "next/navigation";
import { Logo } from "@/components/Header";
import { auth, api } from "@/lib/api";
import { LANGS, useI18n } from "@/lib/i18n";

export default function LanguagePage() {
  const { lang, setLang, t, ready } = useI18n();
  const router = useRouter();

  const go = async () => {
    if (auth.token()) {
      api.patchMe({ language: lang }).catch(() => {});
      router.push("/advisor");
    } else router.push("/login");
  };

  return (
    <main className="flex flex-1 flex-col px-5 pb-6 pt-10">
      <Logo size="lg" />
      <p className="mt-2 text-ink-2">{t("app.tagline")}</p>
      <h1 className="mt-10 text-2xl font-bold">{t("lang.title")}</h1>
      <p className="mt-1 text-sm text-ink-2">{t("lang.subtitle")}</p>
      <div className="mt-6 grid grid-cols-2 gap-3" role="radiogroup" aria-label={t("lang.title")}>
        {LANGS.map((l) => {
          const on = ready && l.code === lang;
          return (
            <button
              key={l.code}
              role="radio"
              aria-checked={on}
              onClick={() => setLang(l.code)}
              className={`flex min-h-[64px] flex-col items-start justify-center rounded-2xl border px-4 text-left transition-colors ${
                on ? "border-brand bg-brand-soft ring-2 ring-brand/30" : "border-line bg-white hover:border-brand"
              }`}
            >
              <span className="text-lg font-semibold">{l.label}</span>
              <span className="text-xs text-muted">{l.english}</span>
            </button>
          );
        })}
      </div>
      <div className="mt-auto pt-8">
        <button className="btn-primary" onClick={go}>
          {t("lang.continue")}
        </button>
      </div>
    </main>
  );
}
