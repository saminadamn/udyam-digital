"use client";

import { useEffect, useRef, useState } from "react";
import { listen, listenEngine, type Engine, type Listening } from "@/lib/voice";

/** Tap to talk (C3): one tap starts listening, it stops by itself when the speaker pauses, and a second tap stops it early. */
export function MicButton({
  lang,
  disabled,
  labels,
  onTranscript,
  onFinal,
  onUnavailable,
  onBusy,
  onListening,
}: {
  lang: string;
  disabled?: boolean;
  labels: { idle: string; listening: string; transcribing: string };
  onTranscript: (text: string) => void;
  onFinal: (text: string) => void;
  onUnavailable: () => void;
  onBusy?: (busy: boolean) => void;
  onListening?: (on: boolean) => void;
}) {
  const [active, setActive] = useState(false);
  const [busy, setBusy] = useState(false);
  const [engine, setEngine] = useState<Engine | null | undefined>(undefined);
  const ref = useRef<Listening | null>(null);
  const lastRef = useRef("");

  useEffect(() => {
    let live = true;
    listenEngine().then((e) => live && setEngine(e));
    return () => {
      live = false;
      ref.current?.stop();
    };
  }, []);

  const start = () => {
    if (disabled || active || busy) return;
    if (!engine) {
      onUnavailable();
      return;
    }
    lastRef.current = "";
    setActive(true);
    onListening?.(true);
    ref.current = listen(engine, lang, {
      onText: (text, final) => {
        lastRef.current = text;
        onTranscript(text);
        if (final && engine === "server") onFinal(text.trim());
      },
      onBusy: (b) => {
        setBusy(b);
        onBusy?.(b);
      },
      onDone: (error) => {
        setActive(false);
        onListening?.(false);
        if (error && !["no-speech", "aborted"].includes(error)) onUnavailable();
        else if (engine === "browser" && lastRef.current.trim()) onFinal(lastRef.current.trim());
      },
    });
  };
  const stop = () => ref.current?.stop();
  const label = busy ? labels.transcribing : active ? labels.listening : labels.idle;

  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      data-engine={engine ?? "none"}
      data-state={busy ? "busy" : active ? "listening" : "idle"}
      disabled={disabled || busy}
      aria-pressed={active}
      onClick={() => (active ? stop() : start())}
      className={`flex h-12 w-12 shrink-0 items-center justify-center rounded-full border transition-colors disabled:opacity-40 ${
        active ? "animate-pulse border-brand bg-brand text-white" : "border-line bg-white text-brand"
      }`}
    >
      {busy ? (
        <span className="h-5 w-5 animate-spin rounded-full border-2 border-brand border-t-transparent" aria-hidden />
      ) : (
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
          <rect x="9" y="3" width="6" height="11" rx="3" />
          <path d="M5 11a7 7 0 0 0 14 0M12 18v3" strokeLinecap="round" />
        </svg>
      )}
    </button>
  );
}
