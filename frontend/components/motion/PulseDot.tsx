import { cn } from "@/lib/utils";

type Tone = "ok" | "fail" | "pending";

const TONES: Record<Tone, { dot: string; ring: string }> = {
  ok: { dot: "bg-verified", ring: "bg-verified" },
  fail: { dot: "bg-rejected", ring: "" },
  pending: { dot: "bg-review", ring: "bg-review" },
};

/** Status dot: a pulsing ring when ok (or pending), static rose when failed. The ring is CSS so reduced-motion CSS stops it. */
export function PulseDot({ tone, className }: { tone: Tone; className?: string }) {
  const t = TONES[tone];
  return (
    <span className={cn("relative inline-flex size-2.5", className)} aria-hidden>
      {tone !== "fail" && (
        <span className={cn("absolute inset-0 rounded-full motion-safe:animate-ping-slow", t.ring)} />
      )}
      <span className={cn("relative inline-flex size-2.5 rounded-full", t.dot)} />
    </span>
  );
}
