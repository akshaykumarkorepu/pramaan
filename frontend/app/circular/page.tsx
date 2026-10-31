import { Suspense } from "react";
import Link from "next/link";
import { ArrowLeft, ExternalLink } from "lucide-react";
import { FadeIn } from "@/components/motion/FadeIn";

export const metadata = { title: "Circular — Pramaan" };

const one = (v: string | string[] | undefined) => (Array.isArray(v) ? v[0] : v) ?? "";

// F3 placeholder: the live analysis view lands here. For now it just shows what it was opened with.
type SP = Promise<Record<string, string | string[] | undefined>>;

export default function CircularPage({ searchParams }: { searchParams: SP }) {
  // reading searchParams is request-time data, so it sits inside Suspense and the page shell can still prerender
  return (
    <Suspense fallback={<div className="mx-auto h-64 max-w-[1100px] px-4 sm:px-6" />}>
      <CircularDetails searchParams={searchParams} />
    </Suspense>
  );
}

async function CircularDetails({ searchParams }: { searchParams: SP }) {
  const sp = await searchParams;
  const url = one(sp.url);
  const profile = one(sp.profile);
  const lang = one(sp.lang);
  // only offer a clickable link for http(s) addresses
  const safe = /^https?:\/\//i.test(url);
  return (
    <div className="mx-auto w-full max-w-[1100px] px-4 py-14 sm:px-6">
      <FadeIn>
        <Link href="/" className="inline-flex items-center gap-1.5 text-sm font-medium text-brand hover:underline">
          <ArrowLeft className="size-4" aria-hidden /> Back to notices
        </Link>
        <h1 className="mt-6 text-3xl font-bold text-slate-900 sm:text-4xl">Circular analysis</h1>
        <p className="mt-3 max-w-2xl text-slate-600">The live, line-by-line verified view arrives in the next release.</p>
        <dl className="mt-8 grid gap-4 rounded-2xl border border-slate-200 bg-white p-5 text-sm shadow-soft sm:grid-cols-[120px_1fr]">
          <dt className="font-medium text-slate-500">Profile</dt>
          <dd className="text-slate-900">{profile || "—"}</dd>
          <dt className="font-medium text-slate-500">Language</dt>
          <dd className="text-slate-900">{lang || "—"}</dd>
          <dt className="font-medium text-slate-500">Notice</dt>
          <dd className="break-all text-slate-900">
            {safe ? (
              <a href={url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-brand hover:underline">
                {url} <ExternalLink className="size-3.5 shrink-0" aria-hidden />
              </a>
            ) : (
              url || "—"
            )}
          </dd>
        </dl>
      </FadeIn>
    </div>
  );
}
