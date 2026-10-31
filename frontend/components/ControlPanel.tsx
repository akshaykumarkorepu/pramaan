"use client";

import type { Ref } from "react";
import { ArrowRight, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { LangText } from "@/components/LangText";
import { FadeIn } from "@/components/motion/FadeIn";
import { LANGS, PROFILES, isLang, isProfile } from "@/lib/profile";
import type { Lang, ProfileId } from "@/lib/types";

export function ControlPanel({
  profile,
  lang,
  onProfile,
  onLang,
  onCheck,
  busy,
  showHint,
  triggerRef,
}: {
  profile: ProfileId | null;
  lang: Lang;
  onProfile: (p: ProfileId) => void;
  onLang: (l: Lang) => void;
  onCheck: () => void;
  busy: boolean;
  showHint: boolean;
  triggerRef: Ref<HTMLButtonElement>;
}) {
  return (
    <section id="check" className="mx-auto w-full max-w-[1100px] scroll-mt-20 px-4 sm:px-6" aria-labelledby="who-are-you">
      <FadeIn delay={0.45}>
        <div className="glass rounded-2xl border border-slate-200 p-5 shadow-soft sm:p-6">
          <h2 id="who-are-you" className="text-lg font-semibold text-slate-900">
            Who are you?
          </h2>
          <p className="mt-0.5 text-sm text-slate-500">We use this to tell you which notices apply to you.</p>

          <div className="mt-5 grid gap-5 md:grid-cols-[minmax(0,1fr)_auto_auto] md:items-end">
            <div>
              <label className="mb-1.5 block text-xs font-medium uppercase tracking-wide text-slate-500">
                I am a…
              </label>
              <Select
                value={profile}
                onValueChange={(v) => {
                  if (isProfile(v)) onProfile(v);
                }}
              >
                <SelectTrigger
                  ref={triggerRef}
                  aria-label="Who are you"
                  aria-invalid={showHint && !profile}
                  className="h-11 w-full bg-white text-[15px]"
                >
                  <SelectValue placeholder="Choose who you are">
                    {(v: ProfileId | null) => {
                      const p = PROFILES.find((x) => x.id === v);
                      if (!p) return "Choose who you are";
                      return (
                        <>
                          <p.icon className="size-4 text-brand" aria-hidden />
                          {p.label}
                        </>
                      );
                    }}
                  </SelectValue>
                </SelectTrigger>
                <SelectContent alignItemWithTrigger={false}>
                  {PROFILES.map((p) => (
                    <SelectItem key={p.id} value={p.id} className="py-2 text-[15px]">
                      <p.icon className="size-4 text-brand" aria-hidden />
                      {p.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {showHint && !profile && (
                <p role="alert" className="mt-1.5 text-[13px] font-medium text-rejected">
                  Choose who you are first.
                </p>
              )}
            </div>

            <div>
              <span className="mb-1.5 block text-xs font-medium uppercase tracking-wide text-slate-500">Language</span>
              <ToggleGroup
                value={[lang]}
                onValueChange={(v) => {
                  // single-select that can't be emptied: ignore the click that would un-press the active item
                  const next = v[0];
                  if (isLang(next)) onLang(next);
                }}
                variant="outline"
                spacing={0}
                aria-label="Language"
                className="w-full rounded-lg bg-white md:w-fit"
              >
                {LANGS.map((l) => (
                  <ToggleGroupItem
                    key={l.id}
                    value={l.id}
                    className="h-11 flex-1 px-4 text-[15px] aria-pressed:bg-brand aria-pressed:text-white md:flex-none"
                  >
                    <LangText lang={l.id}>{l.label}</LangText>
                  </ToggleGroupItem>
                ))}
              </ToggleGroup>
            </div>

            <Button
              onClick={onCheck}
              disabled={busy}
              className="h-11 w-full gap-2 bg-gradient-accent px-6 text-[15px] text-white shadow-md shadow-indigo-900/20 md:w-auto"
            >
              {busy ? <Loader2 className="animate-spin" aria-hidden /> : null}
              Check new rules {!busy && <ArrowRight aria-hidden />}
            </Button>
          </div>
        </div>
      </FadeIn>
    </section>
  );
}
