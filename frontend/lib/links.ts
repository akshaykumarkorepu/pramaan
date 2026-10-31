// Client-side check for pasted links. The backend allowlist (and its redirect check) is still the final authority.
const ALLOWED_HOSTS = new Set(["rbi.org.in", "rbidocs.rbi.org.in", "sebi.gov.in", "pib.gov.in"]);

export const NOT_OFFICIAL = "Pramaan only reads official RBI, SEBI and PIB pages";

const TRAILING = /[.,;:!?)\]]+$/;

/**
 * First link in pasted text; trailing punctuation from a sentence is dropped. A bare address such as
 * "sebi.gov.in/legal/..." (no scheme) gets https:// prepended; the host allowlist still decides if it is accepted.
 */
export function extractFirstUrl(text: string): string | null {
  const m = text.match(/https?:\/\/[^\s<>"']+/i);
  if (m) return m[0].replace(TRAILING, "");
  const bare = text.match(/(?:^|[\s(<"'])((?:[a-z0-9-]+\.)+[a-z]{2,}(?::\d+)?(?:[/?#][^\s<>"']*)?)(?=$|[\s<>"'),;])/i); // must end the word, so "rbi.org.in@evil.com" is not cut down to "rbi.org.in"
  return bare ? "https://" + bare[1].replace(TRAILING, "") : null;
}

export type LinkCheck = { ok: true; url: string } | { ok: false; error: string };

export function validateOfficialUrl(raw: string): LinkCheck {
  const text = raw.trim();
  if (!text) return { ok: false, error: "Paste a link first" };
  const found = extractFirstUrl(text);
  if (!found) return { ok: false, error: "That doesn't look like a link. Paste the full address starting with https://" };
  let u: URL;
  try {
    u = new URL(found);
  } catch {
    return { ok: false, error: "That doesn't look like a valid link" };
  }
  const host = u.hostname.toLowerCase().replace(/^www\./, "");
  if (!ALLOWED_HOSTS.has(host)) return { ok: false, error: NOT_OFFICIAL };
  if (u.protocol !== "https:") return { ok: false, error: "Use the secure https:// address of the page" };
  return { ok: true, url: u.toString() };
}
