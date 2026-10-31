"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { motion } from "motion/react";
import { ShieldCheck } from "lucide-react";
import { cn } from "@/lib/utils";

const NAV = [
  { href: "/", label: "Home" },
  { href: "/how-it-works", label: "How it works" },
];

export function Header() {
  const pathname = usePathname();
  return (
    <header className="glass sticky top-0 z-40 border-b border-slate-200/70">
      <div className="mx-auto flex h-14 w-full max-w-[1100px] items-center justify-between px-4 sm:px-6">
        <Link href="/" className="group flex items-center gap-2 font-semibold tracking-tight text-slate-900">
          <span className="flex size-7 items-center justify-center rounded-lg bg-gradient-accent text-white shadow-sm transition-transform group-hover:scale-105">
            <ShieldCheck className="size-4" aria-hidden />
          </span>
          Pramaan
        </Link>
        <nav className="flex items-center gap-1" aria-label="Main">
          {NAV.map((n) => {
            const active = n.href === "/" ? pathname === "/" : pathname.startsWith(n.href);
            return (
              <Link
                key={n.href}
                href={n.href}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "relative rounded-lg px-3 py-1.5 text-sm font-medium transition-colors",
                  active ? "bg-brand-soft text-brand" : "text-slate-600 hover:bg-slate-100 hover:text-slate-900",
                )}
              >
                {n.label}
                {active && <motion.span layoutId="nav-active" className="absolute inset-x-3 -bottom-[7px] h-0.5 rounded-full bg-gradient-accent" />}
              </Link>
            );
          })}
        </nav>
      </div>
    </header>
  );
}
