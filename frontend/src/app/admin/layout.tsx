"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Logo } from "@/components/Header";
import { api, auth, type User } from "@/lib/api";

const NAV = [
  { href: "/admin/leads", label: "Leads" },
  { href: "/admin/escalations", label: "Escalations" },
  { href: "/admin/notifications", label: "Outbox" },
  { href: "/admin/simulator", label: "Order simulator", admin: true },
];

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const path = usePathname();
  const [user, setUser] = useState<User | null>(null);

  useEffect(() => {
    const u = auth.user();
    if (!auth.token() || !u || u.role === "customer") {
      router.replace("/login");
      return;
    }
    setUser(u);
  }, [router]);

  if (!user) return null;
  return (
    <div className="flex min-h-dvh flex-col">
      <header className="sticky top-0 z-20 border-b border-line bg-white">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-6 gap-y-1 px-4 py-2">
          <Link href={user.role === "admin" ? "/admin/leads" : "/admin/escalations"} className="inline-flex min-h-[44px] items-center gap-2">
            <Logo />
            <span className="rounded bg-ink px-1.5 py-0.5 text-[11px] font-semibold uppercase tracking-wide text-white">Staff</span>
          </Link>
          <nav className="flex flex-wrap gap-1">
            {NAV.filter((n) => !n.admin || user.role === "admin").map((n) => (
              <Link
                key={n.href}
                href={n.href}
                className={`inline-flex min-h-[44px] items-center rounded-lg px-3 text-sm ${path?.startsWith(n.href) ? "bg-brand-soft font-semibold text-brand" : "text-ink-2 hover:text-ink"}`}
              >
                {n.label}
              </Link>
            ))}
          </nav>
          <div className="ml-auto flex items-center gap-3 text-sm text-ink-2">
            <span>
              {user.phone_masked} · {user.role}
            </span>
            <button
              type="button"
              className="btn-ghost"
              onClick={async () => {
                await api.logout().catch(() => {});
                auth.clear();
                router.replace("/login");
              }}
            >
              Sign out
            </button>
          </div>
        </div>
      </header>
      <div className="mx-auto w-full max-w-6xl flex-1 px-4 py-5">{children}</div>
    </div>
  );
}
