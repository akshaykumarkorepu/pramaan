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

/** One duty's proof sentence as a place in the document. */
export interface DocHighlight {
  obligation: Obligation;
  paragraph: string;
  start: number; // offsets inside that paragraph's text
  end: number;
}

/**
 * The duties that can be marked in the document: verified / near / fixed ones that have a match_span, in reading order
 * (paragraph order, then position inside the paragraph). Rejected duties and the injected test claim have nothing to mark.
 */
export function highlightTargets(real: Obligation[], paragraphs: { id: string }[]): DocHighlight[] {
  const order = new Map(paragraphs.map((p, i) => [p.id, i]));
  return real
    .filter((o) => o.status !== "rejected" && !o.injected_test && o.match_span && order.has(o.match_span.paragraph))
    .map((o) => ({ obligation: o, paragraph: o.match_span!.paragraph, start: o.match_span!.para_start, end: o.match_span!.para_end }))
    .sort((a, b) => order.get(a.paragraph)! - order.get(b.paragraph)! || a.start - b.start);
}

export interface Segment {
  text: string;
  mark: "active" | "other" | null;
}

/** Cuts a paragraph into plain and highlighted pieces. Offsets are clamped; a span inside an earlier one is dropped. */
export function paragraphSegments(text: string, spans: { start: number; end: number; active: boolean }[]): Segment[] {
  const clamp = (n: number) => Math.max(0, Math.min(n, text.length));
  const sorted = spans
    .map((s) => ({ ...s, start: clamp(s.start), end: clamp(s.end) }))
    .filter((s) => s.end > s.start)
    .sort((a, b) => a.start - b.start || b.end - a.end);
  const out: Segment[] = [];
  let pos = 0;
  for (const s of sorted) {
    const start = Math.max(s.start, pos);
    if (s.end <= start) continue;
    if (start > pos) out.push({ text: text.slice(pos, start), mark: null });
    out.push({ text: text.slice(start, s.end), mark: s.active ? "active" : "other" });
    pos = s.end;
  }
  if (pos < text.length) out.push({ text: text.slice(pos), mark: null });
  return out.length ? out : [{ text, mark: null }];
}
