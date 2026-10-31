import { ImageResponse } from "next/og";

export const alt = "Pramaan — New rules, explained in your language, every line proved.";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

const TAGLINE = "New rules, explained in your language, every line proved.";
const TELUGU = "తెలుగు";

/** A subset of a Google font (only the glyphs in `text`) as TTF bytes, or null if it can't be fetched. */
async function loadFont(family: string, text: string): Promise<ArrayBuffer | null> {
  try {
    // no browser User-Agent: Google then answers with TTF, which is what the image renderer reads (not woff2)
    const css = await (await fetch(`https://fonts.googleapis.com/css2?family=${family}:wght@700&text=${encodeURIComponent(text)}`)).text();
    const url = css.match(/src: url\((.+?)\) format\('(?:opentype|truetype)'\)/)?.[1];
    if (!url) return null;
    const res = await fetch(url);
    return res.ok ? await res.arrayBuffer() : null;
  } catch {
    return null;
  }
}

export default async function OpengraphImage() {
  const telugu = await loadFont("Noto+Sans+Telugu", TELUGU);
  const fonts = [
    telugu && { name: "Noto Sans Telugu", data: telugu, weight: 700 as const, style: "normal" as const },
  ].filter((f): f is NonNullable<typeof f> => !!f);
  // Telugu renders correctly here. Devanagari does not: the renderer does not reorder the vowel sign "ि", so "हिंदी" came out
  // wrong. A mangled word is worse than none, so Hindi is written in Latin letters on this card.

  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          padding: "72px 80px",
          color: "white",
          background: "linear-gradient(135deg, #312e81 0%, #3730a3 55%, #4f46e5 100%)",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 24 }}>
          <svg width="96" height="96" viewBox="0 0 64 64">
            <rect width="64" height="64" rx="14" fill="rgba(255,255,255,0.16)" />
            <path d="M32 11 47 16.5v13.2c0 9.6-6.2 17.4-15 20.8-8.8-3.4-15-11.2-15-20.8V16.5L32 11Z" fill="none" stroke="#fff" strokeWidth="3.4" strokeLinejoin="round" />
            <path d="m24.5 31.5 5.6 5.6 10-11" fill="none" stroke="#fff" strokeWidth="3.6" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          <div style={{ fontSize: 84, fontWeight: 700, letterSpacing: -2 }}>Pramaan</div>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 28 }}>
          <div style={{ fontSize: 68, fontWeight: 700, lineHeight: 1.12, letterSpacing: -1.5, maxWidth: 1000 }}>{TAGLINE}</div>
          <div style={{ display: "flex", alignItems: "center", gap: 14, fontSize: 36, color: "#c7d2fe" }}>
            <span>Live · Verified ·</span>
            {telugu ? <span style={{ fontFamily: "Noto Sans Telugu" }}>{TELUGU}</span> : <span>Telugu</span>}
            <span>· Hindi · English</span>
          </div>
        </div>
      </div>
    ),
    { ...size, fonts },
  );
}
