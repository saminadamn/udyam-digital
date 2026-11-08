export type QueueItem = {
  escalation_id: string;
  trigger: string;
  priority: string;
  status: string;
  business: string | null;
  segment: string | null;
  city: string | null;
  reason: string;
  language: string | null;
  order_id: string | null;
  order_display_id: string | null;
  order_state: string | null;
  age_minutes: number;
  sla_due_at: string | null;
  breached: boolean;
  agent: string | null;
  agent_id: string | null;
};
export type Queue = { items: QueueItem[]; counts: { open: number; assigned: number; breached: number } };
export type Agent = { id: string; name: string; languages: string[]; skills: string[]; open_cases: number; max_open: number };

export const TRIGGER: Record<string, string> = {
  sla_breach: "Late order",
  kyc_flag: "KYC flag",
  advisor_failed: "Advisor stuck",
  user_request: "Asked for a person",
  assisted_deal: "Assisted deal",
};
export const RESOLUTION: Record<string, string> = {
  approved: "Approve documents",
  ask_fix: "Ask customer to fix",
  rejected: "Reject",
  rebooked: "Rebook install (tomorrow)",
  installed: "Mark installed",
  went_live: "Mark live",
  contacted: "Called, sorted",
  no_answer: "No answer",
  quoted: "Sent a quote",
  survey_booked: "Site survey booked",
};
export const LANG_NAME: Record<string, string> = { hi: "Hindi", en: "English", mr: "Marathi", ta: "Tamil", bn: "Bengali", kn: "Kannada", gu: "Gujarati", te: "Telugu" };

export function countdown(iso: string | null, now = Date.now()) {
  if (!iso) return { text: "—", late: false };
  const mins = Math.round((new Date(iso).getTime() - now) / 60000);
  const a = Math.abs(mins);
  const s = a >= 1440 ? `${Math.floor(a / 1440)}d ${Math.floor((a % 1440) / 60)}h` : a >= 60 ? `${Math.floor(a / 60)}h ${a % 60}m` : `${a}m`;
  return { text: mins < 0 ? `${s} over` : `${s} left`, late: mins < 0 };
}

export function stamp(iso: string | null) {
  return iso ? new Date(iso).toLocaleString("en-IN", { day: "numeric", month: "short", hour: "numeric", minute: "2-digit" }) : "—";
}

export type Propensity = { score: number; bucket: "High" | "Medium" | "Low"; bucket_conversion_pct: number | null; reasons: string[] } | null;
export type LeadRow = {
  lead_id: string;
  origin: "import" | "app";
  business_name: string;
  contact: string | null;
  segment: string | null;
  city: string | null;
  lead_source: string | null;
  created_date: string | null;
  stage_reached: string;
  outcome: string | null;
  drop_reason: string | null;
  advisor_outcome: string;
  lead_status: string;
  propensity: Propensity;
  last_contacted_at: string | null;
  last_call: { call_id: string; outcome: string | null; at: string; agent: string | null } | null;
};
export type LeadList = {
  items: LeadRow[];
  total: number;
  page: number;
  page_size: number;
  counts: { all: number; not_closed: number; hot_uncontacted: number; app: number };
  bucket_conversion_pct: Record<string, number>;
};
export type Metric = {
  key: string;
  label: string;
  baseline: number | null;
  target: number;
  current: number | null;
  unit: "pct" | "days" | "inr" | "num" | "hours";
  better: "higher" | "lower";
  note: string;
  strip: boolean;
};
export type Metrics = { metrics: Metric[]; baseline_period: string; app_leads: number; app_orders: number };
export type CallStart = { call_id: string; status: "ringing" | "logged"; provider: string; notice: string | null; lead_id: string };

export const SEGMENTS = ["Micro retail & services", "Professional offices", "Small multi-site businesses", "Small manufacturers"];
export const SOURCES = ["Field sales", "Channel partner", "Website form", "Inbound call", "Referral", "WhatsApp campaign", "App"];
export const CALL_OUTCOMES: Record<string, string> = {
  connected: "Connected",
  no_answer: "No answer",
  callback_requested: "Call back later",
  interested: "Interested",
  converted: "Converted",
  not_interested: "Not interested",
};
export const ADVISOR_OUTCOME: Record<string, string> = {
  not_started: "In advisor",
  abandoned: "Left the advisor",
  escalated: "Handed to a person",
  quoted: "Quoted",
  ordered: "Ordered",
};

export function fmtMetric(v: number | null, unit: Metric["unit"]) {
  if (v === null || v === undefined) return "—";
  if (unit === "pct") return `${(v * 100).toFixed(1)}%`;
  if (unit === "inr") return `Rs ${Math.round(v).toLocaleString("en-IN")}`;
  if (unit === "days") return `${v.toFixed(1)} d`;
  if (unit === "hours") return `${v.toFixed(1)} h`;
  return v.toFixed(2).replace(/\.?0+$/, "") || "0";
}

/** green: on or past target; amber: better than baseline; red: worse than baseline; grey: no data yet. */
export function metricTone(m: Metric): "ok" | "mid" | "bad" | "none" {
  if (m.current === null) return "none";
  const beats = (a: number, b: number) => (m.better === "higher" ? a >= b : a <= b);
  if (beats(m.current, m.target)) return "ok";
  if (m.baseline === null || beats(m.current, m.baseline)) return "mid";
  return "bad";
}
