// Licence deed links for photo credits (T-169; CC BY needs a link to the licence, Decision 081).
// Client-safe and tiny: pages pass the release's SPDX-style id ("CC-BY-SA-4.0"), not a URL.

const CC = /^CC-(BY(?:-SA|-ND|-NC|-NC-SA|-NC-ND)?)-(\d\.\d)(?:-([A-Z]{2}))?$/;

/** creativecommons.org deed for a CC licence id, or null (public domain, press kits, unknown ids). */
export function licenceUrl(id: string | null | undefined): string | null {
  if (!id) return null;
  if (id === "CC0-1.0") return "https://creativecommons.org/publicdomain/zero/1.0/";
  const m = CC.exec(id);
  if (!m) return null;
  const port = m[3] ? `${m[3].toLowerCase()}/` : "";
  return `https://creativecommons.org/licenses/${m[1]!.toLowerCase()}/${m[2]}/${port}`;
}
