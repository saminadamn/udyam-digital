"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { auth } from "@/lib/api";

/** Admins land on the leads dashboard (A2); agents on their escalation queue (A4). */
export default function AdminHome() {
  const router = useRouter();
  useEffect(() => router.replace(auth.user()?.role === "admin" ? "/admin/leads" : "/admin/escalations"), [router]);
  return null;
}
