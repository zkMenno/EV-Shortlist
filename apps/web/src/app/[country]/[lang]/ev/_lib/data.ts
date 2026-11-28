// Catalogue lookups for the ev pages (server only; reads go through getCatalogue()).
import type { ChangeMarker, Generation, GenerationYearCheck, GenerationYearsCorroboration, PublishedVariant } from "@ev/schema";
import type { Catalogue } from "@/lib/catalogue";
import { timelineOrder } from "@/lib/spec-diff";

export interface GenerationView {
  id: string;
  name: string;
  yearStart: number;
  yearEnd: number | null;
  uncertain: boolean;
  /** Years badge state (shared by model, generation and variant pages). */
  years: YearsStatus;
  changeMarkers: ChangeMarker[];
  rows: PublishedVariant[];
}

/** Generation entity from the catalogue, filled in from its rows when the release has none. */
export function generationView(cat: Catalogue, rows: PublishedVariant[]): GenerationView {
  const ordered = timelineOrder(rows);
  const first = ordered[0]!;
  const g: Generation | undefined = cat.generation(first.generation_id);
  const ends = ordered.map((r) => r.year_end ?? null);
  return {
    id: first.generation_id,
    name: g?.name ?? first.generation_name,
    yearStart: g?.year_start ?? Math.min(...ordered.map((r) => r.year_start)),
    yearEnd: g ? (g.year_end ?? null) : ends.includes(null) ? null : Math.max(...(ends as number[])),
    uncertain: g?.uncertain ?? !!first.generation_uncertain,
    years: yearsStatus(g?.uncertain ?? !!first.generation_uncertain, g?.years_corroboration),
    changeMarkers: [...(g?.change_markers ?? first.change_markers ?? [])].sort((a, b) => a.year - b.year),
    rows: ordered,
  };
}

/**
 * Years badge (T-061). An outside check (Wikidata, T-059) decides when there is one:
 * "corroborated" = every check agrees within the tolerance → "years checked against Wikidata";
 * "disagrees" = at least one check is off → "Wikidata disagrees" (details at Nerd level).
 * Without a check, the existing rule stays: `uncertain` → "years not yet checked", else no badge.
 * Years themselves never change because of a check.
 */
export type YearsStatus =
  | { kind: "none" }
  | { kind: "unchecked" }
  | { kind: "corroborated" | "disagrees"; tolerance: number; checks: GenerationYearCheck[] };

export function yearsStatus(uncertain: boolean, corroboration: GenerationYearsCorroboration | undefined): YearsStatus {
  if (corroboration?.checks.length) {
    return {
      kind: corroboration.corroborated && corroboration.checks.every((c) => c.agrees) ? "corroborated" : "disagrees",
      tolerance: corroboration.tolerance_years,
      checks: [...corroboration.checks],
    };
  }
  return uncertain ? { kind: "unchecked" } : { kind: "none" };
}

/** Rows grouped by generation, generations in year order. */
export function groupGenerations(cat: Catalogue, rows: PublishedVariant[]): GenerationView[] {
  const by = new Map<string, PublishedVariant[]>();
  for (const r of rows) by.set(r.generation_id, [...(by.get(r.generation_id) ?? []), r]);
  return [...by.values()].map((rs) => generationView(cat, rs)).sort((a, b) => a.yearStart - b.yearStart || a.name.localeCompare(b.name));
}

/** First row carrying a value for `key` (generation-level facts like registered_count_nl). */
export function firstWith<K extends keyof PublishedVariant>(rows: PublishedVariant[], key: K): PublishedVariant | undefined {
  return rows.find((r) => r[key] !== null && r[key] !== undefined);
}

/** Distinct non-empty values of a field across rows. */
export function distinct<K extends keyof PublishedVariant>(rows: PublishedVariant[], key: K): PublishedVariant[K][] {
  return [...new Set(rows.map((r) => r[key]).filter((v) => v !== null && v !== undefined))];
}

export { generationTitle } from "@/lib/generation-title";
