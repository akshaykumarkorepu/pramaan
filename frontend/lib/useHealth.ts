"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, getHealth } from "./api";
import type { HealthResponse } from "./types";

const RETRY_EVERY_MS = 4_000;
const GIVE_UP_AFTER_MS = 60_000; // Render free tier can take ~60 s to cold-start

export type HealthPhase = "loading" | "waking" | "ready" | "failed";

/**
 * Loads /health. While the backend is asleep (network error / timeout / 5xx) it keeps retrying for up to 60 s
 * and reports phase "waking"; after that phase is "failed" until retry() is called.
 */
export function useHealth() {
  const [phase, setPhase] = useState<HealthPhase>("loading");
  const [data, setData] = useState<HealthResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [elapsedMs, setElapsedMs] = useState(0);
  const [attempt, setAttempt] = useState(0); // bumping this restarts the loop
  const startedAt = useRef(0);

  useEffect(() => {
    const ctrl = new AbortController();
    let timer: ReturnType<typeof setTimeout> | undefined;
    startedAt.current = Date.now();

    const tick = setInterval(() => setElapsedMs(Date.now() - startedAt.current), 500);

    async function run() {
      try {
        const h = await getHealth(ctrl.signal);
        setData(h);
        setError(null);
        setPhase("ready");
        clearInterval(tick);
      } catch (e) {
        if (ctrl.signal.aborted) return;
        // visible in the browser console so a failure on someone else's machine (e.g. Brave Shields) can be diagnosed
        console.warn(
          `[pramaan] /health attempt failed after ${Math.round((Date.now() - startedAt.current) / 1000)}s`,
          e instanceof ApiError ? { kind: e.kind, status: e.status, message: e.message, cause: e.cause } : e,
        );
        const msg = e instanceof ApiError ? e.message : "Something went wrong while contacting the server.";
        if (Date.now() - startedAt.current >= GIVE_UP_AFTER_MS) {
          setError(msg);
          setPhase("failed");
          clearInterval(tick);
          return;
        }
        setPhase("waking");
        timer = setTimeout(run, RETRY_EVERY_MS);
      }
    }
    run();

    return () => {
      ctrl.abort();
      clearTimeout(timer);
      clearInterval(tick);
    };
  }, [attempt]);

  const retry = useCallback(() => {
    setPhase("loading");
    setError(null);
    setElapsedMs(0);
    setAttempt((n) => n + 1);
  }, []);

  return { phase, data, error, elapsedMs, giveUpAfterMs: GIVE_UP_AFTER_MS, retry };
}
