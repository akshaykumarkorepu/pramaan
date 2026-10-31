"use client";

import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { SOURCE_STYLE } from "@/components/status";
import type { SourceId } from "@/lib/types";

export type Tab = "all" | "yes" | "review";
const TABS: { id: Tab; label: string }[] = [
  { id: "all", label: "All" },
  { id: "yes", label: "Applies to you" },
  { id: "review", label: "Needs review" },
];
const SOURCE_IDS: SourceId[] = ["rbi", "sebi", "pib"];

const pill =
  "h-9 rounded-full border border-slate-200 bg-white px-3.5 text-[13px] aria-pressed:border-brand aria-pressed:bg-brand aria-pressed:text-white";

export function NoticeFilters({
  tab,
  onTab,
  counts,
  sources,
  onSources,
}: {
  tab: Tab;
  onTab: (t: Tab) => void;
  counts: Record<Tab, number>;
  sources: SourceId[];
  onSources: (s: SourceId[]) => void;
}) {
  return (
    <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
      <ToggleGroup
        value={[tab]}
        onValueChange={(v) => {
          if (v[0]) onTab(v[0] as Tab);
        }}
        spacing={2}
        aria-label="Filter by applicability"
        className="flex-wrap"
      >
        {TABS.map((t) => (
          <ToggleGroupItem key={t.id} value={t.id} className={pill}>
            {t.label}
            <span className="ml-1 tabular-nums opacity-70">{counts[t.id]}</span>
          </ToggleGroupItem>
        ))}
      </ToggleGroup>
      {/* multi-select; none pressed = all sources */}
      <ToggleGroup
        multiple
        value={sources}
        onValueChange={(v) => onSources(v as SourceId[])}
        spacing={2}
        aria-label="Filter by source"
        className="flex-wrap"
      >
        {SOURCE_IDS.map((id) => (
          <ToggleGroupItem key={id} value={id} className={pill}>
            {SOURCE_STYLE[id].label}
          </ToggleGroupItem>
        ))}
      </ToggleGroup>
    </div>
  );
}
