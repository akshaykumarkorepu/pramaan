// Mirrors backend/api/schemas.py. Change both in the same commit.

export type SourceId = "rbi" | "sebi" | "pib";
export type ProfileId = "nbfc" | "coop_bank" | "research_analyst" | "stock_broker" | "citizen_msme";
export type Lang = "en" | "te" | "hi";
export type Applies = "yes" | "no" | "review";
export type ObligationStatus = "verified" | "near" | "rejected" | "fixed";
export type StepStatus = "running" | "done" | "failed";

// ---------- /health ----------
export interface SourceHealth {
  ok: boolean;
  last_fetch: string | null;
  count: number;
  error: string | null;
}
export interface LLMHealth {
  ok: boolean;
  model: string | null;
  error: string | null;
}
export interface RuntimeHealth {
  ok: boolean;
  error: string | null;
}
export interface HealthResponse {
  sources: Record<SourceId, SourceHealth>;
  llm: LLMHealth;
  runtime: RuntimeHealth;
}

// ---------- /notices ----------
export interface Notice {
  id: string;
  source: SourceId;
  title: string;
  url: string;
  date: string | null; // ISO date; the PIB feed has none
  fetched_at: string;
  applies: Applies;
  reason: string;
}
export interface NoticeSource {
  ok: boolean;
  error: string | null;
  count: number;
}
export interface NoticesResponse {
  items: Notice[];
  sources: Record<SourceId, NoticeSource>;
}

// ---------- /analyze (SSE) ----------
export interface Paragraph {
  id: string;
  text: string;
}
export interface Doc {
  title: string;
  url: string;
  fetched_at: string;
  paragraphs: Paragraph[];
}
export interface MatchSpan {
  start: number;
  end: number;
  paragraph: string;
  para_start: number;
  para_end: number;
}
export interface Obligation {
  who: string;
  must_do: string;
  deadline: string | null;
  effective_from: string | null;
  paragraph: string | null;
  quote: string;
  penalty_or_consequence: string | null; // not returned by the API today; kept as the schema declares it
  status: ObligationStatus;
  reason: string | null;
  match_span: MatchSpan | null;
  matched_text: string | null;
  score: number | null;
  paragraph_corrected: boolean;
  injected_test: boolean;
}
export interface Counts {
  verified: number; // includes "near"
  rejected: number;
  fixed: number;
}
export interface Applicability {
  value: Applies;
  reason: string;
  quote: string | null;
}
export interface Explainer {
  lang: Lang;
  text: string;
  source: "llm" | "template";
}
export interface LLMMeta {
  model: string;
  ms: number;
}

export interface StepEvent {
  type: "step";
  name: string; // fetch_document | extract | verify | retry | applicability | explain
  status: StepStatus;
  ms: number | null;
  detail: string | null;
}
export interface ResultEvent {
  type: "result";
  doc: Doc;
  obligations: Obligation[];
  counts: Counts;
  applies: Applicability;
  explainer: Explainer;
  llm: LLMMeta;
}
export interface ErrorEvent {
  type: "error";
  step: string;
  message: string;
  url: string | null;
}
export type AnalyzeEvent = StepEvent | ResultEvent | ErrorEvent;
