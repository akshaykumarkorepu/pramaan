import { FileSearch, Languages, ListChecks, RefreshCcw, ShieldCheck, UserCheck, type LucideIcon } from "lucide-react";
import type { StepName } from "./useAnalyze";
import type { Doc, MatchSpan, Obligation, SourceId } from "./types";

export const STEP_META: Record<StepName, { label: string; icon: LucideIcon }> = {
  fetch_document: { label: "Reading the document", icon: FileSearch },
  extract: { label: "Extracting duties", icon: ListChecks },
  verify: { label: "Verifying every quote", icon: ShieldCheck },
  retry: { label: "Self-correcting", icon: RefreshCcw },
  applicability: { label: "Checking if it applies to you", icon: UserCheck },
  explain: { label: "Explaining in your language", icon: Languages },
};

export function sourceFromUrl(url: string): SourceId | null {
  try {
    const h = new URL(url).hostname.toLowerCase();
    if (h.endsWith("rbi.org.in")) return "rbi";
    if (h.endsWith("sebi.gov.in")) return "sebi";
    if (h.endsWith("pib.gov.in")) return "pib";
  } catch {
    /* not a URL */
  }
  return null;
}

/** Verified / near / fixed first (earliest deadline first, undated last), rejected last. The injected test claim is split out. */
export function splitObligations(all: Obligation[]): { real: Obligation[]; test: Obligation | null } {
  const test = all.find((o) => o.injected_test) ?? null;
  const rank = (o: Obligation) => (o.status === "rejected" ? 1 : 0);
  const real = all
    .filter((o) => !o.injected_test)
    .map((o, i) => ({ o, i }))
    .sort((a, b) => rank(a.o) - rank(b.o) || (a.o.deadline ?? "9999").localeCompare(b.o.deadline ?? "9999") || a.i - b.i)
    .map((x) => x.o);
  return { real, test };
}

/** The paragraph where the quote matched, cut into text before / the match / after. Offsets are clamped to the paragraph. */
export function proofParts(doc: Doc, span: MatchSpan | null): { id: string; before: string; hit: string; after: string } | null {
  if (!span) return null;
  const para = doc.paragraphs.find((p) => p.id === span.paragraph);
  if (!para) return null;
  const start = Math.max(0, Math.min(span.para_start, para.text.length));
  const end = Math.max(start, Math.min(span.para_end, para.text.length));
  return { id: para.id, before: para.text.slice(0, start), hit: para.text.slice(start, end), after: para.text.slice(end) };
}

const REASONS: Record<string, string> = {
  "quote not found in source": "Quote not found in the official text",
};
export const friendlyReason = (r: string | null) => (r ? (REASONS[r] ?? r.charAt(0).toUpperCase() + r.slice(1)) : "Not found in the official text");

export function formatMs(ms: number | null): string {
  if (ms === null) return "";
  return ms < 1000 ? `${Math.round(ms)} ms` : `${(ms / 1000).toFixed(1)} s`;
}

export function formatDeadline(iso: string): string {
  const d = new Date(`${iso}T00:00:00`);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
}

/** "Paragraph 6" for ids like "6" or "p6"; the document's own numbering ("2.1", "3.1(a)") is kept as it is. */
export function paragraphLabel(id: string): string {
  return `Paragraph ${id.replace(/^p(?=\d)/i, "")}`;
}
