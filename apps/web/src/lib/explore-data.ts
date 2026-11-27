// Compact rows shipped to the browser for Explore. Same field names as PublishedVariant,
// only the columns Explore needs, nulls dropped. Pure: safe on server and client.
import type { FieldProvenance, PublishedVariant, Source } from "@ev/schema";
import type { Popularity } from "./popularity";
import type { CompactScores, ReleaseScores, VariantScores } from "./release-scores";
import type { CompactBand, CompactBands, PriceHow, VariantBand, VariantUsedPrices } from "./variant-prices";

/** Flags on a compact band: estimate (basis), low confidence, generation-scope band (Decision 069). */
export const BAND_ESTIMATE = 1;
export const BAND_LOW = 2;
export const BAND_GENERATION = 4;

export const EXPLORE_FIELDS = [
  "variant_id",
  "variant_name",
  "generation_id",
  "generation_name",
  "model_id",
  "model_name",
  "make_id",
  "make_name",
  "year_start",
  "year_end",
  "era",
  "segment",
  "body",
  "real_range_km",
  "real_range_rung",
  // T-130 cards: winter estimate (-5 °C and colder, mixed driving), with its own provenance.
  "real_range_winter_km",
  "battery_kwh_net",
  // Trip fit (T-036): WLTP battery consumption = usable kWh / WLTP km (fallback: published consumption).
  "wltp_range_km",
  "consumption_kwh_100km",
  "dc_km_per_20min",
  "dc_km_per_10min",
  "dc_peak_kw",
  "dc_peak_kw_is_claim",
  "dc_speed_is_claim",
  // Not shown in Explore; carried so hasDcData() (src/lib/dc.ts) gives the same answer as on spec pages.
  "dc_avg_10_80_kw",
  "dc_minutes_10_80",
  "ac_km_per_h",
  "boot_l",
  "length_mm",
  "towing_kg",
  "price_new",
  "registered_count_nl",
  "quality_tier",
  // Decision 010
  "voltage_class_id",
  "voltage_nominal_v",
  "voltage_label",
  "charger_400v_mode",
  "charger_400v_kw",
  "fast_on_400v",
  "chemistry_id",
  "cooling_id",
  "cell_format",
  "charge_100_daily",
  "platform_name",
  "battery_pack_id",
  // Hero shortlist scoring (T-080, shortlist rules): AC speed, heat pump, seats, mass, new or used.
  "ac_kw",
  "heat_pump",
  "seats",
  "kerb_mass_kg",
  "mass_running_order_kg",
  "on_sale_new",
] as const satisfies readonly (keyof PublishedVariant)[];

/** Numeric fields that carry provenance in the client JSON. */
const NUMERIC = new Set<string>([
  "real_range_km",
  "real_range_winter_km",
  "battery_kwh_net",
  // T-143 (Decision 085): the official WLTP range shows next to the real range, so it ships with its provenance.
  "wltp_range_km",
  // consumption_kwh_100km ships without provenance: Explore never shows it, it only feeds the trip
  // estimate, which carries its own "fixture matrix" provenance (T-036).
  "dc_km_per_20min",
  "dc_km_per_10min",
  "dc_peak_kw",
  "ac_km_per_h",
  "boot_l",
  "length_mm",
  "towing_kg",
  "registered_count_nl",
  "voltage_nominal_v",
  "charger_400v_kw",
]);

export type ExploreRow = Pick<PublishedVariant, (typeof EXPLORE_FIELDS)[number]> & {
  provenance: Record<string, FieldProvenance>;
  /** Used price bands by build year and country (T-081), compact; absent without data. */
  used_bands?: CompactBands;
  /** Shortlist scores from the release (T-114, Decision 065), compact; absent without data. */
  shortlist?: CompactScores;
  /** "Most popular" score 0–100 of the row's generation (T-130); absent when unknown. */
  pop?: number;
  /** Popularity rank of the row's generation (1 = most popular); absent when unknown. */
  pop_rank?: number;
};

export interface ClientCatalogue {
  release: number;
  /** The release has shortlist_scores.json (else the hero says "ranking not available yet"). */
  scores: boolean;
  /** source id → display name, for the provenance popovers. */
  sources: Record<string, string>;
  rows: ExploreRow[];
}

export function toExploreRow(
  row: PublishedVariant,
  used?: VariantUsedPrices,
  scores?: ReleaseScores | null,
  popularity?: Map<string, Popularity>,
): ExploreRow {
  const out: Record<string, unknown> = {};
  for (const f of EXPLORE_FIELDS) {
    const v = row[f];
    if (v !== null && v !== undefined) out[f] = v;
  }
  const prov: Record<string, FieldProvenance> = {};
  for (const [k, p] of Object.entries(row.provenance ?? {})) {
    if (NUMERIC.has(k) || k.startsWith("price_new")) {
      // fact_ids stay on the server (catalogue.json / per-generation detail); Explore never reads them (T-167 perf budget).
      const compact: FieldProvenance = { ...p };
      delete compact.fact_ids;
      prov[k] = compact;
    }
  }
  out.provenance = prov;
  const bands = compactBands(used?.get(row.variant_id));
  if (bands) out.used_bands = bands;
  const ss = compactScores(scores?.variants.get(row.variant_id));
  if (ss) out.shortlist = ss;
  const pop = popularity?.get(row.generation_id);
  if (pop) {
    out.pop = pop.score;
    out.pop_rank = pop.rank;
  }
  return out as ExploreRow;
}

export function sourceNames(sources: Source[]): Record<string, string> {
  return Object.fromEntries(sources.map((s) => [s.id, s.name]));
}

export function toClientCatalogue(
  release: number,
  sources: Source[],
  rows: PublishedVariant[],
  used?: VariantUsedPrices,
  scores?: ReleaseScores | null,
  popularity?: Map<string, Popularity>,
): ClientCatalogue {
  return { release, scores: !!scores, sources: sourceNames(sources), rows: rows.map((r) => toExploreRow(r, used, scores, popularity)) };
}

/** How the band was made, from the row's own fields (Decision 064, Nerd mode); undefined when nothing is known. */
function priceHow(b: VariantBand): PriceHow | undefined {
  const h: PriceHow = {};
  if (b.source) {
    h.src = b.source.name;
    if (b.source.url) h.url = b.source.url;
    if (b.source.ref) h.ref = b.source.ref;
  }
  if (b.date) h.date = b.date;
  if (b.basis === "band" && b.samples > 0) h.n = b.samples;
  if (b.curve) h.curve = b.curve;
  if (b.curve_fitted_on.length) h.on = b.curve_fitted_on;
  if (b.list_price !== null) h.list = b.list_price;
  if (b.list_source_ids.length) h.ls = b.list_source_ids;
  if (b.kept_share !== null) h.kept = b.kept_share;
  return Object.keys(h).length ? h : undefined;
}

/** Compact per-row bands for the client catalogue (T-092). */
export function compactBands(per: Record<string, VariantBand[]> | undefined): CompactBands | undefined {
  if (!per) return undefined;
  const out: CompactBands = {};
  for (const [cc, list] of Object.entries(per)) {
    out[cc] = list.map((b) => {
      const flags = (b.basis === "estimate" ? BAND_ESTIMATE : 0) | (b.confidence === "low" ? BAND_LOW : 0) | (b.scope === "generation" ? BAND_GENERATION : 0);
      const how = priceHow(b);
      const row: CompactBand = how ? [b.build_year, b.p25, b.median, b.p75, flags, how] : [b.build_year, b.p25, b.median, b.p75, flags];
      return row;
    });
  }
  return out;
}

/** Compact per-row shortlist scores for the client catalogue (T-114). */
export function compactScores(v: VariantScores | undefined): CompactScores | undefined {
  if (!v) return undefined;
  const s: CompactScores["s"] = {};
  for (const [k, c] of Object.entries(v.scores)) s[k] = [c.score, c.band, ...c.reasons];
  const out: CompactScores = { s };
  const f: NonNullable<CompactScores["f"]> = {};
  for (const [trip, fs] of Object.entries(v.factors)) {
    const known = Object.entries(fs).filter((e): e is [string, number] => e[1] !== null);
    if (known.length) f[trip] = Object.fromEntries(known);
  }
  if (Object.keys(f).length) out.f = f;
  const u = Object.fromEntries(Object.entries(v.unknown).filter(([, l]) => l.length));
  if (Object.keys(u).length) out.u = u;
  if (Object.keys(v.derived).length) out.d = { ...v.derived };
  return out;
}
