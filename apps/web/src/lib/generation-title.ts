import type { PublishedVariant } from "@ev/schema";

/**
 * "Make Model Generation" without repeating names: generation names often already hold the
 * model ("e-tron (GE)") or even the make ("Honda e").
 * Shared by page titles and photo alt text (T-135 review S1), so it lives in src/lib (client-safe).
 */
export function generationTitle(r: Pick<PublishedVariant, "make_name" | "model_name" | "generation_name">): string {
  const g = r.generation_name;
  const lower = g.toLowerCase();
  if (lower.startsWith(r.make_name.toLowerCase())) return g;
  if (r.model_name.length >= 2 && lower.includes(r.model_name.toLowerCase())) return `${r.make_name} ${g}`;
  return `${r.make_name} ${r.model_name} ${g}`;
}
