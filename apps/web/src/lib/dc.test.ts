import type { FieldProvenance, PublishedVariant } from "@ev/schema";
import { describe, expect, it } from "vitest";
import { rowSources } from "@/components/Explore";
import { catalogue, row } from "@/test/helpers";
import { DC_SPEED_CLAIM_KEYS, hasDcData, hiddenForNoDc, isClaimField } from "./dc";
import { defaultFilters } from "./state";
import { applyFilters } from "./filters";
import { cellValue, DIFF_KEYS, fieldsFor, SPEC_FIELDS, specDiff } from "./spec-diff";

const field = (key: string) => SPEC_FIELDS.find((f) => f.key === key)!;

function v(over: Partial<PublishedVariant> & { variant_id: string }): PublishedVariant {
  return {
    release: 1,
    variant_name: over.variant_id,
    generation_id: "g",
    generation_name: "G",
    model_id: "m",
    model_name: "M",
    make_id: "mk",
    make_name: "Make",
    year_start: 2020,
    era: "2018-20",
    quality_tier: "sourced",
    provenance: {},
    ...over,
  };
}

// The release-1 bug: 400 V behaviour recorded, but no DC figure at all.
const noDc = v({ variant_id: "no-dc", charger_400v_mode: "booster", charger_400v_kw: 50, fast_on_400v: true });
const withDc = v({ variant_id: "dc", dc_peak_kw: 175, charger_400v_mode: "booster", charger_400v_kw: 50, fast_on_400v: true });

describe("hasDcData", () => {
  it("needs a positive DC figure (peak, 10-80 % average or minutes)", () => {
    expect(hasDcData({})).toBe(false);
    expect(hasDcData({ dc_peak_kw: null })).toBe(false);
    expect(hasDcData({ dc_peak_kw: 0 })).toBe(false);
    expect(hasDcData({ dc_peak_kw: Number.NaN })).toBe(false);
    expect(hasDcData({ dc_peak_kw: 50 })).toBe(true);
    expect(hasDcData({ dc_avg_10_80_kw: 40 })).toBe(true);
    expect(hasDcData({ dc_minutes_10_80: 30 })).toBe(true);
  });

  it("hides only DC-behaviour fields", () => {
    expect(hiddenForNoDc(noDc, "charger_400v_mode")).toBe(true);
    expect(hiddenForNoDc(noDc, "charger_400v_kw")).toBe(true);
    expect(hiddenForNoDc(noDc, "fast_on_400v")).toBe(true);
    expect(hiddenForNoDc(noDc, "real_range_km")).toBe(false);
    expect(hiddenForNoDc(withDc, "charger_400v_mode")).toBe(false);
  });
});

describe("no DC data → no 400 V behaviour anywhere", () => {
  it("cellValue (spec diff and compare) reads the fields as missing", () => {
    expect(cellValue(noDc, field("charger_400v_mode"))).toBeNull();
    expect(cellValue(noDc, field("charger_400v_kw"))).toBeNull();
    expect(cellValue(withDc, field("charger_400v_mode"))).toBe("booster");
    expect(cellValue(withDc, field("charger_400v_kw"))).toBe(50);
  });

  it("the generation spec diff drops the 400 V row when no variant has DC data", () => {
    const diff = specDiff([noDc, { ...noDc, variant_id: "no-dc-2", charger_400v_mode: "native" }], fieldsFor(DIFF_KEYS));
    expect(diff.rows.map((r) => r.field.key)).not.toContain("charger_400v_mode");
  });

  it("Explore's 'fast on 400 V' filter never matches a car without DC data", () => {
    const out = applyFilters([row(noDc), row(withDc)], { ...defaultFilters(), fast400: true }, "NL");
    expect(out.map((r) => r.variant_id)).toEqual(["dc"]);
  });

  it("Explore rows carry every DC figure hasDcData looks at", () => {
    expect(hasDcData(row({ variant_id: "m", dc_minutes_10_80: 31 }))).toBe(true);
  });

  it("the Nerd sources list skips the 400 V power of a car without DC data", () => {
    const prov: FieldProvenance = { source_ids: ["s"], confidence: "low" };
    const r = row({ ...noDc, provenance: { charger_400v_kw: prov } });
    expect(rowSources(r, "NL", {}).map((x) => x.key)).not.toContain("charger_400v_kw");
    const d = row({ ...withDc, provenance: { charger_400v_kw: prov, dc_peak_kw: prov } });
    expect(rowSources(d, "NL", { s: "Src" }).map((x) => x.key)).toEqual(["dc_peak_kw", "charger_400v_kw"]);
  });

  it("the dev fixture's Zoe R240 has no DC data (e2e relies on it)", () => {
    const zoe = catalogue.rows.find((r) => r.variant_id === "renault-zoe-x10-r240")!;
    expect(zoe).toBeTruthy();
    expect(hasDcData(zoe)).toBe(false);
  });
});

describe("isClaimField (T-157)", () => {
  it("flags dc_peak_kw only when dc_peak_kw_is_claim is true", () => {
    expect(isClaimField({ dc_peak_kw_is_claim: true }, "dc_peak_kw")).toBe(true);
    expect(isClaimField({ dc_peak_kw_is_claim: false }, "dc_peak_kw")).toBe(false);
    expect(isClaimField({ dc_speed_is_claim: true }, "dc_peak_kw")).toBe(false);
  });

  it("flags all four DC speed fields when dc_speed_is_claim is true, and never other fields", () => {
    for (const key of DC_SPEED_CLAIM_KEYS) {
      expect(isClaimField({ dc_speed_is_claim: true }, key), key).toBe(true);
      expect(isClaimField({ dc_speed_is_claim: false }, key), key).toBe(false);
      expect(isClaimField({ dc_peak_kw_is_claim: true }, key), key).toBe(false);
    }
    expect(isClaimField({ dc_speed_is_claim: true, dc_peak_kw_is_claim: true }, "real_range_km")).toBe(false);
    expect(isClaimField({ dc_speed_is_claim: true, dc_peak_kw_is_claim: true }, "ac_kw")).toBe(false);
  });
});
