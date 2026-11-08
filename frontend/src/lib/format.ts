export function rupees(n: number, lang: string): string {
  const locale = lang === "en" ? "en-IN" : `${lang}-IN`;
  try {
    return "₹" + new Intl.NumberFormat(locale, { maximumFractionDigits: 0, numberingSystem: "latn" } as Intl.NumberFormatOptions).format(n);
  } catch {
    return "₹" + n.toLocaleString("en-IN");
  }
}
