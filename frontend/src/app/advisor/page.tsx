"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { ChatBubble, HumanBanner, QuickReplies, TypingBubble } from "@/components/Chat";
import { Header } from "@/components/Header";
import { MicButton } from "@/components/MicButton";
import { api, auth, errorText, type Escalation, type Profile, type Question } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { speak, stopSpeaking } from "@/lib/voice";
import { session } from "@/lib/store";

type Line = { role: "assistant" | "user"; content: string; speak?: string };
const maskIds = (s: string) =>
  s.replace(/\b(\d{2})[A-Z]{5}\d{4}[A-Z][0-9A-Z]Z([0-9A-Z])\b/gi, (m) => `${m.slice(0, 2)}${"•".repeat(10)}${m.slice(-3)}`);
const TOTAL = 6;

export default function AdvisorPage() {
  const { t, lang, ready } = useI18n();
  const router = useRouter();
  const [cid, setCid] = useState<string | null>(null);
  const [convLang, setConvLang] = useState<string | null>(null);
  const [lines, setLines] = useState<Line[]>([]);
  const [question, setQuestion] = useState<Question | null>(null);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [status, setStatus] = useState("active");
  const [escalation, setEscalation] = useState<Escalation>(null);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [readAloud, setReadAloud] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);

  const say = useCallback((text: string) => speak(text, convLang || lang), [convLang, lang]);

  const begin = useCallback(async (language: string) => {
    setBusy(true);
    setError(null);
    try {
      const r = await api.startConversation(language);
      session.set("conv", r.conversation_id);
      setCid(r.conversation_id);
      setConvLang(language);
      setProfile(r.profile);
      if (r.resumed) {
        const full = await api.getConversation(r.conversation_id);
        setLines(full.messages.filter((m) => m.role === "user" || m.role === "assistant") as Line[]);
        setQuestion(full.next_question);
        setStatus(full.conversation.status);
      } else {
        setLines([{ role: "assistant", content: r.message.content, speak: r.speak }]);
        setQuestion(r.message);
        setStatus("active");
      }
      setEscalation(null);
    } catch (e) {
      setError(errorText(e, t));
      if (!auth.token()) router.replace("/login");
    } finally {
      setBusy(false);
    }
  }, [router, t]);

  useEffect(() => {
    if (!ready) return;
    if (!auth.token()) {
      router.replace("/login");
      return;
    }
    if (!cid) begin(lang);
  }, [ready, cid, lang, begin, router]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [lines, question, busy, escalation]);

  useEffect(() => () => stopSpeaking(), []);

  const send = async (content: string, modality: "text" | "voice" = "text") => {
    if (!cid || !content.trim() || busy) return;
    setLines((l) => [...l, { role: "user", content: maskIds(content) }]);
    setInput("");
    setQuestion((q) => (q ? { ...q, quick_replies: [] } : q));
    setBusy(true);
    setError(null);
    try {
      const r = await api.sendMessage(cid, content, modality);
      setLines((l) => [...l, { role: "assistant", content: r.message.content, speak: r.speak }]);
      setQuestion(r.message);
      setProfile(r.profile);
      setStatus(r.status);
      if (r.escalation) setEscalation(r.escalation);
      // Spoken answers get spoken replies, kept short by the API (`speak`); the screen shows the full text.
      if (modality === "voice" && !readAloud) setReadAloud(true);
      if (modality === "voice" || readAloud) say(r.speak || r.message.content);
    } catch (e) {
      setError(errorText(e, t));
    } finally {
      setBusy(false);
    }
  };

  const seePlan = async () => {
    if (!cid) return;
    setBusy(true);
    setError(null);
    try {
      const rec = await api.recommend(cid);
      session.set(`rec:${cid}`, JSON.stringify(rec));
      session.remove("conv");
      router.push(`/advisor/recommendation?c=${encodeURIComponent(cid)}`);
    } catch (e) {
      setError(errorText(e, t));
    } finally {
      setBusy(false);
    }
  };

  const restart = () => {
    session.remove("conv");
    setCid(null);
    setLines([]);
    setQuestion(null);
    begin(lang);
  };

  const answered = profile ? TOTAL - profile.missing.length : 0;
  const done = status === "ready_to_recommend";
  const escalated = status === "escalated" || Boolean(escalation);

  return (
    <>
      <Header
        right={
          <button className="btn-ghost text-xs" onClick={() => send(t("chat.talk_person"))} disabled={busy || escalated || !cid}>
            {t("chat.talk_person")}
          </button>
        }
      />
      <div className="flex items-center justify-between border-b border-line bg-white px-4 py-2 text-xs text-ink-2">
        <span>{t("chat.title")}</span>
        <div className="flex items-center gap-3">
          <span aria-live="polite">{t("chat.progress", { n: Math.min(TOTAL, answered + (done ? 0 : 1)), total: TOTAL })}</span>
          <div className="flex gap-1" aria-hidden>
            {Array.from({ length: TOTAL }).map((_, i) => (
              <span key={i} className={`h-1.5 w-4 rounded-full ${i < answered ? "bg-brand" : "bg-line"}`} />
            ))}
          </div>
        </div>
      </div>

      <main className="flex flex-1 flex-col gap-3 overflow-y-auto px-4 py-4" aria-live="polite">
        {lines.map((l, i) => (
          <ChatBubble
            key={i}
            role={l.role}
            onPlay={l.role === "assistant" && i === lines.length - 1 ? () => say(l.speak || l.content) : undefined}
            playLabel={t("chat.play")}
          >
            {l.content}
          </ChatBubble>
        ))}
        {busy && <TypingBubble label={t("chat.thinking")} />}
        {escalated && <HumanBanner message={escalation?.message || t("chat.agent_banner")} />}
        {!busy && !done && !escalated && question?.quick_replies && (
          <QuickReplies
            key={`${question.field}-${lines.length}`}
            options={question.quick_replies}
            multi={question.multi_select}
            doneLabel={question.done_label || t("chat.done")}
            disabled={busy}
            onPick={(v) => send(v)}
          />
        )}
        {done && (
          <button className="btn-primary" onClick={seePlan} disabled={busy}>
            {t("chat.see_plan")}
          </button>
        )}
        {error && (
          <p className="rounded-xl bg-brand-soft px-4 py-3 text-sm text-brand-dark" role="alert">
            {error}
          </p>
        )}
        <div ref={endRef} />
      </main>

      <footer className="sticky bottom-0 border-t border-line bg-white px-3 py-2">
        <div className="mb-1 flex items-center justify-between">
          <label className="flex min-h-[44px] items-center gap-2 text-xs text-ink-2">
            <input type="checkbox" className="accent-[var(--color-brand)]" checked={readAloud} onChange={(e) => setReadAloud(e.target.checked)} />
            {t("chat.read_aloud")}
          </label>
          {(done || escalated) && (
            <button className="text-xs font-medium text-brand" onClick={restart}>
              {t("rec.restart")}
            </button>
          )}
        </div>
        <form
          className="flex items-center gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            send(input);
          }}
        >
          <MicButton
            lang={convLang || lang}
            disabled={busy || done || escalated}
            labels={{ idle: t("chat.mic"), listening: t("chat.listening"), transcribing: t("chat.transcribing") }}
            onTranscript={setInput}
            onFinal={(text) => send(text, "voice")}
            onUnavailable={() => setError(t("chat.mic_denied"))}
          />
          <input
            className="field"
            placeholder={t("chat.placeholder")}
            value={input}
            disabled={busy || done || escalated}
            onChange={(e) => setInput(e.target.value)}
            aria-label={t("chat.placeholder")}
          />
          <button className="h-12 shrink-0 rounded-xl bg-brand px-4 font-semibold text-white disabled:opacity-40" disabled={busy || !input.trim()}>
            {t("chat.send")}
          </button>
        </form>
      </footer>
    </>
  );
}
