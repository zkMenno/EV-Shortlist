// The optional bigger on-board charger next to the standard one (T-063 field ac_kw_optional).
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { SPEC_FIELDS } from "@/lib/spec-diff";
import { pageCtx } from "../_lib/context";
import { SpecValue } from "./SpecValue";

const ctx = pageCtx("nl", "en");
const field = SPEC_FIELDS.find((f) => f.key === "ac_kw")!;
const base = ctx.cat.rows()[0]!;
const text = (html: string) => html.replace(/<[^>]+>/g, "").replace(/&nbsp;|\u00a0/g, " ").replace(/\s+/g, " ");

describe("SpecValue: AC charging power", () => {
  it('shows "7.4 kW (11 kW optional)" when a bigger charger is optional', () => {
    const row = { ...base, ac_kw: 7.4, ac_kw_optional: 11 };
    const html = renderToStaticMarkup(<SpecValue ctx={ctx} row={row} field={field} />);
    expect(html).toContain('data-testid="ac-optional"');
    expect(text(html)).toMatch(/7\.4 kW[\s\S]*\(11 kW[\s\S]* optional\)$/);
  });

  it("shows only the standard power without an optional one", () => {
    const row = { ...base, ac_kw: 11, ac_kw_optional: null };
    const html = renderToStaticMarkup(<SpecValue ctx={ctx} row={row} field={field} />);
    expect(html).not.toContain("ac-optional");
    expect(text(html)).not.toContain("optional");
    expect(text(html)).toMatch(/11(\.0)? kW/);
  });
});

describe("SpecValue: dc_speed_is_claim badge (T-157)", () => {
  const dcSpeedKeys = ["dc_avg_10_80_kw", "dc_minutes_10_80", "dc_km_per_10min", "dc_km_per_20min"] as const;
  const prov = { source_ids: ["maker-docs"] as [string], confidence: "medium" as const, derived: true };
  const claimRow = {
    ...base,
    dc_speed_is_claim: true,
    dc_peak_kw_is_claim: false,
    dc_peak_kw: 175,
    dc_avg_10_80_kw: 115.5,
    dc_minutes_10_80: 28,
    dc_km_per_10min: 96.2,
    dc_km_per_20min: 192.3,
    real_range_km: 400,
    provenance: {
      ...base.provenance,
      dc_peak_kw: prov,
      dc_avg_10_80_kw: prov,
      dc_minutes_10_80: prov,
      dc_km_per_10min: prov,
      dc_km_per_20min: prov,
      real_range_km: prov,
    },
  };

  it("shows the claim badge on all four DC speed fields when dc_speed_is_claim is true", () => {
    for (const key of dcSpeedKeys) {
      const f = SPEC_FIELDS.find((s) => s.key === key)!;
      const html = renderToStaticMarkup(<SpecValue ctx={ctx} row={claimRow} field={f} />);
      expect(html, key).toContain('data-testid="num-badges"');
      expect(html, key).toContain(`>${ctx.labels.claim}<`);
      expect(html, key).toContain(ctx.labels.claimHelp);
    }
  });

  it("does not show the claim badge on non-DC-speed fields or when dc_speed_is_claim is false", () => {
    const peakHtml = renderToStaticMarkup(<SpecValue ctx={ctx} row={claimRow} field={SPEC_FIELDS.find((s) => s.key === "dc_peak_kw")!} />);
    expect(peakHtml).not.toContain(`>${ctx.labels.claim}<`);
    const rangeHtml = renderToStaticMarkup(<SpecValue ctx={ctx} row={claimRow} field={SPEC_FIELDS.find((s) => s.key === "real_range_km")!} />);
    expect(rangeHtml).not.toContain(`>${ctx.labels.claim}<`);

    const measuredRow = { ...claimRow, dc_speed_is_claim: false };
    for (const key of dcSpeedKeys) {
      const f = SPEC_FIELDS.find((s) => s.key === key)!;
      const html = renderToStaticMarkup(<SpecValue ctx={ctx} row={measuredRow} field={f} />);
      expect(html, key).not.toContain(`>${ctx.labels.claim}<`);
      expect(html, key).not.toContain(ctx.labels.claimHelp);
    }
  });
});
