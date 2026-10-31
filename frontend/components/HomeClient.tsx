"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { ControlPanel } from "@/components/ControlPanel";
import { Hero } from "@/components/Hero";
import { LiveStatus } from "@/components/LiveStatus";
import { PasteLink } from "@/components/PasteLink";
import { NoticesSection } from "@/components/NoticesSection";
import { usePrefs } from "@/lib/usePrefs";
import { useNotices } from "@/lib/useNotices";
import type { ProfileId } from "@/lib/types";

const DEBOUNCE_MS = 400;

export function HomeClient() {
  const router = useRouter();
  const { prefs, update } = usePrefs();
  const notices = useNotices();
  const [showHint, setShowHint] = useState(false);
  const started = useRef(false); // true once the user has pressed "Check new rules"
  const selectRef = useRef<HTMLButtonElement>(null);
  const { run } = notices;

  const check = useCallback(() => {
    if (!prefs.profile) {
      setShowHint(true);
      selectRef.current?.focus();
      return;
    }
    started.current = true;
    run(prefs.profile, prefs.lang);
  }, [prefs.profile, prefs.lang, run]);

  // After the first check, a change of profile or language re-fetches by itself (debounced).
  // Restoring saved prefs on load does not count: nothing is fetched until the first click.
  useEffect(() => {
    if (!started.current || !prefs.profile) return;
    const profile = prefs.profile;
    const t = setTimeout(() => run(profile, prefs.lang), DEBOUNCE_MS);
    return () => clearTimeout(t);
  }, [prefs.profile, prefs.lang, run]);

  const scrollToControls = () =>
    document.getElementById("check")?.scrollIntoView({ behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block: "start" });

  const goToCircular = (url: string, profile: ProfileId) =>
    router.push(`/circular?url=${encodeURIComponent(url)}&profile=${profile}&lang=${prefs.lang}`);

  return (
    <>
      <Hero
        onCheck={() => {
          scrollToControls();
          check();
        }}
      />
      <ControlPanel
        profile={prefs.profile}
        lang={prefs.lang}
        onProfile={(profile) => {
          setShowHint(false);
          update({ profile });
        }}
        onLang={(lang) => update({ lang })}
        onCheck={check}
        busy={notices.status === "loading"}
        showHint={showHint}
        triggerRef={selectRef}
      />
      <LiveStatus />
      <NoticesSection
        status={notices.status}
        data={notices.data}
        error={notices.error}
        slow={notices.slow}
        elapsedMs={notices.elapsedMs}
        giveUpAfterMs={notices.giveUpAfterMs}
        onRetry={notices.retry}
        profile={prefs.profile}
        lang={prefs.lang}
      />
      <PasteLink id="paste" variant="card" profile={prefs.profile} onProfile={(profile) => update({ profile })} onGo={goToCircular} />
    </>
  );
}
