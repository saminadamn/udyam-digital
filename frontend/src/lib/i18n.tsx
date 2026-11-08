"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import bn from "../../messages/bn.json";
import en from "../../messages/en.json";
import gu from "../../messages/gu.json";
import hi from "../../messages/hi.json";
import kn from "../../messages/kn.json";
import mr from "../../messages/mr.json";
import ta from "../../messages/ta.json";
import te from "../../messages/te.json";
import { store } from "./store";

export const LANGS = [
  { code: "hi", label: "हिंदी", english: "Hindi" },
  { code: "en", label: "English", english: "English" },
  { code: "mr", label: "मराठी", english: "Marathi" },
  { code: "ta", label: "தமிழ்", english: "Tamil" },
  { code: "bn", label: "বাংলা", english: "Bengali" },
  { code: "kn", label: "ಕನ್ನಡ", english: "Kannada" },
  { code: "gu", label: "ગુજરાતી", english: "Gujarati" },
  { code: "te", label: "తెలుగు", english: "Telugu" },
] as const;

export type Lang = (typeof LANGS)[number]["code"];
type Dict = typeof en;
const DICTS: Record<Lang, Dict> = { hi, en, mr, ta, bn, kn, gu, te };
const DEFAULT: Lang = (process.env.NEXT_PUBLIC_DEFAULT_LANG as Lang) || "hi";

export function isLang(x: unknown): x is Lang {
  return typeof x === "string" && x in DICTS;
}

function lookup(d: Dict, key: string): string | undefined {
  let node: unknown = d;
  for (const part of key.split(".")) {
    if (node && typeof node === "object" && part in (node as Record<string, unknown>)) node = (node as Record<string, unknown>)[part];
    else return undefined;
  }
  return typeof node === "string" ? node : undefined;
}

type Ctx = { lang: Lang; setLang: (l: Lang) => void; t: (key: string, vars?: Record<string, string | number>) => string; ready: boolean };
const I18nContext = createContext<Ctx | null>(null);

export function I18nProvider({ children }: { children: React.ReactNode }) {
  const [lang, setLangState] = useState<Lang>(DEFAULT);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const saved = store.get("lang");
    if (isLang(saved)) setLangState(saved);
    else {
      const nav = typeof navigator !== "undefined" ? navigator.language.slice(0, 2) : "";
      if (isLang(nav)) setLangState(nav);
    }
    setReady(true);
  }, []);

  useEffect(() => {
    document.documentElement.lang = lang;
  }, [lang]);

  const setLang = useCallback((l: Lang) => {
    setLangState(l);
    store.set("lang", l);
  }, []);

  const t = useCallback(
    (key: string, vars?: Record<string, string | number>) => {
      let s = lookup(DICTS[lang], key) ?? lookup(DICTS.en, key) ?? key;
      if (vars) for (const [k, v] of Object.entries(vars)) s = s.replaceAll(`{${k}}`, String(v));
      return s;
    },
    [lang],
  );

  const value = useMemo(() => ({ lang, setLang, t, ready }), [lang, setLang, t, ready]);
  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n() {
  const ctx = useContext(I18nContext);
  if (!ctx) throw new Error("useI18n must be used inside I18nProvider");
  return ctx;
}
