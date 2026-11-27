// "Most popular" sort (T-130, T-149, T-157, Decision 038 blend). Pure: safe on server and client.
// Release 4+ publishes `generations[].popularity` directly (computed in the pipeline with
// config/popularity.yaml). Older releases (1–3) without the field fall back to `rankGenerations()`
// from `src/config/popularity.generated.json` (D5 N-1). Ranked per generation: every variant of one
// generation shares its score and "#n popular".
import type { Generation } from "@ev/schema";

export interface PopularityInputs {
  schema?: "popularity-inputs/v1";
  weights: { registrations: number; owner_picks: number };
  inputs?: {
    top40_generated_on?: string | null;
    picks_imported?: string | null;
    registration_sources?: string[];
  };
  /** model id → registration score (% share of the BEV fleet, top40 method). */
  models: Record<string, number>;
  /** generation id → owner pick 0..1 (absent = no verdict). */
  generations: Record<string, number>;
}

export interface PopularityReleaseData {
  schema: "popularity-release/v1";
  release: number | null;
  weights: { registrations: number; owner_picks: number };
  inputs: {
    as_of: string | null;
    registration_sources: string[];
  };
  rankings: Record<string, { score: number; rank: number }>;
}

export type PopularityGenerated = PopularityReleaseData | PopularityInputs;

export interface Popularity {
  /** 0–100, one decimal. */
  score: number;
  /** 1 = most popular generation in this catalogue. */
  rank: number;
}

type PopRow = { model_id: string; generation_id: string; registered_count_nl?: number | null };
type PopGen = Pick<Generation, "id" | "popularity">;
const DATE_RE = /^\d{4}-\d{2}-\d{2}$/;

/**
 * Read `generations[].popularity` directly from a published release (T-149, T-157).
 * Returns an empty Map for older releases (1–3) or fixtures that lack the field.
 */
export function releasePopularity(generations: readonly PopGen[] | undefined): Map<string, Popularity> {
  if (!generations?.length) return new Map();
  const list: [string, Popularity][] = [];
  for (const g of generations) {
    const p = g.popularity;
    if (!p || typeof p.score !== "number" || !Number.isFinite(p.score) || p.score < 0) continue;
    if (typeof p.rank !== "number" || !Number.isInteger(p.rank) || p.rank < 1) continue;
    list.push([g.id, { score: p.score, rank: p.rank }]);
  }
  list.sort((a, b) => a[1].rank - b[1].rank || a[0].localeCompare(b[0]));
  return new Map(list);
}

/** Newest registration date across `generations[].popularity.as_of`, or null if absent. */
export function releasePopularityAsOf(generations: readonly PopGen[] | undefined): string | null {
  if (!generations?.length) return null;
  let newest: string | null = null;
  for (const g of generations) {
    const d = g.popularity?.as_of;
    if (typeof d === "string" && DATE_RE.test(d) && (newest === null || d > newest)) newest = d;
  }
  return newest;
}

/** Fallback `as_of` date from `popularity.generated.json` (release or legacy inputs schema). */
export function generatedAsOf(generated: PopularityGenerated | undefined): string | null {
  if (!generated?.inputs) return null;
  if ("as_of" in generated.inputs && typeof generated.inputs.as_of === "string") return generated.inputs.as_of;
  if ("top40_generated_on" in generated.inputs && typeof generated.inputs.top40_generated_on === "string") {
    return generated.inputs.top40_generated_on;
  }
  return null;
}

/**
 * Registration share per generation. top40 scores are per MODEL, so a model's share is split over its
 * generations in this catalogue by the release's own RDW count per generation (`registered_count_nl`,
 * counted at generation level). A generation without a count while its siblings have one gets none of
 * the share (not on Dutch roads in the RDW window). A model with no RDW count at all is split evenly.
 */
export function generationShares(rows: readonly PopRow[], models: Record<string, number>): Map<string, number> {
  const gens = new Map<string, { model: string; count: number | null }>();
  for (const r of rows) {
    const c = typeof r.registered_count_nl === "number" && r.registered_count_nl >= 0 ? r.registered_count_nl : null;
    const g = gens.get(r.generation_id);
    if (!g) gens.set(r.generation_id, { model: r.model_id, count: c });
    else if (c !== null) g.count = Math.max(g.count ?? 0, c);
  }
  const byModel = new Map<string, string[]>();
  for (const [id, g] of gens) (byModel.get(g.model) ?? byModel.set(g.model, []).get(g.model)!).push(id);
  const out = new Map<string, number>();
  for (const [model, ids] of byModel) {
    const reg = models[model];
    if (reg === undefined) continue;
    const total = ids.reduce((t, id) => t + (gens.get(id)!.count ?? 0), 0);
    for (const id of ids) out.set(id, total > 0 ? (reg * (gens.get(id)!.count ?? 0)) / total : reg / ids.length);
  }
  return out;
}

/**
 * Score (0–100, one decimal) and rank per generation id, over the generations present in `rows`.
 * Null score = neither registrations nor a pick known: no rank, sorts last. Ties keep a stable order by id.
 */
export function rankGenerations(rows: readonly PopRow[], inputs: PopularityInputs): Map<string, Popularity> {
  const shares = generationShares(rows, inputs.models);
  const max = Math.max(0, ...shares.values());
  const { registrations: wr, owner_picks: wp } = inputs.weights;
  const total = wr + wp;
  const scores = new Map<string, number>();
  if (total <= 0) return new Map();
  for (const r of rows) {
    if (scores.has(r.generation_id)) continue;
    const share = shares.get(r.generation_id);
    const pick = inputs.generations[r.generation_id];
    if (share === undefined && pick === undefined) continue;
    const s = (100 * (wr * (share !== undefined && max > 0 ? share / max : 0) + wp * (pick ?? 0))) / total;
    scores.set(r.generation_id, Math.round(s * 10) / 10);
  }
  const order = [...scores.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
  return new Map(order.map(([id, score], i) => [id, { score, rank: i + 1 }]));
}

/**
 * Resolve popularity for a catalogue:
 * 1. Release `generations[].popularity` when present (release 4+, T-149 / T-157).
 * 2. Build-time `popularity.generated.json`: `rankings` (release snapshot) or legacy `rankGenerations` (N-1).
 */
export function resolvePopularity(
  rows: readonly PopRow[],
  generations: readonly PopGen[] | undefined,
  generated?: PopularityGenerated,
): Map<string, Popularity> {
  const fromRel = releasePopularity(generations);
  if (fromRel.size > 0) return fromRel;
  if (!generated) return new Map();
  if ("rankings" in generated && generated.rankings) {
    const present = new Set(rows.map((r) => r.generation_id));
    const list: [string, Popularity][] = [];
    for (const id of present) {
      const p = generated.rankings[id];
      if (p && typeof p.score === "number" && Number.isFinite(p.score) && typeof p.rank === "number" && p.rank >= 1) {
        list.push([id, { score: p.score, rank: p.rank }]);
      }
    }
    list.sort((a, b) => a[1].rank - b[1].rank || a[0].localeCompare(b[0]));
    return new Map(list);
  }
  if ("models" in generated && "generations" in generated) {
    return rankGenerations(rows, generated);
  }
  return new Map();
}
