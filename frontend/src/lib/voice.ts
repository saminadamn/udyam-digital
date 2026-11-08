/**
 * One voice interface for the advisor (DESIGN.md D1.1 Voice service, C3).
 * Listening: the phone's Web Speech API first; if the browser has none, record with MediaRecorder and send to POST /voice/transcribe
 * (Sarvam or Bhashini on the server). Speaking: the phone's voice when it has one for the language, otherwise POST /voice/speak.
 * Audio is never stored (D2.8).
 */
import { api } from "./api";
import { hasVoiceFor, listen as browserListen, recognitionSupported, speak as browserSpeak, stopSpeaking as browserStop, synthesisSupported } from "./speech";

export type Engine = "browser" | "server";
export type Listening = { stop: () => void };
type Handlers = { onText: (text: string, final: boolean) => void; onBusy: (busy: boolean) => void; onDone: (error?: string) => void };

const MAX_MS = 30_000;
let serverCheck: Promise<boolean> | null = null;
let audioEl: HTMLAudioElement | null = null;

export function serverVoice(): Promise<boolean> {
  if (!serverCheck) {
    serverCheck = api
      .health()
      .then((h) => ["sarvam", "bhashini"].includes(h.providers.voice ?? ""))
      .catch(() => false);
  }
  return serverCheck;
}

function canRecord(): boolean {
  return typeof window !== "undefined" && "MediaRecorder" in window && !!navigator.mediaDevices?.getUserMedia;
}

export async function listenEngine(): Promise<Engine | null> {
  if (recognitionSupported()) return "browser";
  if (canRecord() && (await serverVoice())) return "server";
  return null;
}

function recordToServer(lang: string, h: Handlers): Listening {
  let rec: MediaRecorder | null = null;
  let stream: MediaStream | null = null;
  let timer: ReturnType<typeof setTimeout> | null = null;
  let stopped = false;
  const chunks: Blob[] = [];
  const finish = () => {
    if (timer) clearTimeout(timer);
    stream?.getTracks().forEach((t) => t.stop());
  };
  navigator.mediaDevices
    .getUserMedia({ audio: true })
    .then((s) => {
      stream = s;
      if (stopped) return finish();
      const type = ["audio/webm;codecs=opus", "audio/ogg;codecs=opus", "audio/webm"].find((t) => MediaRecorder.isTypeSupported?.(t));
      rec = new MediaRecorder(s, type ? { mimeType: type } : undefined);
      rec.ondataavailable = (e) => e.data.size && chunks.push(e.data);
      rec.onstop = async () => {
        finish();
        const blob = new Blob(chunks, { type: rec?.mimeType || "audio/webm" });
        if (!blob.size) return h.onDone("no-speech");
        h.onBusy(true);
        try {
          const r = await api.transcribe(blob, lang);
          if (r.text.trim()) h.onText(r.text.trim(), true);
          h.onDone(r.text.trim() ? undefined : "no-speech");
        } catch {
          h.onDone("unavailable");
        } finally {
          h.onBusy(false);
        }
      };
      rec.start();
      timer = setTimeout(() => rec?.state === "recording" && rec.stop(), MAX_MS);
    })
    .catch(() => {
      finish();
      h.onDone("not-allowed");
    });
  return {
    stop: () => {
      stopped = true;
      if (rec?.state === "recording") rec.stop();
    },
  };
}

export function listen(engine: Engine, lang: string, h: Handlers): Listening {
  stopSpeaking();
  if (engine === "server") return recordToServer(lang, h);
  return { stop: browserListen(lang, h.onText, h.onDone) };
}

/** Read a reply aloud. `text` should already be the short spoken version from the API. */
export async function speak(text: string, lang: string): Promise<void> {
  if (!text) return;
  stopSpeaking();
  if (synthesisSupported() && hasVoiceFor(lang)) return browserSpeak(text, lang);
  if (await serverVoice()) {
    try {
      const blob = await api.speakAudio(text, lang);
      audioEl = new Audio(URL.createObjectURL(blob));
      await audioEl.play();
      return;
    } catch {}
  }
  browserSpeak(text, lang);
}

export function stopSpeaking() {
  browserStop();
  try {
    audioEl?.pause();
  } catch {}
  audioEl = null;
}
