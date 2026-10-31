"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, getNotices } from "./api";
import type { Lang, NoticesResponse, ProfileId } from "./types";

const RETRY_EVERY_MS = 4_000;
const GIVE_UP_AFTER_MS = 60_000;
const SLOW_AFTER_MS = 8_000; // after this the first load is "waking up the server", not just reading

export type NoticesStatus = "idle" | "loading" | "refreshing" | "ready" | "error";

/**
 * Loads /notices. The first load shows skeletons ("loading"); later loads keep the old list ("refreshing").
 * Network errors, timeouts and 5xx are retried for up to 60 s (Render cold start); a newer request cancels an older one,
 * so a slow earlier response can never overwrite a newer one.
 */
export function useNotices() {
  const [status, setStatus] = useState<NoticesStatus>("idle");
  const [data, setData] = useState<NoticesResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [elapsedMs, setElapsedMs] = useState(0);
  const last = useRef<{ profile: ProfileId; lang: Lang } | null>(null);
  const ctrl = useRef<AbortController | null>(null);
  const dataRef = useRef<NoticesResponse | null>(null);

  useEffect(() => () => ctrl.current?.abort(), []);

  const run = useCallback(async (profile: ProfileId, lang: Lang) => {
    ctrl.current?.abort();
    const c = new AbortController();
    ctrl.current = c;
    last.current = { profile, lang };
    const startedAt = Date.now();
    setStatus(dataRef.current ? "refreshing" : "loading");
    setError(null);
    setElapsedMs(0);
    const tick = setInterval(() => setElapsedMs(Date.now() - startedAt), 500);

    try {
      for (;;) {
        try {
          const res = await getNotices(profile, lang, c.signal);
          if (c.signal.aborted) return;
          dataRef.current = res;
          setData(res);
          setStatus("ready");
          return;
        } catch (e) {
          if (c.signal.aborted) return;
          const api = e instanceof ApiError ? e : null;
          console.warn("[pramaan] /notices attempt failed", api ? { kind: api.kind, status: api.status, cause: api.cause } : e);
          const retryable = !api || api.kind !== "server" || (api.status ?? 500) >= 500;
          if (!retryable || Date.now() - startedAt >= GIVE_UP_AFTER_MS) {
            setError(api?.message ?? "Something went wrong while loading the notices.");
            setStatus("error");
            return;
          }
          await new Promise((r) => setTimeout(r, RETRY_EVERY_MS));
          if (c.signal.aborted) return;
        }
      }
    } finally {
      clearInterval(tick);
    }
  }, []);

  const retry = useCallback(() => {
    if (last.current) run(last.current.profile, last.current.lang);
  }, [run]);

  return { status, data, error, elapsedMs, slow: elapsedMs >= SLOW_AFTER_MS, giveUpAfterMs: GIVE_UP_AFTER_MS, run, retry };
}
