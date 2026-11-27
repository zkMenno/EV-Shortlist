import { describe, expect, it } from "vitest";
import { row } from "@/test/helpers";
import { EXPLORE_FIELDS } from "./explore-data";

describe("Explore rows keep WLTP, never EPA (T-061)", () => {
  it("does not ship epa_range_km to the browser", () => {
    expect(EXPLORE_FIELDS as readonly string[]).not.toContain("epa_range_km");
    const r = row({ variant_id: "x", wltp_range_km: 400, epa_range_km: 350, provenance: { epa_range_km: { source_ids: ["fueleconomy"], confidence: "medium" } } });
    expect(r).not.toHaveProperty("epa_range_km");
    expect(r.provenance).not.toHaveProperty("epa_range_km");
    expect(r.wltp_range_km).toBe(400);
  });
});

describe("WLTP ships with its provenance (T-143, Decision 085)", () => {
  it("keeps the official WLTP figure's source and confidence for <Num>", () => {
    const prov = { source_ids: ["openev"] as [string], confidence: "medium" as const };
    const r = row({ variant_id: "x", wltp_range_km: 452, provenance: { wltp_range_km: prov } });
    expect(r.provenance.wltp_range_km).toEqual(prov);
  });
});

describe("Nerd 'Sources' list reaches the WLTP source (T-143 review)", () => {
  it("lists the official WLTP figure's sources, so keyboard users can open them in the table", async () => {
    const { rowSources } = await import("@/components/Explore");
    const r = row({ variant_id: "x", wltp_range_km: 452, provenance: { wltp_range_km: { source_ids: ["openev"] as [string], confidence: "medium" } } });
    const hit = rowSources(r, "NL", { openev: "Open EV Data" }).find((x) => x.key === "wltp_range_km");
    expect(hit).toMatchObject({ label: "range.wltp.label", names: "Open EV Data", confidence: "medium" });
  });
});

describe("Client Explore provenance omits unused fact_ids (T-167 perf budget)", () => {
  it("drops fact_ids from Explore rows while keeping source_ids, confidence, estimate and note", () => {
    const r = row({
      variant_id: "x",
      wltp_range_km: 452,
      provenance: {
        wltp_range_km: {
          source_ids: ["rdw-tgk"] as [string],
          confidence: "high",
          estimate: false,
          note: "TGK best case",
          fact_ids: ["rdw-tgk:very-long-id-1", "rdw-tgk:very-long-id-2"],
        },
      },
    });
    expect(r.provenance.wltp_range_km).toEqual({
      source_ids: ["rdw-tgk"],
      confidence: "high",
      estimate: false,
      note: "TGK best case",
    });
    expect(r.provenance.wltp_range_km).not.toHaveProperty("fact_ids");
  });
});

describe("dc_speed_is_claim carried in Explore rows (T-157)", () => {
  it("carries dc_speed_is_claim when true and drops it when absent", () => {
    expect(EXPLORE_FIELDS as readonly string[]).toContain("dc_speed_is_claim");
    const claimed = row({ variant_id: "elroq-85", dc_speed_is_claim: true, dc_km_per_20min: 192.3 });
    expect(claimed.dc_speed_is_claim).toBe(true);
    const measured = row({ variant_id: "measured", dc_km_per_20min: 200 });
    expect(measured).not.toHaveProperty("dc_speed_is_claim");
  });
});

