"use client";

import Link from "next/link";
import { motion, useReducedMotion } from "motion/react";
import { ArrowRight, BadgeCheck, Languages, Radio } from "lucide-react";
import { Button, buttonVariants } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { FadeIn } from "@/components/motion/FadeIn";
import { LangText } from "@/components/LangText";
import { cn } from "@/lib/utils";

function Chip({ icon, children }: { icon: React.ReactNode; children: React.ReactNode }) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border border-slate-200 bg-white/80 px-3 py-1 text-[13px] font-medium text-slate-700 shadow-sm">
      {icon}
      {children}
    </span>
  );
}

export function Hero() {
  const reduce = useReducedMotion();
  return (
    <section className="relative isolate overflow-hidden">
      <div className="bg-dots absolute inset-0 -z-20" aria-hidden />
      {/* soft animated glow behind the headline */}
      <div aria-hidden className="absolute left-1/2 top-4 -z-10 w-[min(720px,90vw)] -translate-x-1/2">
        <motion.div
          className="h-72 w-full rounded-full bg-gradient-accent blur-3xl"
          initial={{ opacity: 0.18 }}
          animate={reduce ? undefined : { scale: [1, 1.08, 1], opacity: [0.14, 0.26, 0.14] }}
          transition={{ duration: 10, repeat: Infinity, ease: "easeInOut" }}
        />
      </div>

      <div className="mx-auto max-w-[1100px] px-4 pb-14 pt-16 text-center sm:px-6 sm:pt-24">
        <FadeIn>
          <h1 className="mx-auto max-w-3xl text-balance text-4xl font-bold leading-[1.1] text-slate-900 sm:text-5xl md:text-6xl">
            New rules, explained in <span className="text-gradient-accent">your language</span> — every line proved.
          </h1>
        </FadeIn>
        <FadeIn delay={0.12}>
          <p className="mx-auto mt-6 max-w-2xl text-pretty text-base leading-relaxed text-slate-600 sm:text-lg">
            Pramaan reads live RBI, SEBI and PIB notices, tells you what applies to you, and verifies every claim against
            the source.
          </p>
        </FadeIn>
        <FadeIn delay={0.24}>
          <div className="mt-6 flex flex-wrap items-center justify-center gap-2">
            <Chip icon={<Radio className="size-3.5 text-verified" aria-hidden />}>Live official sources</Chip>
            <Chip icon={<BadgeCheck className="size-3.5 text-brand" aria-hidden />}>Every quote verified</Chip>
            <Chip icon={<Languages className="size-3.5 text-slate-500" aria-hidden />}>
              <LangText lang="te">తెలుగు</LangText> · <LangText lang="hi">हिंदी</LangText> · English
            </Chip>
          </div>
        </FadeIn>
        <FadeIn delay={0.36}>
          <div className="mt-9 flex flex-col items-center justify-center gap-3 sm:flex-row">
            <Tooltip>
              {/* a disabled button swallows hover, so the tooltip hangs off a focusable wrapper */}
              <TooltipTrigger render={<span tabIndex={0} className="rounded-lg" />}>
                <Button
                  size="lg"
                  disabled
                  className="h-11 gap-2 bg-gradient-accent px-6 text-base text-white shadow-lg shadow-indigo-900/20"
                >
                  Check new rules <ArrowRight aria-hidden />
                </Button>
              </TooltipTrigger>
              <TooltipContent>Coming next</TooltipContent>
            </Tooltip>
            <Link
              href="/how-it-works"
              className={cn(buttonVariants({ variant: "outline", size: "lg" }), "h-11 bg-white px-6 text-base")}
            >
              How it works
            </Link>
          </div>
        </FadeIn>
      </div>
    </section>
  );
}
