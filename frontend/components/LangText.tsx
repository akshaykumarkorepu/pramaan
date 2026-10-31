import { cn } from "@/lib/utils";
import type { Lang } from "@/lib/types";
import type { ElementType, ReactNode } from "react";

const FONT: Record<Lang, string> = {
  en: "",
  te: "font-telugu",
  hi: "font-deva",
};

/** Wrap any Telugu/Hindi text so it gets the right `lang` attribute and font (no tofu boxes). */
export function LangText({
  lang,
  as: Tag = "span",
  className,
  children,
}: {
  lang: Lang;
  as?: ElementType;
  className?: string;
  children: ReactNode;
}) {
  return (
    <Tag lang={lang} className={cn(FONT[lang], lang !== "en" && "leading-relaxed", className)}>
      {children}
    </Tag>
  );
}
