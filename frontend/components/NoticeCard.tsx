"use client";

import Link from "next/link";
import { motion, useReducedMotion } from "motion/react";
import { Calendar, Clock, ExternalLink } from "lucide-react";
import { APPLIES_STATUS, SOURCE_STYLE } from "@/components/status";
import { ago, formatDate } from "@/lib/time";
import { cn } from "@/lib/utils";
import type { Lang, Notice, ProfileId } from "@/lib/types";

export function NoticeCard({
  notice,
  profile,
  lang,
  now,
  index,
}: {
  notice: Notice;
  profile: ProfileId;
  lang: Lang;
  now: number;
  index: number;
}) {
  const reduce = useReducedMotion();
  const src = SOURCE_STYLE[notice.source];
  const applies = APPLIES_STATUS[notice.applies];
  const href = `/circular?${new URLSearchParams({ url: notice.url, profile, lang })}`;

  const body = (
    <div
      className={cn(
        "group relative flex h-full flex-col gap-3 rounded-2xl border border-slate-200 bg-white p-5 shadow-soft transition-shadow hover:shadow-lift",
        "focus-within:ring-2 focus-within:ring-ring",
      )}
    >
      <div className="flex items-center justify-between gap-2">
        <span className={cn("rounded-full border px-2 py-0.5 text-xs font-semibold", src.badge)}>{src.label}</span>
        <span className={cn("rounded-full border px-2.5 py-0.5 text-xs font-medium", applies.badge)}>{applies.label}</span>
      </div>

      <h3 className="line-clamp-2 text-[15px] font-semibold leading-snug text-slate-900">
        {/* stretched link: the whole card is clickable, while "Open original" below stays a separate, higher link */}
        <Link href={href} className="outline-none after:absolute after:inset-0 after:rounded-2xl after:content-['']">
          {notice.title}
        </Link>
      </h3>

      <p className="text-[13px] leading-relaxed text-slate-500">{notice.reason}</p>

      <div className="mt-auto flex flex-wrap items-center justify-between gap-x-4 gap-y-2 pt-1 text-xs text-slate-500">
        <span className="flex flex-wrap items-center gap-x-3 gap-y-1">
          <span className="inline-flex items-center gap-1">
            <Calendar className="size-3.5" aria-hidden />
            {formatDate(notice.date)}
          </span>
          <span className="inline-flex items-center gap-1">
            <Clock className="size-3.5" aria-hidden />
            {ago(notice.fetched_at, now) || "…"}
          </span>
        </span>
        <a
          href={notice.url}
          target="_blank"
          rel="noopener noreferrer"
          className="relative z-10 inline-flex items-center gap-1 rounded-md px-1 py-0.5 font-medium text-brand hover:underline"
        >
          Open original <ExternalLink className="size-3" aria-hidden />
        </a>
      </div>
    </div>
  );

  if (reduce) return <div role="listitem">{body}</div>;
  return (
    <motion.div
      role="listitem"
      layout
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, scale: 0.97 }}
      transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1], delay: Math.min(index, 8) * 0.04 }}
      whileHover={{ y: -3, transition: { duration: 0.15, delay: 0 } }}
    >
      {body}
    </motion.div>
  );
}
