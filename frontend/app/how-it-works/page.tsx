import { FadeIn } from "@/components/motion/FadeIn";
import { PipelineDiagram } from "@/components/how/PipelineDiagram";
import { BuiltWith, Evidence, Guardrails, HowCta, Limits, Section, Sources, Team } from "@/components/how/HowSections";

export const metadata = {
  title: "How it works",
  description: "How Pramaan fetches live notices, extracts duties with verbatim quotes, verifies each one in code, and explains only what passed.",
};

export default function HowItWorks() {
  return (
    <>
      <section className="relative isolate overflow-hidden">
        <div className="bg-dots absolute inset-0 -z-20" aria-hidden />
        <div aria-hidden className="absolute left-1/2 top-2 -z-10 h-64 w-[min(640px,90vw)] -translate-x-1/2 rounded-full bg-gradient-accent opacity-15 blur-3xl" />
        <div className="mx-auto max-w-[1100px] px-4 pb-8 pt-16 text-center sm:px-6 sm:pt-24">
          <FadeIn>
            <h1 className="mx-auto max-w-3xl text-balance text-4xl font-bold leading-[1.1] text-slate-900 sm:text-5xl">
              Live data in. <span className="text-gradient-accent">Verified answers out.</span>
            </h1>
          </FadeIn>
          <FadeIn delay={0.12}>
            <p className="mx-auto mt-5 max-w-2xl text-pretty text-base leading-relaxed text-slate-600 sm:text-lg">
              Pramaan fetches a real notice when you ask, lets AI draft the duties, then proves every quote, number and date in code before
              anything is explained to you.
            </p>
          </FadeIn>
        </div>
      </section>

      <Section title="The pipeline" intro="Seven steps, in order. The fourth one is where trust is decided.">
        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-soft sm:p-8">
          <PipelineDiagram />
        </div>
      </Section>

      <Section title="How we stop the AI from making things up">
        <Guardrails />
      </Section>

      <Section title="Live official sources">
        <Sources />
      </Section>

      <Section title="Built with">
        <BuiltWith />
      </Section>

      <Section title="Evidence">
        <Evidence />
      </Section>

      <Section title="Honest limits">
        <Limits />
      </Section>

      <Section title="Team">
        <Team />
      </Section>

      <Section title="Try it on a real notice">
        <HowCta />
      </Section>
    </>
  );
}
