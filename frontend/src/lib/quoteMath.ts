import type { Quote, QuoteItem } from "./api";

const LINKS = new Set(["P01", "P02", "P03", "P04", "P05", "P06"]);

export function applyLocal(q: Quote, pid: string, change: { selected?: boolean; qty?: number }): Quote {
  const items: QuoteItem[] = q.items.map((i) => {
    if (i.product_id !== pid) return i;
    const qty = change.qty ?? i.qty;
    return { ...i, selected: change.selected ?? i.selected, qty, line_monthly_inr: i.unit_price_inr * qty, line_setup_inr: i.setup_fee_inr * qty };
  });
  const sel = items.filter((i) => i.selected);
  const monthly = sel.reduce((a, i) => a + i.line_monthly_inr, 0);
  return {
    ...q,
    items,
    monthly_total_inr: monthly,
    setup_total_inr: sel.reduce((a, i) => a + i.line_setup_inr, 0),
    contract_months: Math.max(0, ...sel.map((i) => i.min_contract_months)),
    max_install_days: Math.max(0, ...sel.map((i) => i.install_days)),
    live_in_days: Math.max(0, ...sel.map((i) => i.install_days)) + 1,
    difference_inr: q.current_spend_inr == null ? null : monthly - q.current_spend_inr,
  };
}

export function localBlockReason(q: Quote, pid: string): string | null {
  const item = q.items.find((i) => i.product_id === pid);
  return item && item.selected && item.locked ? item.lock_reason : null;
}

export function addWouldBreak(q: Quote, pid: string): boolean {
  const item = q.items.find((i) => i.product_id === pid);
  if (!item || !item.requires_one_of.length) return false;
  const sel = new Set(q.items.filter((i) => i.selected).map((i) => i.product_id));
  return !item.requires_one_of.some((p) => sel.has(p));
}

export const isLink = (pid: string) => LINKS.has(pid);
