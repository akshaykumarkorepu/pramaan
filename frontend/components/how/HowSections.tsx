import Link from "next/link";
import { ArrowRight, BadgeCheck, Calculator, EyeOff, ExternalLink, FileWarning, Quote, RefreshCcw, type LucideIcon } from "lucide-react";
import { Stagger, StaggerItem } from "@/components/motion/Stagger";
import { FadeIn } from "@/components/motion/FadeIn";
import { buttonVariants } from "@/components/ui/button";
import { SOURCE_STYLE } from "@/components/status";
import { ProofStatsCard } from "@/components/ProofStats";
import { cn } from "@/lib/utils";

/** Section wrapper with a heading that fades in on scroll. */
export function Section({ id, title, intro, children }: { id?: string; title: string; intro?: string; children: React.ReactNode }) {
  return (
    <section id={id} className="mx-auto w-full max-w-[1100px] px-4 py-10 sm:px-6 sm:py-14">
      <FadeIn inView>
        <h2 className="text-2xl font-bold text-slate-900 sm:text-3xl">{title}</h2>
        {intro && <p className="mt-2 max-w-2xl text-slate-600">{intro}</p>}
      </FadeIn>
      <div className="mt-8">{children}</div>
    </section>
  );
}

const GUARDS: { icon: LucideIcon; title: string; text: string }[] = [
  { icon: Quote, title: "Exact quotes required", text: "Every duty the AI reports must carry a word-for-word quote from the notice." },
  { icon: Calculator, title: "Code checks the proof", text: "Plain code, not AI, looks for the quote, and for every date and number, in the source text." },
  { icon: EyeOff, title: "Rejected items are shown", text: "Anything that fails the check stays on screen, marked rejected, with the reason. Nothing is hidden." },
  { icon: BadgeCheck, title: "Explainer sees verified only", text: "The Telugu, Hindi and English explanation is written from verified duties, never from the raw document." },
  { icon: RefreshCcw, title: "One self-correction pass", text: "Rejected items get a single retry. If they still fail, they stay rejected. Never more." },
];

export function Guardrails() {
  return (
    <Stagger inView className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {GUARDS.map((g) => (
        <StaggerItem key={g.title} lift>
          <div className="h-full rounded-2xl border border-slate-200 bg-white p-5 shadow-soft">
            <span className="flex size-10 items-center justify-center rounded-xl bg-verified-soft text-verified">
              <g.icon className="size-5" aria-hidden />
            </span>
            <h3 className="mt-4 text-base font-semibold text-slate-900">{g.title}</h3>
            <p className="mt-1 text-sm leading-relaxed text-slate-600">{g.text}</p>
          </div>
        </StaggerItem>
      ))}
    </Stagger>
  );
}

const FEEDS = [
  { id: "rbi", name: "Reserve Bank of India", feed: "https://www.rbi.org.in/notifications_rss.xml", label: "RBI notifications feed" },
  { id: "sebi", name: "Securities and Exchange Board of India", feed: "https://www.sebi.gov.in/sebirss.xml", label: "SEBI feed (circulars only)" },
  { id: "pib", name: "Press Information Bureau", feed: "https://www.pib.gov.in/RssMain.aspx?ModId=6&Lang=1&Regid=3&reg=3", label: "PIB English feed" },
] as const;

export function Sources() {
  return (
    <>
      <Stagger inView className="grid gap-4 md:grid-cols-3">
        {FEEDS.map((f) => (
          <StaggerItem key={f.id}>
            <div className="h-full rounded-2xl border border-slate-200 bg-white p-5 shadow-soft">
              <span className={cn("rounded-full border px-2 py-0.5 text-xs font-semibold", SOURCE_STYLE[f.id].badge)}>{SOURCE_STYLE[f.id].label}</span>
              <p className="mt-3 text-sm font-semibold text-slate-900">{f.name}</p>
              <a
                href={f.feed}
                target="_blank"
                rel="noopener noreferrer"
                className="mt-2 inline-flex items-center gap-1 text-[13px] font-medium text-brand hover:underline"
              >
                {f.label} <ExternalLink className="size-3" aria-hidden />
              </a>
            </div>
          </StaggerItem>
        ))}
      </Stagger>
      <p className="mt-4 text-sm text-slate-500">Fetched at the moment you ask, never stored.</p>
    </>
  );
}

const BUILT_WITH = ["FastAPI", "Groq (gpt-oss-120b / 20b)", "Next.js", "rapidfuzz", "pdfplumber", "Render", "Vercel"];

export function BuiltWith() {
  return (
    <ul className="flex flex-wrap gap-2">
      {BUILT_WITH.map((b) => (
        <li key={b} className="rounded-full border border-slate-200 bg-white px-3 py-1 text-[13px] font-medium text-slate-700 shadow-sm">
          {b}
        </li>
      ))}
    </ul>
  );
}

/** Placeholder only: no figures until the live evaluation endpoint is wired in a later milestone. */
export function Evidence() {
  return <ProofStatsCard />;
}

const LIMITS = [
  "English source documents only.",
  "Covers RBI, SEBI and PIB only.",
  "The free-tier AI can be slow on the first analysis.",
  "Always confirm with the original document.",
];

export function Limits() {
  return (
    <ul className="grid gap-3 sm:grid-cols-2">
      {LIMITS.map((l) => (
        <li key={l} className="flex items-start gap-3 rounded-xl border border-review/25 bg-review-soft/60 p-4 text-sm text-slate-700">
          <FileWarning className="mt-0.5 size-4 shrink-0 text-review" aria-hidden />
          {l}
        </li>
      ))}
    </ul>
  );
}

export function Team() {
  return (
    <FadeIn inView>
      <p className="text-lg font-semibold text-slate-900">Team CTRL + AI</p>
      <p className="mt-1 text-slate-600">Akshay Kumar Korepu &amp; Ragula Thirumal, NIT Warangal</p>
    </FadeIn>
  );
}

export function HowCta() {
  return (
    <FadeIn inView>
      <div className="flex flex-col gap-3 sm:flex-row">
        <Link href="/#check" className={cn(buttonVariants({ size: "lg" }), "h-11 gap-2 bg-gradient-accent px-6 text-base text-white shadow-lg shadow-indigo-900/20")}>
          Check new rules <ArrowRight aria-hidden />
        </Link>
        <a
          href="https://github.com/akshaykumarkorepu/pramaan"
          target="_blank"
          rel="noopener noreferrer"
          className={cn(buttonVariants({ variant: "outline", size: "lg" }), "h-11 gap-2 bg-white px-6 text-base")}
        >
          GitHub <ExternalLink aria-hidden />
        </a>
      </div>
    </FadeIn>
  );
}
