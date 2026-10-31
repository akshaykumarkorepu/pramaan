"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ttsUrl } from "./api";
import type { Lang } from "./types";

export type SpeechState = "idle" | "loading" | "playing" | "paused" | "error";

const BCP: Record<Lang, string> = { en: "en-IN", te: "te-IN", hi: "hi-IN" };

/** Split into short pieces: Chrome stops long utterances after ~15 s, and /tts accepts at most 1200 characters. */
export function chunkText(text: string, max: number): string[] {
  const sentences = text.split(/(?<=[.!?।])\s+/).filter(Boolean);
  const out: string[] = [];
  let cur = "";
  for (const s of sentences) {
    if (cur && cur.length + s.length + 1 > max) {
      out.push(cur);
      cur = "";
    }
    cur = cur ? `${cur} ${s}` : s;
    while (cur.length > max) {
      out.push(cur.slice(0, max));
      cur = cur.slice(max);
    }
  }
  if (cur) out.push(cur);
  return out;
}

async function pickVoice(lang: Lang): Promise<SpeechSynthesisVoice | null> {
  if (typeof window === "undefined" || !("speechSynthesis" in window)) return null;
  const find = () => {
    const vs = window.speechSynthesis.getVoices();
    const want = BCP[lang].toLowerCase();
    return vs.find((v) => v.lang.replace("_", "-").toLowerCase() === want) ?? vs.find((v) => v.lang.toLowerCase().startsWith(lang)) ?? null;
  };
  const now = find();
  if (now || window.speechSynthesis.getVoices().length) return now;
  // voices load asynchronously in some browsers
  return new Promise((resolve) => {
    const done = () => {
      window.speechSynthesis.removeEventListener("voiceschanged", done);
      resolve(find());
    };
    window.speechSynthesis.addEventListener("voiceschanged", done);
    setTimeout(done, 700);
  });
}

/**
 * Reads `text` aloud: the browser's own te-IN / hi-IN / en-IN voice when one is installed, otherwise the
 * backend's gTTS mp3 (/tts). `mode` says which one was used.
 */
export function useSpeech(text: string, lang: Lang) {
  const [state, setState] = useState<SpeechState>("idle");
  const [error, setError] = useState<string | null>(null);
  const [mode, setMode] = useState<"browser" | "server" | null>(null);
  const ctl = useRef<{ pause: () => void; resume: () => void; stop: () => void } | null>(null);
  const token = useRef(0);

  const stop = useCallback(() => {
    token.current += 1; // invalidates callbacks of the run being stopped
    ctl.current?.stop();
    ctl.current = null;
    setState("idle");
  }, []);

  // a new text or language must never keep talking
  useEffect(() => stop, [text, lang, stop]);

  const play = useCallback(async () => {
    stop();
    const me = token.current;
    setError(null);
    setState("loading");
    const voice = await pickVoice(lang);
    if (me !== token.current) return;

    const fail = (msg: string) => {
      if (me !== token.current) return;
      setError(msg);
      setState("error");
    };

    if (voice) {
      setMode("browser");
      const synth = window.speechSynthesis;
      const parts = chunkText(text, 220);
      synth.cancel();
      const speak = (i: number) => {
        if (me !== token.current) return;
        if (i >= parts.length) {
          setState("idle");
          return;
        }
        const u = new SpeechSynthesisUtterance(parts[i]);
        u.voice = voice;
        u.lang = voice.lang;
        u.onstart = () => me === token.current && setState("playing");
        u.onend = () => speak(i + 1);
        u.onerror = (ev) => {
          if (ev.error === "canceled" || ev.error === "interrupted") return;
          fail("Your browser could not read this aloud.");
        };
        synth.speak(u);
      };
      ctl.current = {
        pause: () => {
          synth.pause();
          setState("paused");
        },
        resume: () => {
          synth.resume();
          setState("playing");
        },
        stop: () => synth.cancel(),
      };
      speak(0);
      return;
    }

    setMode("server");
    const parts = chunkText(text, 1000);
    const audio = new Audio();
    const next = (i: number) => {
      if (me !== token.current) return;
      if (i >= parts.length) {
        setState("idle");
        return;
      }
      audio.src = ttsUrl(parts[i], lang);
      audio.onplaying = () => me === token.current && setState("playing");
      audio.onended = () => next(i + 1);
      audio.onerror = () => fail("Couldn't load the audio. Please try again.");
      audio.play().catch(() => fail("Couldn't play the audio. Please try again."));
    };
    ctl.current = {
      pause: () => {
        audio.pause();
        setState("paused");
      },
      resume: () => {
        audio.play().catch(() => fail("Couldn't play the audio. Please try again."));
        setState("playing");
      },
      stop: () => {
        audio.pause();
        audio.removeAttribute("src");
      },
    };
    next(0);
  }, [lang, stop, text]);

  const toggle = useCallback(() => {
    if (state === "playing") ctl.current?.pause();
    else if (state === "paused") ctl.current?.resume();
    else if (state === "idle" || state === "error") void play();
  }, [play, state]);

  return { state, error, mode, toggle, stop };
}
