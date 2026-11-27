// One rule for "does this car have DC charging data?" (T-009/T-010 review). Without a DC figure we
// must never describe how the car behaves on DC chargers ("native", "booster · 50 kW", "fast on
// 400 V: yes"): those fields read as missing. Used by Explore, SpecValue, cellValue() (spec diff and
// compare) and the generation key facts. Pure: safe on server and client.
import type { PublishedVariant } from "@ev/schema";

/** DC figures that count as "we know something about DC charging". */
export const DC_FIGURE_KEYS = ["dc_peak_kw", "dc_avg_10_80_kw", "dc_minutes_10_80"] as const;

/** Fields that describe DC behaviour and are only shown when the car has DC data. */
export const DC_DEPENDENT_KEYS = ["charger_400v_mode", "charger_400v_kw", "fast_on_400v"] as const;

export type DcDependentKey = (typeof DC_DEPENDENT_KEYS)[number];

type DcRow = Partial<Pick<PublishedVariant, (typeof DC_FIGURE_KEYS)[number]>>;

const positive = (v: unknown): boolean => typeof v === "number" && Number.isFinite(v) && v > 0;

/** True when the row has at least one positive DC figure (peak kW, 10-80 % average kW or minutes). */
export function hasDcData(row: DcRow): boolean {
  return DC_FIGURE_KEYS.some((k) => positive(row[k]));
}

export function isDcDependent(key: string): key is DcDependentKey {
  return (DC_DEPENDENT_KEYS as readonly string[]).includes(key);
}

/** DC speed fields that carry the maker-claim badge when `dc_speed_is_claim: true` (T-157). */
export const DC_SPEED_CLAIM_KEYS = [
  "dc_avg_10_80_kw",
  "dc_minutes_10_80",
  "dc_km_per_10min",
  "dc_km_per_20min",
] as const;

export type DcSpeedClaimKey = (typeof DC_SPEED_CLAIM_KEYS)[number];

type ClaimRow = Partial<Pick<PublishedVariant, "dc_peak_kw_is_claim" | "dc_speed_is_claim">>;

/** True when `key` on `row` is a maker claim rather than a measured or curve-modelled figure. */
export function isClaimField(row: ClaimRow, key: string): boolean {
  if (key === "dc_peak_kw") return !!row.dc_peak_kw_is_claim;
  if ((DC_SPEED_CLAIM_KEYS as readonly string[]).includes(key)) return !!row.dc_speed_is_claim;
  return false;
}

/** True when `key` must read as missing for this row (a DC-behaviour field on a car without DC data). */
export function hiddenForNoDc(row: DcRow, key: string): boolean {
  return isDcDependent(key) && !hasDcData(row);
}
