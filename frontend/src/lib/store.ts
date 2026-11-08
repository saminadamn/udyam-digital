const memory = new Map<string, string>();

function backend(kind: "local" | "session"): Storage | null {
  try {
    if (typeof window === "undefined") return null;
    const s = kind === "local" ? window.localStorage : window.sessionStorage;
    const probe = "__udyam_probe__";
    s.setItem(probe, "1");
    s.removeItem(probe);
    return s;
  } catch {
    return null;
  }
}

function make(kind: "local" | "session") {
  const prefix = `udyam:${kind}:`;
  return {
    get(key: string): string | null {
      try {
        const s = backend(kind);
        return s ? s.getItem(prefix + key) : memory.get(prefix + key) ?? null;
      } catch {
        return memory.get(prefix + key) ?? null;
      }
    },
    set(key: string, value: string) {
      try {
        const s = backend(kind);
        if (s) s.setItem(prefix + key, value);
        else memory.set(prefix + key, value);
      } catch {
        memory.set(prefix + key, value);
      }
    },
    remove(key: string) {
      try {
        backend(kind)?.removeItem(prefix + key);
      } catch {}
      memory.delete(prefix + key);
    },
  };
}

export const store = make("local");
export const session = make("session");
