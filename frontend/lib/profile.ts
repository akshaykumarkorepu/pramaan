import { Building2, Landmark, LineChart, Store, TrendingUp, type LucideIcon } from "lucide-react";
import type { Lang, ProfileId } from "./types";

export const PROFILES: { id: ProfileId; label: string; icon: LucideIcon }[] = [
  { id: "nbfc", label: "NBFC", icon: Landmark },
  { id: "coop_bank", label: "Co-operative Bank", icon: Building2 },
  { id: "research_analyst", label: "SEBI Research Analyst", icon: LineChart },
  { id: "stock_broker", label: "Stock Broker", icon: TrendingUp },
  { id: "citizen_msme", label: "Citizen / Small business", icon: Store },
];

export const LANGS: { id: Lang; label: string }[] = [
  { id: "en", label: "English" },
  { id: "te", label: "తెలుగు" },
  { id: "hi", label: "हिंदी" },
];

export interface Prefs {
  profile: ProfileId | null;
  lang: Lang;
}

const KEY = "pramaan.prefs.v1";

export const isProfile = (v: unknown): v is ProfileId => PROFILES.some((p) => p.id === v);
export const isLang = (v: unknown): v is Lang => LANGS.some((l) => l.id === v);

/** localStorage can throw (private mode, blocked storage) and does not exist on the server. */
export function loadPrefs(): Prefs | null {
  try {
    if (typeof window === "undefined") return null;
    const raw = window.localStorage.getItem(KEY);
    if (!raw) return null;
    const v = JSON.parse(raw);
    return { profile: isProfile(v?.profile) ? v.profile : null, lang: isLang(v?.lang) ? v.lang : "en" };
  } catch {
    return null;
  }
}

export function savePrefs(p: Prefs): void {
  try {
    window.localStorage.setItem(KEY, JSON.stringify(p));
  } catch {
    /* storage unavailable: the choice just won't persist */
  }
}
