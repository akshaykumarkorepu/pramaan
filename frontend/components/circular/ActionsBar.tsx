"use client";

import { CalendarPlus, FlaskConical, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

export function ActionsBar({
  hasDeadlines,
  icsHref,
  onTest,
  testing,
  testOn,
}: {
  hasDeadlines: boolean;
  icsHref: string;
  onTest: () => void;
  testing: boolean;
  testOn: boolean;
}) {
  return (
    <div className="flex flex-col gap-3 sm:flex-row">
      <Button variant="outline" onClick={onTest} disabled={testing} className="h-11 gap-2 bg-white px-5 text-[15px]">
        {testing && testOn ? <Loader2 className="animate-spin" aria-hidden /> : <FlaskConical aria-hidden />}
        Test the verifier
      </Button>
      {hasDeadlines ? (
        <a
          href={icsHref}
          download
          className="inline-flex h-11 items-center justify-center gap-2 rounded-lg border border-border bg-white px-5 text-[15px] font-medium transition-colors hover:bg-muted"
        >
          <CalendarPlus className="size-4" aria-hidden /> Add deadlines to calendar
        </a>
      ) : (
        <Tooltip>
          {/* a disabled button swallows hover, so the tooltip hangs off a focusable wrapper */}
          <TooltipTrigger render={<span tabIndex={0} className="inline-flex rounded-lg" />}>
            <Button variant="outline" disabled className="h-11 gap-2 bg-white px-5 text-[15px]">
              <CalendarPlus aria-hidden /> Add deadlines to calendar
            </Button>
          </TooltipTrigger>
          <TooltipContent>No verified deadlines in this notice</TooltipContent>
        </Tooltip>
      )}
    </div>
  );
}
