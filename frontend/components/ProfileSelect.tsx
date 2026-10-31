"use client";

import type { Ref } from "react";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { PROFILES, isProfile } from "@/lib/profile";
import type { ProfileId } from "@/lib/types";

/** The "I am a…" dropdown, shared by the home control panel and the paste-a-link card. */
export function ProfileSelect({
  profile,
  onProfile,
  invalid,
  triggerRef,
}: {
  profile: ProfileId | null;
  onProfile: (p: ProfileId) => void;
  invalid?: boolean;
  triggerRef?: Ref<HTMLButtonElement>;
}) {
  return (
    <Select
      value={profile}
      onValueChange={(v) => {
        if (isProfile(v)) onProfile(v);
      }}
    >
      <SelectTrigger ref={triggerRef} aria-label="Who are you" aria-invalid={invalid} className="h-11 w-full bg-white text-[15px]">
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
  );
}
