import { Suspense } from "react";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { CircularView } from "@/components/circular/CircularView";
import { isLang, isProfile } from "@/lib/profile";

export const metadata = { title: "Circular — Pramaan" };

type SP = Promise<Record<string, string | string[] | undefined>>;
const one = (v: string | string[] | undefined) => (Array.isArray(v) ? v[0] : v) ?? "";

export default function CircularPage({ searchParams }: { searchParams: SP }) {
  // reading searchParams is request-time data, so it sits inside Suspense and the page shell can still prerender
  return (
    <Suspense fallback={<div className="mx-auto h-96 max-w-[1100px] px-4 sm:px-6" />}>
      <Circular searchParams={searchParams} />
    </Suspense>
  );
}

async function Circular({ searchParams }: { searchParams: SP }) {
  const sp = await searchParams;
  const url = one(sp.url).trim();
  const profile = one(sp.profile);
  const lang = one(sp.lang) || "en";

  const problem = !/^https?:\/\//i.test(url)
    ? "This page needs a link to an RBI, SEBI or PIB notice. Open one from the notices list."
    : !isProfile(profile)
      ? "Choose who you are (NBFC, co-operative bank, research analyst, stock broker or citizen) on the home page first."
      : !isLang(lang)
        ? "Choose English, Telugu or Hindi on the home page."
        : null;

  if (problem || !isProfile(profile) || !isLang(lang)) {
    return (
      <div className="mx-auto w-full max-w-[1100px] px-4 py-16 sm:px-6">
        <div role="alert" className="max-w-xl rounded-2xl border border-slate-200 bg-white p-6 shadow-soft">
          <p className="text-base font-semibold text-slate-900">We can&apos;t open this page yet</p>
          <p className="mt-2 text-[15px] text-slate-600">{problem}</p>
          <Link href="/" className="mt-5 inline-flex items-center gap-1.5 text-sm font-medium text-brand hover:underline">
            <ArrowLeft className="size-4" aria-hidden /> All notices
          </Link>
        </div>
      </div>
    );
  }
  return <CircularView key={url} url={url} profile={profile} initialLang={lang} />;
}
