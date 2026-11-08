import type { Metadata, Viewport } from "next";
import "./globals.css";
import { Shell } from "@/components/Shell";
import { I18nProvider } from "@/lib/i18n";

export const metadata: Metadata = {
  title: "Accel Business — Udyam Digital",
  description: "Find, buy and activate the right business connectivity plan in one sitting, in your language.",
};

export const viewport: Viewport = { width: "device-width", initialScale: 1, themeColor: "#c8102e" };

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="hi">
      <body className="min-h-dvh antialiased">
        <I18nProvider>
          <Shell>{children}</Shell>
        </I18nProvider>
      </body>
    </html>
  );
}
