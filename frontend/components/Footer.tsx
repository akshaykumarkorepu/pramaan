import { ExternalLink } from "lucide-react";

export function Footer() {
  return (
    <footer className="mt-24 border-t border-slate-200 bg-white">
      <div className="mx-auto flex w-full max-w-[1100px] flex-col gap-3 px-4 py-8 text-sm text-slate-500 sm:px-6 md:flex-row md:items-center md:justify-between">
        <p>Independent tool. Not affiliated with RBI, SEBI or the Government of India.</p>
        <div className="flex flex-wrap items-center gap-x-5 gap-y-2">
          <a
            href="https://github.com/akshaykumarkorepu/pramaan"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 font-medium text-slate-700 transition-colors hover:text-brand"
          >
            GitHub <ExternalLink className="size-3.5" aria-hidden />
          </a>
          <span>Built at Forge &apos;26 by team CTRL + AI</span>
        </div>
      </div>
    </footer>
  );
}
