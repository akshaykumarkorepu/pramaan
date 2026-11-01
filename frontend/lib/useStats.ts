"use client";

import { useEffect, useState } from "react";
import { getStats } from "./api";
import type { StatsResponse } from "./types";

const EVERY_MS = 60_000;

/** Live proof stats from /stats, polled once a minute while `enabled`. null until known or if the endpoint is unreachable. */
export function useStats(enabled: boolean): StatsResponse | null {
  const [stats, setStats] = useState<StatsResponse | null>(null);
  useEffect(() => {
    if (!enabled) return;
    const ctrl = new AbortController();
    const load = () =>
      getStats(ctrl.signal)
        .then(setStats)
        .catch(() => {
          /* stats are a nice-to-have: never an error in the UI */
        });
    load();
    const t = setInterval(load, EVERY_MS);
    return () => {
      ctrl.abort();
      clearInterval(t);
    };
  }, [enabled]);
  return stats;
}
