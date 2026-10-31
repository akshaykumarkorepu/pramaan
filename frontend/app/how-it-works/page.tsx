import { FadeIn } from "@/components/motion/FadeIn";

export const metadata = { title: "How it works — Pramaan" };

export default function HowItWorks() {
  return (
    <div className="mx-auto w-full max-w-[1100px] px-4 py-20 sm:px-6">
      <FadeIn>
        <h1 className="text-3xl font-bold text-slate-900 sm:text-4xl">How it works</h1>
        <p className="mt-4 max-w-2xl text-slate-600">
          The full pipeline walkthrough, with a live look at the verifier, is coming soon.
        </p>
      </FadeIn>
    </div>
  );
}
