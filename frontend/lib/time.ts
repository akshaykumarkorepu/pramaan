"use client";

import { useEffect, useState } from "react";

/** Current time in ms, 0 until mounted (Date.now() must not run during prerender). Ticks every `everyMs`. */
export function useNow(everyMs = 30_000): number {
  const [now, setNow] = useState(0);
  useEffect(() => {
    const tick = () => setNow(Date.now());
    tick();
    const t = setInterval(tick, everyMs);
    return () => clearInterval(t);
  }, [everyMs]);
  return now;
}

/** "fetched 5 min ago". Empty until `now` is known. */
export function ago(iso: string | null, now: number): string {
  if (!iso) return "not fetched yet";
  if (!now) return "";
  const mins = Math.max(0, Math.floor((now - new Date(iso).getTime()) / 60_000));
  if (mins < 1) return "fetched just now";
  if (mins === 1) return "fetched 1 min ago";
  if (mins < 60) return `fetched ${mins} min ago`;
  return `fetched ${Math.floor(mins / 60)} h ago`;
}

/** ISO date (YYYY-MM-DD) -> "30 Oct 2026". The PIB feed has no dates. */
export function formatDate(iso: string | null): string {
  if (!iso) return "date not in feed";
  const d = new Date(`${iso}T00:00:00`);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
}
