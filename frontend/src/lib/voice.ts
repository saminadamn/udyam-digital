/**
 * One voice interface for the advisor (DESIGN.md D1.1 Voice service, C3).
 * Server speech first when the API has a provider configured (Sarvam or Bhashini): listening records with MediaRecorder and sends
 * to POST /voice/transcribe; speaking plays POST /voice/speak. Without one, or if a call fails, the phone's Web Speech API is used.
 * Audio is never stored (D2.8).
 */
import { api } from "./api";
import { listen as browserListen, recognitionSupported, speak as browserSpeak, stopSpeaking as browserStop } from "./speech";

export type Engine = "browser" | "server";
export type Listening = { stop: () => void };
type Handlers = { onText: (text: string, final: boolean) => void; onBusy: (busy: boolean) => void; onDone: (error?: string) => void };

const MAX_MS = 30_000;
const SILENCE_MS = 1_200; // stop this long after the speaker goes quiet
const NO_SPEECH_MS = 7_000; // stop if nothing is said at all
const SPEECH_RMS = 0.02; // loudness that counts as speech
let serverCheck: Promise<boolean> | null = null;
let audioEl: HTMLAudioElement | null = null;
let speakSeq = 0; // only the newest reply plays; an older one still loading is dropped

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
  // Server speech (Sarvam/Bhashini) first when it's configured: it handles Indian languages better than most phones.
  if (canRecord() && (await serverVoice())) return "server";
  if (recognitionSupported()) return "browser";
  return null;
}

function recordToServer(lang: string, h: Handlers): Listening {
  let rec: MediaRecorder | null = null;
  let stream: MediaStream | null = null;
  let timer: ReturnType<typeof setTimeout> | null = null;
  let meter: ReturnType<typeof setInterval> | null = null;
  let ctx: AudioContext | null = null;
  let stopped = false;
  const chunks: Blob[] = [];
  const finish = () => {
    if (timer) clearTimeout(timer);
    if (meter) clearInterval(meter);
    ctx?.close().catch(() => {});
    stream?.getTracks().forEach((t) => t.stop());
  };
  // Tap once to talk: watch the microphone level and stop by itself when the speaker pauses.
  const watchSilence = (s: MediaStream, stopRec: () => void) => {
    try {
      ctx = new AudioContext();
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 1024;
      ctx.createMediaStreamSource(s).connect(analyser);
      const buf = new Float32Array(analyser.fftSize);
      const started = Date.now();
      let heard = false;
      let lastLoud = started;
      meter = setInterval(() => {
        analyser.getFloatTimeDomainData(buf);
        let sum = 0;
        for (const v of buf) sum += v * v;
        const now = Date.now();
        if (Math.sqrt(sum / buf.length) > SPEECH_RMS) {
          heard = true;
          lastLoud = now;
        }
        if ((heard && now - lastLoud > SILENCE_MS) || (!heard && now - started > NO_SPEECH_MS)) stopRec();
      }, 100);
    } catch {
      // no Web Audio: the user taps again to stop, or MAX_MS ends it
    }
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
      const stopRec = () => rec?.state === "recording" && rec.stop();
      timer = setTimeout(stopRec, MAX_MS);
      watchSilence(s, stopRec);
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
  const mine = ++speakSeq;
  if (await serverVoice()) {
    try {
      const blob = await api.speakAudio(text, lang);
      if (mine !== speakSeq) return;
      audioEl = new Audio(URL.createObjectURL(blob));
      await audioEl.play();
      return;
    } catch {}
  }
  if (mine === speakSeq) browserSpeak(text, lang);
}

export function stopSpeaking() {
  speakSeq++; // a reply still loading won't start playing (e.g. the owner tapped the mic)
  browserStop();
  try {
    audioEl?.pause();
  } catch {}
  audioEl = null;
}
