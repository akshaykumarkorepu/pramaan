import type { Applies, ObligationStatus } from "@/lib/types";

// One place that decides how each status looks, so colours stay consistent across the app.
export const OBLIGATION_STATUS: Record<ObligationStatus, { label: string; badge: string }> = {
  verified: { label: "Verified", badge: "bg-verified-soft text-verified border-verified/25" },
  near: { label: "Near match", badge: "bg-review-soft text-review border-review/30" },
  rejected: { label: "Rejected", badge: "bg-rejected-soft text-rejected border-rejected/25" },
  fixed: { label: "Fixed on retry", badge: "bg-fixed-soft text-fixed border-fixed/25" },
};

export const APPLIES_STATUS: Record<Applies, { label: string; badge: string }> = {
  yes: { label: "Applies to you", badge: "bg-verified-soft text-verified border-verified/25" },
  review: { label: "Needs review", badge: "bg-review-soft text-review border-review/30" },
  no: { label: "Doesn't apply", badge: "bg-slate-100 text-slate-500 border-slate-200" },
};

// Source badge colours (not status colours): RBI indigo, SEBI teal, PIB orange
export const SOURCE_STYLE = {
  rbi: { label: "RBI", badge: "bg-indigo-50 text-indigo-700 border-indigo-200" },
  sebi: { label: "SEBI", badge: "bg-teal-50 text-teal-700 border-teal-200" },
  pib: { label: "PIB", badge: "bg-orange-50 text-orange-700 border-orange-200" },
} as const;
