const LOCALE: Record<string, string> = { hi: "hi-IN", en: "en-IN", mr: "mr-IN", ta: "ta-IN", bn: "bn-IN", kn: "kn-IN", gu: "gu-IN", te: "te-IN" };

type Recognition = {
  lang: string;
  interimResults: boolean;
  continuous: boolean;
  onresult: ((e: { results: ArrayLike<ArrayLike<{ transcript: string }> & { isFinal: boolean }> }) => void) | null;
  onerror: ((e: { error: string }) => void) | null;
  onend: (() => void) | null;
  start: () => void;
  stop: () => void;
};

export function recognitionSupported(): boolean {
  if (typeof window === "undefined") return false;
  const w = window as unknown as Record<string, unknown>;
  return Boolean(w.SpeechRecognition || w.webkitSpeechRecognition);
}

export function listen(lang: string, onText: (text: string, final: boolean) => void, onDone: (error?: string) => void): () => void {
  const w = window as unknown as Record<string, new () => Recognition>;
  const Ctor = w.SpeechRecognition || w.webkitSpeechRecognition;
  if (!Ctor) {
    onDone("unsupported");
    return () => {};
  }
  const rec = new Ctor();
  rec.lang = LOCALE[lang] ?? "hi-IN";
  rec.interimResults = true;
  rec.continuous = false;
  let failed: string | undefined;
  rec.onresult = (e) => {
    let text = "";
    let final = false;
    for (let i = 0; i < e.results.length; i++) {
      text += e.results[i][0].transcript;
      final = final || e.results[i].isFinal;
    }
    onText(text, final);
  };
  rec.onerror = (e) => {
    failed = e.error;
  };
  rec.onend = () => onDone(failed);
  try {
    rec.start();
  } catch {
    onDone("start_failed");
  }
  return () => {
    try {
      rec.stop();
    } catch {}
  };
}

export function speak(text: string, lang: string) {
  try {
    if (typeof window === "undefined" || !("speechSynthesis" in window)) return;
    window.speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(text);
    u.lang = LOCALE[lang] ?? "hi-IN";
    u.rate = 0.95;
    window.speechSynthesis.speak(u);
  } catch {}
}

export function stopSpeaking() {
  try {
    window.speechSynthesis?.cancel();
  } catch {}
}

/** True when the phone has a voice installed for this language. Unknown (voices not loaded yet) counts as yes. */
export function hasVoiceFor(lang: string): boolean {
  try {
    if (typeof window === "undefined" || !("speechSynthesis" in window)) return false;
    const voices = window.speechSynthesis.getVoices();
    if (!voices.length) return true;
    const want = (LOCALE[lang] ?? "hi-IN").toLowerCase();
    return voices.some((v) => v.lang.toLowerCase().replace("_", "-") === want || v.lang.toLowerCase().startsWith(want.slice(0, 2) + "-"));
  } catch {
    return false;
  }
}

export function synthesisSupported(): boolean {
  return typeof window !== "undefined" && "speechSynthesis" in window;
}
