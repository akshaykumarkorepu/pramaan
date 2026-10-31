import type { Metadata, Viewport } from "next";
import { Inter, Noto_Sans_Devanagari, Noto_Sans_Telugu } from "next/font/google";
import "./globals.css";
import { Footer } from "@/components/Footer";
import { Header } from "@/components/Header";
import { Toaster } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";

const inter = Inter({ variable: "--font-inter", subsets: ["latin"], display: "swap" });
// Indic fonts load their own subset; they are only used where <LangText> asks for them
const notoTelugu = Noto_Sans_Telugu({ variable: "--font-noto-telugu", subsets: ["telugu"], display: "swap" });
const notoDeva = Noto_Sans_Devanagari({ variable: "--font-noto-deva", subsets: ["devanagari"], display: "swap" });

export const metadata: Metadata = {
  title: "Pramaan — New rules, explained in your language",
  description:
    "Pramaan reads live RBI, SEBI and PIB notices, tells you what applies to you, and verifies every claim against the source.",
};

export const viewport: Viewport = { themeColor: "#3730a3" };

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${inter.variable} ${notoTelugu.variable} ${notoDeva.variable} h-full`}>
      <body className="flex min-h-full flex-col">
        <TooltipProvider>
          <Header />
          <main className="flex-1">{children}</main>
          <Footer />
        </TooltipProvider>
        <Toaster />
      </body>
    </html>
  );
}
