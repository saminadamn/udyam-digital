"use client";

import { usePathname } from "next/navigation";

export function Shell({ children }: { children: React.ReactNode }) {
  const staff = usePathname()?.startsWith("/admin");
  return <div className={`mx-auto flex min-h-dvh w-full flex-col bg-canvas ${staff ? "" : "max-w-[480px]"}`}>{children}</div>;
}
