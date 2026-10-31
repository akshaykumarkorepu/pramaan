"use client";

import { useCallback, useSyncExternalStore } from "react";
import { loadPrefs, savePrefs, type Prefs } from "./profile";
import type { Lang, ProfileId } from "./types";

// localStorage as an external store: the server render and hydration use DEFAULT, then React switches to the saved value.
const DEFAULT: Prefs = { profile: null, lang: "en" };
let cache: Prefs | null = null;
const listeners = new Set<() => void>();

function getSnapshot(): Prefs {
  if (!cache) cache = loadPrefs() ?? DEFAULT;
  return cache;
}
const getServerSnapshot = () => DEFAULT;
function subscribe(cb: () => void) {
  listeners.add(cb);
  return () => listeners.delete(cb);
}

/** Profile + language, persisted in localStorage. */
export function usePrefs() {
  const prefs = useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
  const update = useCallback((patch: { profile?: ProfileId; lang?: Lang }) => {
    cache = { ...getSnapshot(), ...patch };
    savePrefs(cache);
    listeners.forEach((l) => l());
  }, []);
  return { prefs, update };
}
