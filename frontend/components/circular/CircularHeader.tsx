"use client";

import Link from "next/link";
import { ArrowLeft, ExternalLink } from "lucide-react";
import { PasteLink } from "@/components/PasteLink";
import { SOURCE_STYLE } from "@/components/status";
import { LangText } from "@/components/LangText";
import { ShimmerSkeleton } from "@/components/motion/ShimmerSkeleton";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { sourceFromUrl } from "@/lib/circular";
import { ago, useNow } from "@/lib/time";
import { LANGS, PROFILES, isLang } from "@/lib/profile";
import type { Lang, ProfileId } from "@/lib/types";
import { cn } from "@/lib/utils";

export function CircularHeader({
  title,
  fetchedAt,
  url,
  profile,
  lang,
  onLang,
  onAnother,
}: {
  title: string | null;
  fetchedAt: string | null; // when the server really read the document; shown so a cached result never looks fresher than it is
  url: string;
  profile: ProfileId;
  lang: Lang;
  onLang: (l: Lang) => void;
  onAnother: (url: string) => void;
}) {
  const now = useNow();
  const src = sourceFromUrl(url);
  const p = PROFILES.find((x) => x.id === profile);
  return (
    <header>
      <Link href="/" className="inline-flex min-h-10 items-center gap-1.5 text-sm font-medium text-brand hover:underline">
        <ArrowLeft className="size-4" aria-hidden /> All notices
      </Link>
      <div className="mt-3 flex flex-wrap items-center gap-2">
        {src && <span className={cn("rounded-full border px-2 py-0.5 text-xs font-semibold", SOURCE_STYLE[src].badge)}>{SOURCE_STYLE[src].label}</span>}
        {p && (
          <span className="inline-flex items-center gap-1.5 rounded-full border border-slate-200 bg-white px-2.5 py-0.5 text-xs font-medium text-slate-700">
            <p.icon className="size-3.5 text-brand" aria-hidden /> {p.label}
          </span>
        )}
        <a href={url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 rounded-md px-1 text-xs font-medium text-brand hover:underline">
          Open original <ExternalLink className="size-3" aria-hidden />
        </a>
        {fetchedAt && <span className="text-xs text-slate-500">· {ago(fetchedAt, now)}</span>}
      </div>
      {title ? (
        <h1 className="mt-3 text-balance text-2xl font-bold leading-tight text-slate-900 sm:text-3xl">{title}</h1>
      ) : (
        <div className="mt-3 space-y-2" aria-label="Loading title">
          <ShimmerSkeleton className="h-7 w-full max-w-xl" />
          <ShimmerSkeleton className="h-7 w-2/3 max-w-md" />
        </div>
      )}
      <PasteLink variant="compact" profile={profile} onGo={onAnother} />
      <ToggleGroup
        value={[lang]}
        onValueChange={(v) => {
          if (isLang(v[0])) onLang(v[0]);
        }}
        variant="outline"
        spacing={0}
        aria-label="Language"
        className="mt-5 w-full rounded-lg bg-white sm:w-fit"
      >
        {LANGS.map((l) => (
          <ToggleGroupItem key={l.id} value={l.id} className="h-10 flex-1 px-4 text-[15px] aria-pressed:bg-brand aria-pressed:text-white sm:flex-none">
            <LangText lang={l.id}>{l.label}</LangText>
          </ToggleGroupItem>
        ))}
      </ToggleGroup>
    </header>
  );
}
