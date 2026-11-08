const CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ";
const PATTERN = /^\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]$/;

export const cleanGstin = (s: string) => s.toUpperCase().replace(/[^0-9A-Z]/g, "").slice(0, 15);

export function gstinState(g: string): "short" | "format" | "checksum" | "ok" {
  if (g.length < 15) return "short";
  if (!PATTERN.test(g)) return "format";
  let total = 0;
  for (let i = 0; i < 14; i++) {
    const v = CHARS.indexOf(g[i]) * (i % 2 ? 2 : 1);
    total += Math.floor(v / 36) + (v % 36);
  }
  return CHARS[(36 - (total % 36)) % 36] === g[14] ? "ok" : "checksum";
}

export const maskGstin = (g: string) => (g.length === 15 ? `${g.slice(0, 2)}${"•".repeat(9)}${g.slice(-3)}` : g);
