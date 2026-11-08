import { store } from "./store";

const BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000/api/v1";

export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string, public details: Record<string, unknown> = {}) {
    super(message);
  }
}

export type User = { id: string; role: string; language: string; phone_masked: string; whatsapp_opt_in: boolean };

export type Question = {
  role: "assistant" | "user";
  content: string;
  quick_replies?: string[];
  field?: string;
  multi_select?: boolean;
  done_label?: string;
};

export type Profile = {
  segment: string | null;
  employees: number | null;
  sites: number | null;
  city: string | null;
  city_tier: number | null;
  has_gstin: boolean | null;
  gst_status: string | null;
  gstin_masked: string | null;
  current_internet: string | null;
  needs: string[];
  complete: boolean;
  missing: string[];
};

export type Escalation = { id: string; agent_name: string | null; eta: string; message: string } | null;

export type MessageResponse = { message: Question; profile: Profile; status: string; failed_turns: number; escalation: Escalation; speak?: string };

export type BundleItem = { product_id: string; name: string; qty: number; role: "core" | "addon"; why: string; what_it_does: string; monthly_inr?: number };

export type PlanOptionKey = "essential" | "recommended" | "quick" | "grow" | "secure" | "complete";

export type PlanOption = {
  key: PlanOptionKey;
  recommended: boolean;
  recommendation_id: string;
  items: BundleItem[];
  addons: BundleItem[];
  monthly_total_inr: number;
  setup_total_inr: number;
  contract_months: number;
  max_install_days: number;
};

export type Recommendation = {
  options?: PlanOption[];
  recommendation_id: string;
  bundle_key: string;
  bundle_name: string;
  items: BundleItem[];
  addons: BundleItem[];
  blocked: { product_id: string; name: string; reasons: string[]; unlock: string }[];
  explanation: string;
  monthly_total_inr: number;
  setup_total_inr: number;
  contract_months: number;
  max_install_days: number;
};

export type QuoteItem = {
  product_id: string;
  name: string;
  qty: number;
  role: "core" | "addon";
  selected: boolean;
  unit_price_inr: number;
  line_monthly_inr: number;
  line_setup_inr: number;
  setup_fee_inr: number;
  locked: boolean;
  lock_reason: string | null;
  what_it_does: string;
  why: string;
  qty_editable: boolean;
  qty_min: number;
  qty_max: number;
  install_days: number;
  min_contract_months: number;
  requires_one_of: string[];
};

export type Quote = {
  quote_id: string;
  status: string;
  segment: string;
  items: QuoteItem[];
  monthly_total_inr: number;
  setup_total_inr: number;
  contract_months: number;
  max_install_days: number;
  live_in_days: number;
  pricing_rule: string;
  current_spend_inr: number | null;
  difference_inr: number | null;
  valid_until: string;
  assisted: boolean;
  order_id: string | null;
  order_display_id: string | null;
};

export type Accepted = { quote_id: string; status: string; order_id: string; display_id: string; state: string; next_step: string; assisted: boolean };

export type DocType = "gst_certificate" | "udyam_certificate" | "signatory_id" | "address_proof";
export const DOC_TYPES: DocType[] = ["gst_certificate", "udyam_certificate", "signatory_id", "address_proof"];

export type Notice = { notice_version: string; title: string; agree: string; sections: { key: string; heading: string; body: string }[]; retention_days: number };
export type ConsentOut = { consent_id: string; kyc_case_id: string; order_state: string };
export type OrderDetail = {
  order_id: string;
  display_id: string;
  state: string;
  kyc_case_id: string | null;
  consent_id: string | null;
  kyc_status: string | null;
  gstin_masked: string | null;
  items: { product_id: string; name: string }[];
};
export type GstinOut = {
  gstin_masked: string;
  legal_name: string;
  trade_name: string;
  state: string;
  status: string;
  effects: { removed_products: { product_id: string; name: string }[]; action: string | null };
};
export type InstantCheck = { check_code: string; result: "pass" | "fail"; severity: string | null; message: string };
export type UploadOut = {
  document_id: string;
  doc_type: DocType;
  version: number;
  quality: { sharpness: number; ocr_confidence: number; readable: boolean; skew_corrected_deg: number };
  extracted: Record<string, string | null>;
  instant_checks: InstantCheck[];
};
export type KycCheck = {
  check_code: string;
  result: "pass" | "fail";
  severity: string | null;
  message: string;
  doc_type: DocType | null;
  action: { type: "reupload" | "change_bundle" | "wait_for_call"; doc_type?: DocType } | null;
};
export type KycResult = {
  case_id: string;
  status: "open" | "submitted" | "flagged" | "review" | "verified" | "rejected";
  order_state: string;
  verdict: "verified" | "reupload" | "review" | "blocked" | null;
  consent_id: string;
  gstin_masked: string | null;
  documents: { document_id: string; doc_type: DocType; version: number; readable: boolean }[];
  checks: KycCheck[];
  fix: KycCheck[];
  escalation: { escalation_id: string; priority: string; agent_name: string | null; sla_due_at: string } | null;
  blocked_items: { product_id: string; name: string }[];
};

export type Step = { key: string; label: string; status: "done" | "current" | "upcoming"; at: string | null; expected: string | null; detail: string | null; late: boolean };
export type Human = { escalation_id: string; trigger: string; priority: string; agent_name: string | null; sla_due_at: string; message: string };
export type Tracker = {
  order_id: string;
  display_id: string;
  state: string;
  headline: string;
  pre_verification: boolean;
  steps: Step[];
  delayed: boolean;
  delay_message: string | null;
  escalation: Human | null;
  next_action: "consent" | "kyc" | null;
  as_of: string;
};
export type OrderRow = { order_id: string; display_id: string; state: string; created_at: string };

export const auth = {
  token: () => store.get("token"),
  set: (token: string, user: User) => {
    store.set("token", token);
    store.set("user", JSON.stringify(user));
  },
  user: (): User | null => {
    try {
      return JSON.parse(store.get("user") || "null");
    } catch {
      return null;
    }
  },
  clear: () => {
    store.remove("token");
    store.remove("user");
  },
};

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const form = typeof FormData !== "undefined" && body instanceof FormData;
  const headers: Record<string, string> = form ? {} : { "Content-Type": "application/json" };
  const token = auth.token();
  if (token) headers.Authorization = `Bearer ${token}`;
  let res: Response;
  try {
    res = await fetch(BASE + path, { method, headers, body: body === undefined ? undefined : form ? (body as FormData) : JSON.stringify(body) });
  } catch {
    throw new ApiError(0, "NETWORK", "network");
  }
  if (res.status === 204) return undefined as T;
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const e = data?.error ?? {};
    if (res.status === 401) auth.clear();
    throw new ApiError(res.status, e.code ?? "ERROR", e.message ?? "error", e.details ?? {});
  }
  return data as T;
}

async function requestBlob(path: string, body: unknown): Promise<Blob> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  const token = auth.token();
  if (token) headers.Authorization = `Bearer ${token}`;
  const res = await fetch(BASE + path, { method: "POST", headers, body: JSON.stringify(body) });
  if (!res.ok) {
    const e = (await res.json().catch(() => ({})))?.error ?? {};
    throw new ApiError(res.status, e.code ?? "ERROR", e.message ?? "error", e.details ?? {});
  }
  return res.blob();
}

export type Health = { status: string; providers: { llm: string; otp: string; ocr: string; messaging: string; voice?: string } };
export type NotificationRow = {
  id: string;
  channel: "whatsapp" | "in_app" | "sms";
  template: string;
  language: string;
  status: string;
  preview: string;
  order_id: string | null;
  display_id: string | null;
  created_at: string;
  sent_at: string | null;
  user_id?: string;
  to?: string | null;
  provider_ref?: string | null;
  error?: string | null;
  params?: Record<string, unknown>;
};

export const api = {
  health: () => request<Health>("GET", "/health"),
  transcribe: (audio: Blob, language: string) => {
    const f = new FormData();
    f.append("audio", audio, audio.type.includes("ogg") ? "speech.ogg" : "speech.webm");
    f.append("language", language);
    return request<{ text: string; confidence: number | null }>("POST", "/voice/transcribe", f);
  },
  speakAudio: (text: string, language: string) => requestBlob("/voice/speak", { text, language }),
  notifications: (params = "") => request<{ items: NotificationRow[]; provider?: string }>("GET", `/notifications${params}`),
  otpRequest: (phone: string) => request<{ request_id: string; expires_in: number; dev_code?: string }>("POST", "/auth/otp/request", { phone }),
  otpVerify: (request_id: string, code: string, language: string, whatsapp_opt_in: boolean) =>
    request<{ token: string; user: User }>("POST", "/auth/otp/verify", { request_id, code, language, whatsapp_opt_in }),
  logout: () => request<unknown>("POST", "/auth/logout", {}),
  patchMe: (body: { language?: string; whatsapp_opt_in?: boolean }) => request<{ user: User }>("PATCH", "/me", body),
  startConversation: (language: string, channel: "text" | "voice" = "text") =>
    request<{ conversation_id: string; message: Question; resumed: boolean; profile: Profile; speak?: string }>("POST", "/advisor/conversations", { language, channel }),
  sendMessage: (conversation_id: string, content: string, modality: "text" | "voice") =>
    request<MessageResponse>("POST", "/advisor/message", { conversation_id, content, modality }),
  getConversation: (id: string) =>
    request<{ conversation: { id: string; status: string; questions_asked: number; profile: Profile }; messages: { role: string; content: string }[]; next_question: Question | null }>(
      "GET",
      `/advisor/conversations/${id}`,
    ),
  recommend: (conversation_id: string) => request<Recommendation>("POST", "/advisor/recommend", { conversation_id }),
  createQuote: (recommendation_id: string) => request<Quote>("POST", "/quotes", { recommendation_id }),
  getQuote: (id: string) => request<Quote>("GET", `/quotes/${id}`),
  setSpend: (id: string, current_spend_inr: number) => request<Quote>("PATCH", `/quotes/${id}`, { current_spend_inr }),
  updateItem: (id: string, pid: string, body: { selected?: boolean; qty?: number }) => request<Quote>("PATCH", `/quotes/${id}/items/${pid}`, body),
  acceptQuote: (id: string) => request<Accepted>("POST", `/quotes/${id}/accept`),
  getOrder: (id: string) => request<OrderDetail>("GET", `/orders/${id}`),
  notice: (language: string) => request<Notice>("GET", `/consent/notice?purpose=kyc_verification&language=${language}`),
  giveConsent: (order_id: string, notice_version: string, language: string) =>
    request<ConsentOut>("POST", "/consent", { purpose: "kyc_verification", order_id, notice_version, granted: true, language }),
  withdrawConsent: (id: string) => request<{ withdrawn_at: string; documents_deleted: number }>("DELETE", `/consent/${id}`),
  lookupGstin: (gstin: string, order_id: string) => request<GstinOut>("GET", `/kyc/gstin/${gstin}?order_id=${order_id}`),
  lookupUdyam: (num: string, order_id: string) => request<{ udyam_masked: string; enterprise_name: string; city: string }>("GET", `/kyc/udyam/${num}?order_id=${order_id}`),
  upload: (case_id: string, doc_type: DocType, file: File, language: string) => {
    const f = new FormData();
    f.append("case_id", case_id);
    f.append("doc_type", doc_type);
    f.append("language", language);
    f.append("file", file);
    return request<UploadOut>("POST", "/kyc/upload", f);
  },
  submitKyc: (case_id: string) => request<{ status: string }>("POST", `/kyc/${case_id}/submit`, {}),
  kycResult: (case_id: string) => request<KycResult>("GET", `/kyc/${case_id}/result`),
  orders: () => request<{ orders: OrderRow[] }>("GET", "/orders"),
  tracker: (id: string, language: string) => request<Tracker>("GET", `/orders/${id}/tracker?language=${language}`),
  talkToPerson: (order_id: string, reason: string, preferred_time: string | null) =>
    request<Human & { agent: { name: string } | null }>("POST", "/escalations", { order_id, reason, preferred_time }),
  get: <T,>(path: string) => request<T>("GET", path),
  post: <T,>(path: string, body: unknown) => request<T>("POST", path, body),
  patch: <T,>(path: string, body: unknown) => request<T>("PATCH", path, body),
};

export function errorText(e: unknown, t: (k: string) => string): string {
  if (e instanceof ApiError) {
    if (e.code === "NETWORK") return t("errors.network");
    for (const q of [`quote.e_${e.code}`, `kyc.e_${e.code}`]) if (t(q) !== q) return t(q);
    const key = `errors.${e.code}`;
    const s = t(key);
    return s === key ? t("errors.generic") : s;
  }
  return t("errors.generic");
}
