"use client";

import { useId, useState } from "react";
import { ArrowRight, Link2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ProfileSelect } from "@/components/ProfileSelect";
import { validateOfficialUrl } from "@/lib/links";
import type { ProfileId } from "@/lib/types";
import { cn } from "@/lib/utils";

/**
 * Paste any RBI / SEBI / PIB link. Validated in the browser, then handed to `onGo`.
 * If no profile is chosen yet (home page), a profile picker appears inline and the link continues once one is picked.
 */
export function PasteLink({
  variant,
  profile,
  onProfile,
  onGo,
  id,
}: {
  variant: "card" | "compact";
  profile: ProfileId | null;
  onProfile?: (p: ProfileId) => void;
  onGo: (url: string, profile: ProfileId) => void;
  id?: string;
}) {
  const uid = useId();
  const [text, setText] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState<string | null>(null); // valid link waiting for a profile
  const errId = `${uid}-err`;
  const compact = variant === "compact";

  const submit = () => {
    const r = validateOfficialUrl(text);
    if (!r.ok) {
      setPending(null);
      setError(r.error);
      return;
    }
    setError(null);
    if (profile) onGo(r.url, profile);
    else setPending(r.url);
  };

  const form = (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        submit();
      }}
      noValidate
    >
      <div className={cn("flex flex-col gap-2 sm:flex-row", compact && "sm:items-start")}>
        <div className="relative flex-1">
          <Link2 className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-slate-400" aria-hidden />
          <input
            id={id ? `${id}-input` : undefined}
            type="text"
            inputMode="url"
            autoComplete="off"
            spellCheck={false}
            value={text}
            onChange={(e) => {
              setText(e.target.value);
              setError(null);
              setPending(null);
            }}
            placeholder="Paste any RBI, SEBI or PIB link"
            aria-label="Paste any RBI, SEBI or PIB link"
            aria-invalid={!!error}
            aria-describedby={error ? errId : undefined}
            className={cn(
              "w-full rounded-lg border bg-white pl-9 pr-3 text-[15px] text-slate-900 shadow-xs outline-none transition-colors placeholder:text-slate-400 focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/30",
              compact ? "h-10" : "h-11",
              error ? "border-rejected" : "border-slate-200",
            )}
          />
        </div>
        <Button
          type="submit"
          className={cn("w-full gap-2 bg-gradient-accent px-5 text-[15px] text-white shadow-md shadow-indigo-900/20 sm:w-auto", compact ? "h-10" : "h-11")}
        >
          Analyse <ArrowRight aria-hidden />
        </Button>
      </div>
      {error && (
        <p id={errId} role="alert" className="mt-1.5 text-[13px] font-medium text-rejected">
          {error}
        </p>
      )}
    </form>
  );

  const picker = pending && onProfile && (
    <div className="mt-4 rounded-xl border border-slate-200 bg-white/70 p-4">
      <p className="text-sm font-medium text-slate-900">One more thing: who are you?</p>
      <p className="mt-0.5 text-[13px] text-slate-500">We use this to check whether the notice applies to you.</p>
      <div className="mt-3 max-w-sm">
        <ProfileSelect
          profile={null}
          onProfile={(p) => {
            onProfile(p);
            onGo(pending, p);
          }}
        />
      </div>
    </div>
  );

  if (compact) {
    return (
      <div id={id} className="mt-5 max-w-2xl">
        {form}
      </div>
    );
  }
  return (
    <section id={id} className="mx-auto mt-10 w-full max-w-[1100px] scroll-mt-20 px-4 sm:px-6" aria-labelledby={`${uid}-h`}>
      <div className="glass rounded-2xl border border-slate-200 p-5 shadow-soft sm:p-6">
        <h2 id={`${uid}-h`} className="text-lg font-semibold text-slate-900">
          Have a link?
        </h2>
        <p className="mb-4 mt-0.5 text-sm text-slate-500">Check any specific notice by pasting its address.</p>
        {form}
        {picker}
      </div>
    </section>
  );
}
