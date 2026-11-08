"use client";

import Link from "next/link";
import { LANGS, useI18n, type Lang } from "@/lib/i18n";

export function Logo({ size = "md" }: { size?: "md" | "lg" }) {
  const big = size === "lg";
  return (
    <span className="inline-flex items-center gap-2" aria-label="Accel Business">
      <svg width={big ? 36 : 28} height={big ? 36 : 28} viewBox="0 0 32 32" aria-hidden>
        <rect width="32" height="32" rx="9" fill="var(--color-brand)" />
        <path d="M9 22 L16 9 L23 22" stroke="white" strokeWidth="3" fill="none" strokeLinecap="round" strokeLinejoin="round" />
        <circle cx="16" cy="19" r="2.2" fill="white" />
      </svg>
      <span className={`font-bold tracking-tight ${big ? "text-2xl" : "text-lg"}`}>
        accel<span className="font-medium text-brand max-[389px]:hidden"> business</span>
      </span>
    </span>
  );
}

export function Header({ right }: { right?: React.ReactNode }) {
  const { lang, setLang } = useI18n();
  return (
    <header className="sticky top-0 z-20 flex items-center justify-between gap-2 border-b border-line bg-white/95 px-4 py-2 backdrop-blur">
      <Link href="/" className="min-h-[44px] inline-flex items-center">
        <Logo />
      </Link>
      <div className="flex items-center gap-2">
        {right}
        <label className="sr-only" htmlFor="lang-switch">
          Language
        </label>
        <select
          id="lang-switch"
          value={lang}
          onChange={(e) => setLang(e.target.value as Lang)}
          className="min-h-[44px] rounded-lg border border-line bg-white px-2 text-sm"
        >
          {LANGS.map((l) => (
            <option key={l.code} value={l.code}>
              {l.label}
            </option>
          ))}
        </select>
      </div>
    </header>
  );
}
