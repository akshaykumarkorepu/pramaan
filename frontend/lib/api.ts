import type {
  AnalyzeEvent,
  ErrorEvent,
  HealthResponse,
  Lang,
  NoticesResponse,
  ProfileId,
  ResultEvent,
  StepEvent,
} from "./types";

// Browser talks to the backend directly (not through Next API routes) so SSE streams work.
export const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/+$/, "");

/** Always carries a message that is safe to show to a user. */
export class ApiError extends Error {
  constructor(
    message: string,
    /** "network" = could not reach the server at all (offline, cold start, CORS); "timeout"; "server" = HTTP error */
    readonly kind: "network" | "timeout" | "server",
    readonly status?: number,
    /** the underlying fetch error, kept for console debugging only */
    readonly cause?: unknown,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

function qs(params: Record<string, string>): string {
  return new URLSearchParams(params).toString();
}

async function fetchJson<T>(path: string, timeoutMs = 15_000, signal?: AbortSignal): Promise<T> {
  const ctrl = new AbortController();
  let timedOut = false;
  const timer = setTimeout(() => {
    timedOut = true;
    ctrl.abort();
  }, timeoutMs);
  signal?.addEventListener("abort", () => ctrl.abort(), { once: true });
  try {
    const res = await fetch(`${API_URL}${path}`, { signal: ctrl.signal, headers: { Accept: "application/json" } });
    if (!res.ok) {
      let detail = "";
      try {
        const body = await res.json();
        detail = typeof body?.error === "string" ? body.error : "";
      } catch {
        /* body was not JSON */
      }
      throw new ApiError(detail || `The server answered with an error (${res.status}).`, "server", res.status);
    }
    return (await res.json()) as T;
  } catch (e) {
    if (e instanceof ApiError) throw e;
    if (timedOut) throw new ApiError("The server took too long to answer.", "timeout", undefined, e);
    if (signal?.aborted) throw e; // caller cancelled on purpose
    throw new ApiError("Could not reach the server. Check your connection and try again.", "network", undefined, e);
  } finally {
    clearTimeout(timer);
  }
}

export function getHealth(signal?: AbortSignal, timeoutMs = 15_000): Promise<HealthResponse> {
  return fetchJson<HealthResponse>("/health", timeoutMs, signal);
}

export function getNotices(
  profile: ProfileId,
  lang: Lang,
  signal?: AbortSignal,
  timeoutMs = 25_000,
): Promise<NoticesResponse> {
  return fetchJson<NoticesResponse>(`/notices?${qs({ profile, lang })}`, timeoutMs, signal);
}

export interface AnalyzeHandlers {
  onStep?: (e: StepEvent) => void;
  onResult?: (e: ResultEvent) => void;
  onError?: (e: ErrorEvent) => void;
}

/** Streams /analyze. Returns a cancel function. The stream is closed on the first result/error event. */
export function analyze(
  url: string,
  profile: ProfileId,
  lang: Lang,
  verifierTest: boolean,
  { onStep, onResult, onError }: AnalyzeHandlers,
): () => void {
  const es = new EventSource(
    `${API_URL}/analyze?${qs({ url, profile, lang, verifier_test: verifierTest ? "1" : "0" })}`,
  );
  let finished = false;
  let gotEvent = false; // nothing received yet usually means the server is still waking up (Render free tier)
  const finish = () => {
    finished = true;
    es.close(); // without this EventSource would reconnect and re-run the analysis
  };

  es.onmessage = (msg) => {
    gotEvent = true;
    if (finished) return; // cancelled (language switched, new run started) or already done: a late frame must not touch state
    let ev: AnalyzeEvent;
    try {
      ev = JSON.parse(msg.data) as AnalyzeEvent;
    } catch {
      return; // ignore malformed frames
    }
    if (ev.type === "step") onStep?.(ev);
    else if (ev.type === "result") {
      finish();
      onResult?.(ev);
    } else if (ev.type === "error") {
      finish();
      onError?.(ev);
    }
  };

  es.onerror = () => {
    if (finished) return;
    finish();
    onError?.({
      type: "error",
      step: "connection",
      message: gotEvent
        ? "The connection to the server dropped before the analysis finished. Please try again."
        : "Couldn't reach the server. It may still be waking up (this can take up to a minute). Please try again.",
      url,
    });
  };

  return () => {
    finished = true;
    es.close();
  };
}

export function ttsUrl(text: string, lang: Lang): string {
  return `${API_URL}/tts?${qs({ text, lang })}`;
}

export function icsUrl(url: string, profile: ProfileId): string {
  return `${API_URL}/ics?${qs({ url, profile })}`;
}
