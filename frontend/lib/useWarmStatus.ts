"use client";

import { useEffect, useState } from "react";
import { getWarmStatus } from "./api";
import type { WarmStatus } from "./types";

const EVERY_MS = 60_000;

/** The background pre-analysis state, polled once a minute while `enabled`. null until known or if the endpoint is unreachable. */
export function useWarmStatus(enabled: boolean): WarmStatus | null {
  const [status, setStatus] = useState<WarmStatus | null>(null);
  useEffect(() => {
    if (!enabled) return;
    const ctrl = new AbortController();
    const load = () =>
      getWarmStatus(ctrl.signal)
        .then(setStatus)
        .catch(() => {
          /* a nice-to-have note: never an error in the UI */
        });
    load();
    const t = setInterval(load, EVERY_MS);
    return () => {
      ctrl.abort();
      clearInterval(t);
    };
  }, [enabled]);
  return status;
}
